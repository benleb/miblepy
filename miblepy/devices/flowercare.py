# supported devices
#   VegTrug Plant Sensor (???)
#   Mi Flora? (???)

from datetime import datetime
from typing import Any, Dict

from bluepy.btle import Peripheral
from miblepy import ATTRS


PLUGIN_NAME = "Flower Care"


def fetch_data(mac: str, interface: str, **kwargs: Any) -> Dict[str, Any]:
    """Get data from one Sensor."""

    # connect to device
    peripheral = Peripheral(mac, iface=int(interface.replace("hci", "")))

    # enable reading of values
    peripheral.writeCharacteristic(0x33, bytes([0xA0, 0x1F]), withResponse=True)

    # 7b in little endian
    #    0: battery level
    #    1: unknown
    #  2-6: firmware version
    battery_and_firmware: bytes = peripheral.readCharacteristic(0x38)
    battery_level = int.from_bytes(battery_and_firmware[:1], byteorder="little")
    firmware_version = str(battery_and_firmware[2:].decode("utf-8"))

    # 16b in little endian
    #   0-1: temperature in 0.1 °C
    #     2: unknown
    #   3-6: brightness in lux
    #     7: moisture in %
    #   8-9: conductivity in µS/cm
    # 10-15: unknown
    data: bytes = peripheral.readCharacteristic(0x35)

    device_name = kwargs.get("alias", None)

    plugin_data: Dict[str, Any] = {
        "name": PLUGIN_NAME,
        "sensors": [
            {
                "name": f"{device_name} {ATTRS.TEMPERATURE.value.capitalize()}",
                "value_template": "{{value_json." + ATTRS.TEMPERATURE.value + "}}",
                "entity_type": ATTRS.TEMPERATURE,
            },
            {
                "name": f"{device_name} {ATTRS.BRIGHTNESS.value.capitalize()}",
                "value_template": "{{value_json." + ATTRS.BRIGHTNESS.value + "}}",
                "entity_type": ATTRS.BRIGHTNESS,
            },
            {
                "name": f"{device_name} {ATTRS.MOISTURE.value.capitalize()}",
                "value_template": "{{value_json." + ATTRS.MOISTURE.value + "}}",
                "entity_type": ATTRS.MOISTURE,
            },
            {
                "name": f"{device_name} {ATTRS.CONDUCTIVITY.value.capitalize()}",
                "value_template": "{{value_json." + ATTRS.CONDUCTIVITY.value + "}}",
                "entity_type": ATTRS.CONDUCTIVITY,
            },
            {
                "name": f"{device_name} {ATTRS.BATTERY.value.capitalize()}",
                "value_template": "{{value_json." + ATTRS.BATTERY.value + "}}",
                "entity_type": ATTRS.BATTERY,
            },
        ],
        "attributes": {
            ATTRS.BATTERY.value: str(battery_level),
            ATTRS.TEMPERATURE.value: str(int.from_bytes(data[0:2], byteorder="little") / 10),
            ATTRS.BRIGHTNESS.value: str(int.from_bytes(data[3:6], byteorder="little")),
            ATTRS.MOISTURE.value: str(int.from_bytes(data[7:8], byteorder="little")),
            ATTRS.CONDUCTIVITY.value: str(int.from_bytes(data[8:10], byteorder="little")),
            ATTRS.FW_VERSION.value: firmware_version,
            ATTRS.TIMESTAMP.value: datetime.now().isoformat(),
        },
    }

    return plugin_data
