# supported devices
#   Mijia LCD Temperature Humidity Sensor (LYWSD03MMC)

import logging

from datetime import datetime
from typing import Any, Dict, Union

from bluepy.btle import DefaultDelegate, Peripheral

from miblepy import ATTRS


SUPPORTED_ATTRS = [ATTRS.BATTERY, ATTRS.VOLTAGE, ATTRS.TEMPERATURE, ATTRS.HUMIDITY, ATTRS.TIMESTAMP]


def fetch_data(mac: str, interface: str, **kwargs: Any) -> Dict[str, Any]:
    """Get data from one Sensor."""

    sensor_data: Dict[str, Union[str, int, float]] = {}

    peripheral = connect(mac, interface, sensor_data)

    if peripheral.waitForNotifications(2000):
        peripheral.disconnect()

    return sensor_data


class MiblepyDelegate(DefaultDelegate):

    def __init__(self, sensor_data: Dict[str, Union[str, int, float]]):
        DefaultDelegate.__init__(self)
        self.sensor_data: Dict[str, Union[str, int, float]] = sensor_data

    def handleNotification(self, cHandle: int, data: bytes) -> None:
        # global sensor_data

        if cHandle == 54:

            try:
                voltage = int.from_bytes(data[3:5], byteorder="little") / 1000.0
                self.sensor_data.update(
                    {
                        # 3.1 or above --> 100% 2.1 --> 0 %
                        ATTRS.BATTERY.value: min(int(round((voltage - 2.1), 2) * 100), 100),
                        ATTRS.VOLTAGE.value: str(voltage),
                        ATTRS.TEMPERATURE.value: str(int.from_bytes(data[0:2], byteorder="little", signed=True) / 100),
                        ATTRS.HUMIDITY.value: str(int.from_bytes(data[2:3], byteorder="little")),
                        ATTRS.TIMESTAMP.value: str(datetime.now().isoformat()),
                    }
                )

            except (TypeError, ValueError) as error:
                logging.error(f"parsing sensor data failed: {error}")
                logging.error(f"sensor data: {data!r}")


def connect(mac: str, interface: str, sensor_data: Dict[str, Any]) -> Peripheral:
    """Connect to device and activate notifications."""
    interface_idx: int = int(interface.replace("hci", ""))

    peripheral = Peripheral(mac, iface=interface_idx)

    # enable temperature, humidity and battery voltage notifications
    peripheral.writeCharacteristic(0x38, bytes([0x01, 0x00]), True)
    peripheral.writeCharacteristic(0x46, bytes([0xF4, 0x01, 0x00]), True)

    # register handler
    peripheral.withDelegate(MiblepyDelegate(sensor_data))

    return peripheral
