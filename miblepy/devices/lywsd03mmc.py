from datetime import datetime
from typing import Any, Dict

from bluepy.btle import DefaultDelegate, Peripheral
from miblepy import ATTRS
from miblepy.deviceplugin import MibleDevicePlugin


class LYWSD03MMC(MibleDevicePlugin, DefaultDelegate):

    plugin_id = "lywsd03mmc"
    plugin_name = "LYWSD03MMC"
    plugin_description = "suports the Temperature/Humidity LCD BLE sensor LYWSD03MMC from Mi/Xiaomi"

    def __init__(self, mac: str, interface: str, **kwargs: Any):
        self.peripheral: Peripheral = None
        self.data: Dict[str, Any] = {}

        super().__init__(mac, interface, **kwargs)

    def fetch_data(self, **kwargs: Any) -> Dict[str, Any]:
        # connect to device
        self.peripheral = Peripheral(self.mac, iface=int(self.interface.replace("hci", "")))

        # attach notification handler
        self.peripheral.setDelegate(self)

        # safe power: https://github.com/JsBergbau/MiTemperature2/issues/18#issuecomment-590986874
        self.peripheral.writeCharacteristic(0x46, bytes([0xF4, 0x01, 0x00]), withResponse=True)

        if self.peripheral.waitForNotifications(10000):
            self.peripheral.disconnect()

        return self.data

    def handleNotification(self, cHandle: int, data: bytes) -> None:
        if cHandle != 0x36:
            return

        # parse data
        voltage = int.from_bytes(data[3:5], byteorder="little") / 1000

        self.data.update(
            {
                "name": self.plugin_name,
                "sensors": [
                    {
                        "name": f"{self.alias} {ATTRS.TEMPERATURE.value.capitalize()}",
                        "value_template": "{{value_json." + ATTRS.TEMPERATURE.value + "}}",
                        "entity_type": ATTRS.TEMPERATURE,
                    },
                    {
                        "name": f"{self.alias} {ATTRS.HUMIDITY.value.capitalize()}",
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

        self.peripheral.disconnect()
