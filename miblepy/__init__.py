__version__ = "0.4.6"

import importlib
import inspect
import json
import logging
import os
import pkgutil
import time

from datetime import datetime
from enum import Enum
from random import shuffle
from typing import Any, Dict, List, Optional, Set, Union

import paho.mqtt.client as mqtt

from tomlkit import parse
from tomlkit.toml_document import TOMLDocument

from bluepy import btle
from miblepy.deviceplugin import MibleDevicePlugin


DEVICE_PREFIX = "miblepy_"

MAX_RETRIES = 3
INITIAL_TIMEOUT = 1
CONFIG_FILE = "~/.mible.toml"


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
    FW_VERSION = "fw_version"
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

    def __init__(self, config_file_path: str, verbose: bool = False, debug: bool = False):

        with open(config_file_path, "r") as file:
            config_file = parse(file.read())

        self.config_file: TOMLDocument = config_file
        self.config: Dict[str, Any] = {}

        config_general = config_file.get("general")

        # debug
        self.debug = debug or config_general.get("debug", False)
        if self.debug:
            self.loglevel = logging.DEBUG
        elif verbose:
            self.loglevel = logging.INFO
        else:
            self.loglevel = logging.WARNING

        # logging
        timeform = "%Y-%m-%d %H:%M:%S"
        logform = "{asctime} {levelname} {message}"

        if logfile := config_general.get("logfile"):
            logging.basicConfig(
                level=logging.INFO, filename=logfile, datefmt=timeform, format=logform, style="{",
            )
        else:
            logging.basicConfig(level=logging.INFO, datefmt=timeform, format=logform, style="{")

        # ble interface
        self.interface: str = config_general.get("interface", "hci0")
        self.max_retries: int = config_general.get("max_retries", MAX_RETRIES)

        #  mqtt
        mqtt_settings: Dict[str, Any] = {}
        config_mqtt = config_file.get("mqtt")
        if "server" not in config_mqtt:
            logging.error("no mqtt server")
        else:
            mqtt_settings["server"] = config_mqtt.get("server")
            mqtt_settings["port"] = config_mqtt.get("port", 8883)
            mqtt_settings["client_id"] = config_mqtt.get("client_id")
            mqtt_settings["user"] = config_mqtt.get("username")
            mqtt_settings["password"] = config_mqtt.get("password")
            mqtt_settings["discovery_prefix"] = config_mqtt.get("discovery_prefix")
            mqtt_settings["prefix"] = config_mqtt.get("prefix", "miblepy/")
            mqtt_settings["trailing_slash"] = config_mqtt.get("trailing_slash", False)
            mqtt_settings["timestamp_format"] = config_mqtt.get("timestamp_format")
            mqtt_settings["ca_cert"] = config_mqtt.get("ca_cert")

        # sensors
        if "sensors" not in config_file:
            logging.error("no mqtt server")
        else:
            sensors: List[DeviceConfig] = []

            for device_type in config_file.get("sensors", {}):
                for sensor in config_file["sensors"][device_type]:
                    fail_silent = "fail_silent" in sensor
                    sensors.append(DeviceConfig(sensor, device_type, fail_silent))

        self.sensors = sensors
        self.mqtt = mqtt_settings

    def __str__(self) -> str:
        return str(self.config_file.as_string())


class DeviceConfig:
    """Stores the configuration of a sensor."""

    def __init__(self, config: Dict[str, Any], device_type: str, fail_silent: bool = False):
        if "mac" not in config:
            logging.exception("mac of sensor must not be None")

        self.mac: str = config.pop("mac")

        self.alias: Optional[str] = config.get("alias", None)
        self.device_type = device_type
        self.fail_silent = fail_silent

        # config file settings
        self.config: Dict[str, Any] = config

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


