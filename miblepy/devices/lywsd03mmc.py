# supported devices
#   Mijia LCD Temperature Humidity Sensor (LYWSD03MMC)

from datetime import datetime
from typing import Any, Dict

from bluepy.btle import DefaultDelegate, Peripheral
from miblepy import ATTRS


PLUGIN_NAME = "LYWSD03MMC"


def fetch_data(mac: str, interface: str, **kwargs: Any) -> Dict[str, Any]:
    """Get data from one Sensor."""

    device_name = kwargs.get("alias", None)

    plugin_data: Dict[str, Any] = {}

    # connect to device
    peripheral = Peripheral(mac, iface=int(interface.replace("hci", "")))

    def handleNotification(cHandle: int, data: bytes) -> None:
        if cHandle != 0x36:
            return

        # parse data
        voltage = int.from_bytes(data[3:5], byteorder="little") / 1000

        plugin_data.update(
            {
                "name": PLUGIN_NAME,
                "sensors": [
                    {
                        "name": f"{device_name} {ATTRS.TEMPERATURE.value.capitalize()}",
                        "value_template": "{{value_json." + ATTRS.TEMPERATURE.value + "}}",
                        "entity_type": ATTRS.TEMPERATURE,
                    },
                    {
                        "name": f"{device_name} {ATTRS.HUMIDITY.value.capitalize()}",
                        "value_template": "{{value_json." + ATTRS.HUMIDITY.value + "}}",
                        "entity_type": ATTRS.HUMIDITY,
                    },
                ],
                "attributes": {
                    # 3.1 or above --> 100% 2.1 --> 0 %
                    ATTRS.BATTERY.value: min(int(round((voltage - 2.1), 2) * 100), 100),
                    ATTRS.VOLTAGE.value: str(voltage),
                    ATTRS.TEMPERATURE.value: str(int.from_bytes(data[0:2], byteorder="little", signed=True) / 100),
                    ATTRS.HUMIDITY.value: str(int.from_bytes(data[2:3], byteorder="little")),
                    ATTRS.TIMESTAMP.value: str(datetime.now().isoformat()),
                },
            }
        )

        peripheral.disconnect()

    # attach notification handler
    delegate = DefaultDelegate()
    delegate.handleNotification = handleNotification
    peripheral.setDelegate(delegate)

    # subscribe to notifications - seems not needed ¯\_(ツ)_/¯
    # peripheral.writeCharacteristic(0x38, bytes([0x01, 0x00]), withResponse=True)

    # safe power: https://github.com/JsBergbau/MiTemperature2/issues/18#issuecomment-590986874
    peripheral.writeCharacteristic(0x46, bytes([0xF4, 0x01, 0x00]), withResponse=True)

    if peripheral.waitForNotifications(10000):
        peripheral.disconnect()

    return plugin_data
