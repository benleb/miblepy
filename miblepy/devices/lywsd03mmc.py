
# supported devices
#   Mijia LCD Temperature Humidity Sensor (LYWSD03MMC)

import logging

from datetime import datetime
from typing import Any, Dict

from bluepy import btle

from miblepy import ATTRS


SUPPORTED_ATTRS = [ATTRS.VOLTAGE, ATTRS.TEMPERATURE, ATTRS.HUMIDITY, ATTRS.TIMESTAMP]


def fetch_data(mac: str, topic: str, interface: str, backend: Any = None) -> Dict[str, Any]:
    """Get data from one Sensor."""

    sensor_data = {}

    try:
        peripheral = connect(mac, interface, sensor_data)

        if peripheral.waitForNotifications(2000):
            peripheral.disconnect()
    except btle.BTLEDisconnectError as error:
        logging.error(f"btle disconnected: {error}")
    except Exception as error:
        logging.exception(f"error when trying to fetch data from {mac}: {error}")

    return sensor_data


class MiblepyDelegate(btle.DefaultDelegate):

    def __init__(self, sensor_data):
        self.sensor_data: Dict[str, Any] = sensor_data
        btle.DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle: int, data: bytes):
        # global sensor_data

        if cHandle == 54:

            try:
                self.sensor_data.update({
                    ATTRS.VOLTAGE.value: str(int.from_bytes(data[3:5], byteorder="little") / 1000.0),
                    ATTRS.TEMPERATURE.value: str(int.from_bytes(data[0:2], byteorder="little", signed=True) / 100),
                    ATTRS.HUMIDITY.value: str(int.from_bytes(data[2:3], byteorder="little")),
                    ATTRS.TIMESTAMP.value: str(datetime.now().isoformat()),
                })

            except (TypeError, ValueError) as error:
                logging.error(f"parsing sensor data failed: {error}")
                logging.error(f"sensor data: {data}")


def connect(mac: str, interface: str, sensor_data: Dict[str, Any]):
    """Connect to device and activate notifications."""
    interface_idx: int = int(interface.replace("hci", ""))

    peripheral = btle.Peripheral(mac, iface=interface_idx)

    # enable temperature, humidity and battery voltage notifications
    peripheral.writeCharacteristic(0x38, bytes([0x01, 0x00]), True)
    peripheral.writeCharacteristic(0x46, bytes([0xf4, 0x01, 0x00]), True)

    # register handler
    peripheral.withDelegate(MiblepyDelegate(sensor_data))

    return peripheral