class Miblepy:
    """Main class of the module."""

    def __init__(
        self,
        config_file_path: str = CONFIG_FILE,
        retries: int = MAX_RETRIES,
        verbose: bool = False,
        debug: bool = False,
    ):
        config_file_path = os.path.abspath(os.path.expanduser(config_file_path))
        self.config = Configuration(config_file_path, verbose=verbose, debug=debug)

        self.config.max_retries = retries
        self.mqtt_client: Optional[mqtt.Client] = None
        self.connected = False

        # logging.getLogger().setLevel(logging.INFO)
        logging.info(
            f"{hl(__name__)} {__version__} | fetching from {hl(len(self.config.sensors))} sensors "
            f"(of {hl(len(self.config.config_file['sensors']))} types) | max retries: {hl(self.config.max_retries)}"
        )

        # set loglevel
        logging.getLogger().setLevel(self.config.loglevel)

        logging.info(
            f"config file: {hl(config_file_path)} | interface: /dev/{hl(self.config.interface)} | "
            f"debug: {hl(self.config.debug)}"
        )
        logging.debug(f"configuration: {self.config.config_file}")

    def start_client(self) -> None:
        """Start the mqtt client."""
        if not self.connected:
            self._start_client()

    def stop_client(self) -> None:
        """Stop the mqtt client."""
        if self.mqtt_client:
            if self.connected:
                self.mqtt_client.disconnect()
                self.connected = False
            self.mqtt_client.loop_stop()
            logging.debug(
                f"disconnected MQTT connection to server "
                f"{hl(self.config.mqtt['server'] + ':' + str(self.config.mqtt['port']))}"
            )

    def _start_client(self) -> None:
        self.mqtt_client = mqtt.Client(self.config.mqtt["client_id"])

        if self.config.mqtt["user"]:
            self.mqtt_client.username_pw_set(self.config.mqtt["user"], self.config.mqtt["password"])

        if self.config.mqtt["ca_cert"]:
            self.mqtt_client.tls_set(self.config.mqtt["ca_cert"], cert_reqs=mqtt.ssl.CERT_REQUIRED)

        def _on_connect(client: Any, _: Any, flags: Any, return_code: int) -> None:  # skipcq: PYL-W0613
            self.connected = True
            logging.debug(
                f"MQTT connection to {hl(self.config.mqtt['server'] + ':' + str(self.config.mqtt['port']))} established"
            )

        self.mqtt_client.on_connect = _on_connect

        logging.debug(f"MQTT connecting to {hl(self.config.mqtt['server'] + ':' + str(self.config.mqtt['port']))}...")
        self.mqtt_client.connect(str(self.config.mqtt["server"]), int(self.config.mqtt["port"]), 60)
        self.mqtt_client.loop_start()

    def _publisher(self, topic: str, data: Dict[str, Any]) -> None:
        if self.config.mqtt["timestamp_format"]:
            data["timestamp"] = datetime.now().strftime(self.config.mqtt["timestamp_format"])

        if self.mqtt_client:
            msg: mqtt.MQTTMessageInfo = self.mqtt_client.publish(topic, json.dumps(data), qos=1, retain=True)
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

    def _get_state_topic(self, sensor_config: DeviceConfig) -> str:
        """Construct state topic to publish to."""
        device_topic = self._get_device_topic(sensor_config, None)

        return f"{self.config.mqtt['prefix']}/{device_topic}{'/' if self.config.mqtt['trailing_slash'] else ''}"

    def _get_announce_topic(self, short_mac: str, name: str) -> str:
        """Construct announce topic to publish to."""
        return f"{self.config.mqtt['discovery_prefix']}/sensor/{short_mac}_{name}/config".replace(" ", "_")

    def fetch(self, sensor_config: DeviceConfig) -> Dict[str, Any]:
        """Get data from one Sensor."""
        logging.info(f"· {hl(sensor_config.name)} ({sensor_config.mac}): fetching data from device...")

        data: Dict[str, Any] = {}

        if miblepy_plugin := get_plugins().get(sensor_config.device_type):
            plugin_class = miblepy_plugin.get("class")
            plugin: MibleDevicePlugin = plugin_class(sensor_config.mac, self.config.interface, **sensor_config.config)
        else:
            return data

        try:
            data = plugin.fetch_data(**sensor_config.config)
        except btle.BTLEDisconnectError as error:
            logging.info(f"· {hl(sensor_config.name)}: ble disconnected: {error}")
        except Exception as error:
            logging.error(f"· {hl(sensor_config.name)}: error when trying to fetch data: {error}")

        if not data:
            logging.info(
                f"· {hl(sensor_config.name)}: no data received from plugin "
                f"{hl(plugin.plugin_name)} "
                f"for device {hl(sensor_config.name)} ({sensor_config.mac})!"
            )
            return data

        entity_list = data.get("sensors", []) + data.get("binary_sensors", [])

        state_topic = self._get_state_topic(sensor_config)
        state_published = False

        for entity in entity_list:
            entity_name = entity["name"]
            entity_type: ATTRS = entity["entity_type"]
            unique_id = f"{sensor_config.short_mac}_{entity_name}".replace(" ", "_")
            announce_topic = self._get_announce_topic(sensor_config.short_mac, entity_name)

            payload = {
                "name": entity_name,
                "state_topic": state_topic,
                "json_attributes_topic": state_topic,
                "value_template": entity["value_template"],
                "unique_id": unique_id,
            }

            if entity_type in UNIT_OF_MEASUREMENT:
                payload["unit_of_measurement"] = UNIT_OF_MEASUREMENT[entity_type]

            if DEVICE_CLASS[entity_type]:
                payload["device_class"] = str(DEVICE_CLASS[entity_type])

            if "own_state_topic" in entity:
                payload["state_topic"] = (
                    f"{self.config.mqtt['prefix']}/{sensor_config.short_mac}_{entity_name}"
                    f"{'/' if self.config.mqtt['trailing_slash'] else ''}"
                ).replace(" ", "_")

                payload["json_attributes_topic"] = payload["state_topic"]

                # push sensor values
                self._publisher(payload["state_topic"], data["attributes"])
                state_published = True
                logging.info(f"· {hl(sensor_config.name)}: sent sensor values to {hl(payload['state_topic'])}")

            self._publisher(announce_topic, payload)
            logging.info(f"· {hl(sensor_config.name)}: sent {hl(entity_name)} configuration to {hl(announce_topic)}")

        # push sensor values
        if not state_published:
            self._publisher(state_topic, data["attributes"])
            logging.info(f"· {hl(sensor_config.name)}: sent sensor values to {hl(state_topic)}")

        return data

    def go(self) -> Set[DeviceConfig]:
        """Get data from all sensors."""
        sensors_list: Set[DeviceConfig] = set(self.config.sensors)

        # initial timeout in seconds
        timeout = INITIAL_TIMEOUT

        retry_count = 1

        while not self.connected:
            self.start_client()
            time.sleep(0.1)

        while retry_count <= self.config.max_retries and sensors_list:

            # if this is not the first try: wait some time before trying again
            if retry_count > 1:
                logging.info(
                    f"try {retry_count}/{self.config.max_retries} for "
                    f"{', '.join((hl(str(sensor.alias)) for sensor in sensors_list))} in {hl(timeout)}s"
                )
                time.sleep(timeout)

                # exponential backoff-time
                timeout *= 2

            # collect failed sensor for next round
            failed_sensors_list: Set[DeviceConfig] = set()

            # increment retry counter
            retry_count += 1

            shuffle([sensors_list])

            # process sensors in list
            for sensor in sensors_list:

                try:
                    if not self.fetch(sensor):
                        # try again in the next round
                        failed_sensors_list.add(sensor)

                except Exception as exception:  # pylint: disable=bare-except, broad-except

                    # try again in the next round
                    failed_sensors_list.add(sensor)

                    msg = f"{hl(sensor.config.name)}: could not read data with reason: {str(exception)}"  # type: ignore

                    if sensor.fail_silent:
                        logging.error(msg)
                        # logging.warning(
                        #     "fail_silent is set for sensor %s, so not raising an exception.",
                        #     sensor.alias,
                        # )
                    else:
                        logging.exception(msg)
                        print(msg)

            sensors_list = failed_sensors_list

        # build summary message
        result_message = (
            f"successfully fetched data from {hl(len(self.config.sensors) - len(failed_sensors_list))} devices"
        )

        # check if have failed ones
        if failed_sensors_list:
            result_message += (
                f" | {hl(len(failed_sensors_list))} failed (after {retry_count - 1} retries): "
                f"{', '.join((hl(str(sensor.alias)) for sensor in sensors_list))}"
            )

        logging.getLogger().setLevel(logging.INFO)
        logging.info(result_message)

        # return sensors that could not be processed after max_retries
        return failed_sensors_list


def get_plugins() -> Dict[str, Any]:
    """Discover available device plugins in plugin dir."""
    plugin_path = os.path.join(os.path.dirname(__file__), "devices")
    modules = pkgutil.iter_modules(path=[plugin_path])

    plugins: Dict[str, Any] = {}

    for loader, mod_name, ispkg in modules:

        try:
            imported_package = importlib.import_module(f"miblepy.devices.{mod_name}")

            for (key, value) in inspect.getmembers(imported_package, inspect.isclass):

                if issubclass(value, MibleDevicePlugin) & (value is not MibleDevicePlugin):

                    plugins.update(
                        {
                            mod_name: {
                                "module": value.__module__,
                                "class_name": value.__name__,
                                "class": getattr(importlib.import_module(value.__module__), value.__name__),
                                "config_key": mod_name,
                            }
                        }
                    )

        except (ModuleNotFoundError, ImportError) as error:
            print(error)
            pass

    return plugins
