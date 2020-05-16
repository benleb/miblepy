
# supported devices
#   Mijia LCD Temperature Humidity Sensor (LYWSD03MMC)

import logging

from datetime import datetime
from pprint import pformat
from typing import Any, Dict

from bluepy import btle

from .. import ATTRS


sensor_data = {}

SUPPORTED_ATTRS = [ATTRS.VOLTAGE, ATTRS.TEMPERATURE, ATTRS.HUMIDITY, ATTRS.TIMESTAMP]


def fetch_data(mac: str, topic: str, interface: str, backend: Any = None) -> Dict[str, Any]:
    """Get data from one Sensor."""

    data = None

    try:
        peripheral = connect(mac, interface)

        if peripheral.waitForNotifications(2000):
            peripheral.disconnect()
            data = sensor_data
    except btle.BTLEDisconnectError as error:
        logging.error(f"btle disconnected: {error}")
    finally:
        return data


class MiblepyDelegate(btle.DefaultDelegate):

    def __init__(self):
        btle.DefaultDelegate.__init__(self)

    def handleNotification(self, cHandle, data):
        global sensor_data

        data: bytes

        if cHandle == 54:

            # logging.info(f"{hex(data) = }")
            # logging.info(f"{cHandle = }")
            # logging.info(f"{sensor_data = }")

            try:
                sensor_data = {
                    ATTRS.VOLTAGE.value: str(int.from_bytes(data[3:5], byteorder="little") / 1000.0),
                    ATTRS.TEMPERATURE.value: str(int.from_bytes(data[0:2], byteorder="little", signed=True) / 100),
                    ATTRS.HUMIDITY.value: str(int.from_bytes(data[2:3], byteorder="little")),
                    ATTRS.TIMESTAMP.value: str(datetime.now().isoformat()),
                }

                logging.info(f"{data.hex(':') = }")
                logging.info(f"{data.hex(':').split(':') = }")
                logging.info(f"{str(int.from_bytes(data[0:2], byteorder='little', signed=True)) = }")
                logging.info(f"{str(int.from_bytes(data[2:3], byteorder='little')) = }")
                # logging.info(f"{[int.from_bytes(xx, byteorder='little') for xx in data.hex(':').split(':')] = }")

            except Exception as error:
                logging.error(f"parsing sensor data failed: {error}")
                logging.error(f"sensor data: {data}")


def connect(mac: str, interface: str):
    """Code """
    interface_idx: int = int(interface.replace("hci", ""))

    peripheral = btle.Peripheral(mac, iface=interface_idx)

    # enable temperature, humidity and battery voltage notifications
    peripheral.writeCharacteristic(0x38, bytes([0x01, 0x00]), True)
    peripheral.writeCharacteristic(0x46, bytes([0xf4, 0x01, 0x00]), True)

    # register handler
    peripheral.withDelegate(MiblepyDelegate())

    return peripheral
