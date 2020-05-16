
__version__ = "0.1.0"

import importlib
import json
import logging
import os
import time

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

import paho.mqtt.client as mqtt

from tomlkit import parse


MI_TEMPERATURE = "temperature"
MI_LIGHT = "light"
MI_MOISTURE = "moisture"
MI_CONDUCTIVITY = "conductivity"
MI_BATTERY = "battery"

DEVICE_PREFIX = "miblepy_"
DEFAULT_MAX_RETRIES = 1

DEFAULT_CONFIG_FILE = f"{os.environ.get('HOME', '')}/.miblepy.toml"


class ATTRS(Enum):
    """Attributes sent in the json dict."""

    AGE = "age"
    BASAL_METABOLISM = "basal_metabolism"
    BATTERY = "battery"
    BMI = "bmi"
    BODY_FAT = "body_fat"
    BONE_MASS = "bone_mass"
    BRIGHTNESS = "brightness"
    CONDUCTIVITY = "conductivity"
    HEIGHT = "height"
    HUMIDITY = "humidity"
    IMPEDANCE = "impedance"
    LEAN_BODY_MASS = "lean_body_mass"
    MOISTURE = "moisture"
    MUSCLE_MASS = "muscle_mass"
    MQTT_SUFFIX = "suffix"
    PROTEIN = "protein"
    SEX = "sex"
    TEMPERATURE = "temperature"
    TIMESTAMP = "timestamp"
    UNIT = "unit"
    USER = "user"
    VISCERAL_FAT = "visceral_fat"
    VOLTAGE = "voltage"
    WATER = "water"
    WEIGHT = "weight"


# unit of measurement for the different attributes
UNIT_OF_MEASUREMENT = {
    ATTRS.BATTERY: "%",
    ATTRS.VOLTAGE: "V",
    ATTRS.TEMPERATURE: "°C",
    ATTRS.BRIGHTNESS: "lux",
    ATTRS.MOISTURE: "%",
    ATTRS.HUMIDITY: "%",
    ATTRS.IMPEDANCE: "Ω",
    ATTRS.CONDUCTIVITY: "µS/cm",
    ATTRS.TIMESTAMP: "s",
    ATTRS.HEIGHT: "cm",
    ATTRS.WEIGHT: "kg",
    ATTRS.UNIT: None,
    ATTRS.USER: None,
}


# home assistant device classes for the different attributes
DEVICE_CLASS = {
    ATTRS.BATTERY: "battery",
    ATTRS.VOLTAGE: "battery",
    ATTRS.TEMPERATURE: "temperature",
    ATTRS.BRIGHTNESS: "illuminance",
    ATTRS.MOISTURE: None,
    ATTRS.HUMIDITY: None,
    ATTRS.CONDUCTIVITY: None,
    ATTRS.TIMESTAMP: "timestamp",
    ATTRS.WEIGHT: None,
    ATTRS.IMPEDANCE: None,
    ATTRS.UNIT: None,
    ATTRS.USER: None,
}


def hl(text: Union[int, float, str]) -> str:
    return f"\033[1m{text}\033[0m"


# pylint: disable-msg=too-many-instance-attributes
class Configuration:
    """Stores the program configuration."""

    def __init__(self, config_file_path: str, debug: bool = False):
        with open(config_file_path, "r") as file:
            config_file = parse(file.read())

        self.config_file = config_file
        self.config = {}

        config_general = config_file.get("general")

        # logging
        if debug:
            config_general["debug"] = debug
        self.debug: str = config_general.get("debug", False)
        self._configure_logging(config_general)

        # ble interface
        self.interface: str = config_general.get("interface", "hci0")
        self.max_retries: str = config_general.get("max_retries", DEFAULT_MAX_RETRIES)

        #  mqtt
        mqtt: Dict[str, Any] = {}
        config_mqtt = config_file.get("mqtt")
        if "server" not in config_mqtt:
            logging.error("no mqtt server")
        else:
            mqtt["server"]: str = config_mqtt.get("server")
            mqtt["port"]: int = config_mqtt.get("port", 8883)
            mqtt["client_id"]: Optional[str] = config_mqtt.get("client_id")
            mqtt["user"]: Optional[str] = config_mqtt.get("username")
            mqtt["password"]: Optional[str] = config_mqtt.get("password")
            mqtt["discovery_prefix"]: Optional[str] = config_mqtt.get("discovery_prefix")
            mqtt["prefix"] = config_mqtt.get("prefix", "miblepy/")
            mqtt["trailing_slash"]: bool = config_mqtt.get("trailing_slash", False)
            mqtt["timestamp_format"]: Optional[str] = config_mqtt.get("timestamp_format")
            mqtt["ca_cert"]: Optional[str] = config_mqtt.get("ca_cert")

        # sensors
        if "sensors" not in config_file:
            logging.error("no mqtt server")
        else:
            sensors: List[DeviceConfig] = []

            for device_type in config_file.get("sensors", {}):
                for sensor in config_file["sensors"][device_type]:
                    fail_silent = "fail_silent" in sensor
                    sensors.append(
                        DeviceConfig(sensor["mac"], sensor["alias"], device_type, fail_silent)
                    )

        self.sensors = sensors
        self.mqtt = mqtt

        def __str__(self) -> str:
            return self.config_file

    @staticmethod
    def _configure_logging(config):
        timeform = "%Y-%m-%d %H:%M:%S"
        logform = "%(asctime)s %(levelname)-7s %(message)s"
        loglevel = logging.INFO if not config["debug"] else logging.DEBUG

        if "logfile" in config:
            logfile = os.path.abspath(os.path.expanduser(config["logfile"]))
            logging.basicConfig(filename=logfile, level=loglevel, datefmt=timeform, format=logform)
        else:
            logging.basicConfig(level=loglevel, datefmt=timeform, format=logform)


class DeviceConfig:
    """Stores the configuration of a sensor."""

    def __init__(
        self, mac: str, alias: str = None, device_type: str = None, fail_silent: bool = False
    ):
        if not mac:
            logging.exception("mac of sensor must not be None")

        self.mac = mac
        self.alias = alias
        self.device_type = device_type
        self.fail_silent = fail_silent

    @property
    def name(self) -> str:
        return self.alias if self.alias else self.mac

    @property
    def short_mac(self) -> str:
        """Get the sensor mac without ':' in it."""
        return self.mac.replace(":", "")

    def get_topic(self) -> str:
        """Get the topic name for the sensor."""
        return f"{self.alias.replace(' ', '_')}_{self.short_mac}" if self.alias else self.mac

    def __str__(self) -> str:
        return f"{self.alias if self.alias else self.mac}{' (fail silent)' if self.fail_silent else ''}"

    @staticmethod
    def get_name_string(sensor_list: List) -> str:
        """Convert a list of sensor objects to a nice string."""
        return ", ".join((str(sensor.alias) for sensor in sensor_list))


class Miblepy:
    """Main class of the module."""

    def __init__(self, config_file_path: str = "~/.miblepy.toml", retries: int = DEFAULT_MAX_RETRIES, debug: bool = False):
        config_file_path = os.path.abspath(os.path.expanduser(config_file_path))
        self.config = Configuration(config_file_path, debug=debug)

        logging.info("")
        logging.info(f"{hl(__name__)} {__version__}")
        logging.info("")
        logging.info(f"config file: {hl(config_file_path)}")
        logging.info(f"  interface: /dev/{hl(self.config.interface)}")
        logging.info(f"      debug: {hl(self.config.debug)}")
        logging.debug("")
        logging.debug(f"configuration: {self.config.config_file}")
        logging.info("")

        self.mqtt_client = None
        self.connected = False

        # sys.exit(0)

    def start_client(self):
        """Start the mqtt client."""
        if not self.connected:
            self._start_client()

    def stop_client(self):
        """Stop the mqtt client."""
        if self.connected:
            self.mqtt_client.disconnect()
            self.connected = False
        self.mqtt_client.loop_stop()
        logging.debug("")
        logging.debug(
            f"disconnected MQTT connection to server {hl(self.config.mqtt['server'] + ':' + str(self.config.mqtt['port']))}"
        )

    def _start_client(self):
        self.mqtt_client: mqtt.Client = mqtt.Client(self.config.mqtt["client_id"])

        if self.config.mqtt["user"]:
            self.mqtt_client.username_pw_set(self.config.mqtt["user"], self.config.mqtt["password"])

        if self.config.mqtt["ca_cert"]:
            self.mqtt_client.tls_set(self.config.mqtt["ca_cert"], cert_reqs=mqtt.ssl.CERT_REQUIRED)

        def _on_connect(client, _, flags, return_code):
            self.connected = True
            logging.info(
                f"MQTT connection to {hl(self.config.mqtt['server'] + ':' + str(self.config.mqtt['port']))} established"  #: {mqtt.connack_string(return_code)}"
            )

        self.mqtt_client.on_connect = _on_connect

        logging.debug(
            f"MQTT connecting to {hl(self.config.mqtt['server'] + ':' + str(self.config.mqtt['port']))}..."
        )
        self.mqtt_client.connect(str(self.config.mqtt["server"]), int(self.config.mqtt["port"]), 60)
        self.mqtt_client.loop_start()

    def _publisher(self, topic: str, data: str):
        # state_topic = state_topic.replace(" ", "_")

        if self.config.mqtt["timestamp_format"]:
            data["timestamp"] = datetime.now().strftime(self.config.mqtt["timestamp_format"])

        msg: mqtt.MQTTMessageInfo = self.mqtt_client.publish(
            topic, json.dumps(data), qos=1, retain=True
        )
        msg.wait_for_publish()
        logging.debug(f"sent {data} to topic {topic} - published: {msg.is_published()}")

    @staticmethod
    def _get_device_topic(sensor_config: DeviceConfig, suffix: Optional[str] = None) -> str:
        device_topic = (
            f"{sensor_config.short_mac}_{sensor_config.alias.replace(' ', '_')}"
            if sensor_config.alias
            else sensor_config.short_mac
        )

        return f"{device_topic}{f'_{suffix}' if suffix else ''}"

    def _get_state_topic(self, sensor_config: DeviceConfig, suffix: Optional[str] = None) -> str:
        """Construct state topic to publish to."""
        device_topic = self._get_device_topic(sensor_config, suffix)

        return f"{self.config.mqtt['prefix']}/{device_topic}{'/' if self.config.mqtt['trailing_slash'] else ''}"

    def _get_announce_topic(self, sensor_config: str, attribute: str, suffix: Optional[str] = None) -> str:
        """Construct announce topic to publish to."""
        device_topic = self._get_device_topic(sensor_config, suffix)

        return f"{self.config.mqtt['discovery_prefix']}/sensor/{device_topic}_{attribute}/config"

    def fetch(self, sensor_config: DeviceConfig) -> Dict[str, Any]:
        """Get data from one Sensor."""
        logging.info("")
        logging.info(f"fetching data from sensor {hl(sensor_config.name)} ({sensor_config.mac})...")

        try:
            device_backend = importlib.import_module(f"miblepy.devices.{sensor_config.device_type}")
        except (ModuleNotFoundError, ImportError) as error:
            logging.exception(f"required module {sensor_config.device_type} not found: {error}")
            return

        data = device_backend.fetch_data(
            sensor_config.mac, sensor_config.get_topic(), self.config.interface
        )

        if not data:
            logging.warning(f"  no data received from backend {device_backend.__name__} for device {hl(sensor_config.name)} ({sensor_config.mac})!")
            return None

        mqtt_device_suffix = data.get(ATTRS.MQTT_SUFFIX.value, None)
        state_topic = self._get_state_topic(sensor_config, mqtt_device_suffix)

        self.announce_sensor(
            device_backend.SUPPORTED_ATTRS,
            sensor_config,
            state_topic,
            suffix=mqtt_device_suffix
        )
        logging.info(
            f"  sent sensor configuration to {hl(self._get_announce_topic(sensor_config, '<attribute>', suffix=mqtt_device_suffix))}"
        )

        # push sensor values
        self._publisher(state_topic, data)
        logging.info(f"  sent sensor values to {hl(state_topic)}")

        return data

    def go(self):
        """Get data from all sensors."""
        sensors_list: Set[DeviceConfig] = set(self.config.sensors)

        # initial timeout in seconds
        timeout = 1

        # number of retries
        max_retries = self.config.max_retries

        retry_count = 1

        while not self.connected:
            self.start_client()
            time.sleep(0.1)

        while retry_count <= max_retries and sensors_list:

            # if this is not the first try: wait some time before trying again
            if retry_count > 1:
                logging.info("")
                logging.info(f"try {retry_count}/{max_retries} for {', '.join((hl(str(sensor.alias)) for sensor in sensors_list))} in {timeout}s")
                time.sleep(timeout)

                # exponential backoff-time
                timeout *= 2

            # collect failed sensor for next round
            failed_sensors_list: Set[DeviceConfig] = set()

            # increment retry counter
            retry_count += 1

            # process sensors in list
            for sensor in sensors_list:

                try:
                    if not self.fetch(sensor):
                        # try again in the next round
                        failed_sensors_list.add(sensor)

                except Exception as exception:  # pylint: disable=bare-except, broad-except

                    # try again in the next round
                    failed_sensors_list.add(sensor)

                    msg = "could not read data from {} ({}) with reason: {}".format(
                        sensor.mac, sensor.alias, str(exception)
                    )

                    if sensor.fail_silent:
                        logging.error(msg)
                        logging.warning(
                            "fail_silent is set for sensor %s, so not raising an exception.",
                            sensor.alias,
                        )
                    else:
                        logging.exception(msg)
                        print(msg)

            sensors_list = failed_sensors_list

        logging.info("")

        # return sensors that could not be processed after max_retries
        return failed_sensors_list

    def announce_sensor(
        self, supported_attributes: List[ATTRS], sensor_config: DeviceConfig, state_topic: str, suffix: Optional[str] = None
    ) -> None:
        """Announce the sensor via Home Assistant MQTT Discovery: https://www.home-assistant.io/docs/mqtt/discovery/"""

        for attribute in supported_attributes:

            payload = {
                "state_topic": state_topic,
                "unit_of_measurement": UNIT_OF_MEASUREMENT[attribute],
                "value_template": "{{value_json." + attribute.value + "}}",
            }
            if sensor_config.alias:
                payload["name"] = f"{sensor_config.alias} {attribute.value}"

            if DEVICE_CLASS[attribute]:
                payload["device_class"] = DEVICE_CLASS[attribute]

            announce_topic = self._get_announce_topic(sensor_config, attribute.value, suffix=suffix)

            # payloads.append(payload)
            self._publisher(announce_topic, payload)
