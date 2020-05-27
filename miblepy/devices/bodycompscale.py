# supported devices
#   Mi Body Composition Scale 2 (XMTZC05HM)

import logging

from datetime import date, datetime
from struct import unpack
from typing import Any, Dict, List, Union

import miblepy.devices.xbm as xbm

from bluepy.btle import BTLEDisconnectError, BTLEManagementError, DefaultDelegate, ScanEntry, Scanner
from miblepy import ATTRS
from miblepy.deviceplugin import MibleDevicePlugin


PLUGIN_NAME = "BodyCompScale"

SCAN_TIMEOUT = 10
UNITS = {2: "kg", 3: "lbs"}
DATA_KEYS = (
    "unit_id",
    "control",
    "year",
    "month",
    "day",
    "hour",
    "min",
    "sec",
    "impedance",
    "weight",
)


class BodyCompScale(MibleDevicePlugin, DefaultDelegate):

    plugin_id = "bodycompscale"
    plugin_name = "BodyCompScale"
    plugin_description = "suports the Mi Body Composition Scale 2 (XMTZC05HM) / Xiaomi Scale 2 (XMTZC02HM)"

    def __init__(self, mac: str, interface: str, **kwargs: Any):
        self.users: List[Dict[str, Union[str, int, float, date]]] = kwargs.get("users", [])
        self.scanner: Scanner = None
        self.data: Dict[str, Any] = {}

        super().__init__(mac, interface, **kwargs)

    def fetch_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Get data from device."""

        # attach notification handler
        self.scanner = Scanner(iface=int(self.interface.replace("hci", ""))).withDelegate(self)

        try:
            self.scanner.scan(SCAN_TIMEOUT)
        except BTLEDisconnectError as error:
            logging.error(f"btle disconnected: {error}")
        except BTLEManagementError as error:
            logging.error(f"(temporary) bluetooth connection error: {error}")

        return self.data

    def get_age(self, birthdate: Any) -> int:
        today = date.today()
        return int(today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day)))

    def find_user(self, weight: float) -> Dict[str, Any]:

        current_user: Dict[str, Any] = {}

        # determine current user by weight
        for user in self.users:

            if not all([user["weightOver"], user["weightBelow"]]):
                continue

            if user["weightOver"] < weight < user["weightBelow"]:  # type: ignore
                # current user found, fill profile values and exit
                current_user = user
                current_user[ATTRS.WEIGHT.value] = weight
                current_user[ATTRS.AGE.value] = self.get_age(current_user["birthdate"])
                break

        return current_user

    def handleDiscovery(self, dev: ScanEntry, new_dev: bool, new_data: bool) -> None:

        if not dev.addr == self.mac.lower() or not new_dev or not new_data:
            return

        for (sdid, _, data) in dev.getScanData():

            # Mi Body Composition Scale 2 (XMTZC05HM) / Xiaomi Scale 2 (XMTZC02HM)
            if not data.startswith("1b18") or sdid != 22:
                continue

            # 15b in little endian
            #   0-1: identifier?
            #     2: unit
            #     3: control byte
            #   4-5: year
            #     6: month
            #     7: day
            #     8: hour
            #     9: min
            #     10: sec
            #  11-12: impedance
            #  13-14: weight

            # unpack bytes to dictionary
            measured = dict(zip(DATA_KEYS, unpack("<xxBBHBBBBBHH", bytes.fromhex(data))))

            # check if we got a proper measurement
            measurement_stabilized = measured["control"] & (1 << 5)
            impedance_available = measured["control"] & (1 << 1)

            # pick unit
            unit = UNITS.get(measured["unit_id"], None)
            # calc weight based on unit
            weight = measured["weight"] / 100 / 2 if measured["unit_id"] == 2 else measured["weight"] / 100

            # check if we got a proper measurement
            if not all([measurement_stabilized, unit]):
                logging.debug(f"missing data! weight: {weight} | unit: {unit} | impedance: {measured['impedance']}")
                continue

            # create datetime
            measurement_datetime = datetime(
                measured["year"], measured["month"], measured["day"], measured["hour"], measured["min"], measured["sec"]
            )

            # find the current user based on its weight
            if user := self.find_user(weight):

                bm = xbm.BodyMetrics(
                    user[ATTRS.WEIGHT.value],
                    user[ATTRS.HEIGHT.value],
                    user[ATTRS.AGE.value],
                    user[ATTRS.SEX.value],
                    measured["impedance"],
                )

                attributes = {
                    ATTRS.USER.value: user[ATTRS.USER.value],
                    ATTRS.AGE.value: user[ATTRS.AGE.value],
                    ATTRS.SEX.value: user[ATTRS.SEX.value],
                    ATTRS.HEIGHT.value: user[ATTRS.HEIGHT.value],
                    ATTRS.WEIGHT.value: f"{weight:.2f}",
                    ATTRS.UNIT.value: unit,
                    ATTRS.BASAL_METABOLISM.value: f"{bm.get_bmr():.2f}",
                    ATTRS.VISCERAL_FAT.value: f"{bm.getVisceralFat():.2f}",
                    ATTRS.BMI.value: f"{bm.getBMI():.2f}",
                    ATTRS.TIMESTAMP.value: measurement_datetime.isoformat(),
                }

                # if we got a valid impedance, we can add more metrics
                if impedance_available:
                    attributes.update(
                        {
                            ATTRS.WATER.value: f"{bm.getWaterPercentage():.2f}",
                            ATTRS.BONE_MASS.value: f"{bm.getBoneMass():.2f}",
                            ATTRS.BODY_FAT.value: f"{bm.getFatPercentage():.2f}",
                            ATTRS.LEAN_BODY_MASS.value: f"{bm.get_lbm_coefficient():.2f}",
                            ATTRS.MUSCLE_MASS.value: f"{bm.getMuscleMass():.2f}",
                            ATTRS.PROTEIN.value: f"{bm.getProteinPercentage():.2f}",
                        }
                    )

                self.data.update(
                    {
                        "name": PLUGIN_NAME,
                        "sensors": [
                            {
                                "name": f"{self.alias} {user[ATTRS.USER.value]}",
                                "value_template": "{{value_json." + ATTRS.WEIGHT.value + "}}",
                                "entity_type": ATTRS.WEIGHT,
                                "own_state_topic": True,
                            },
                        ],
                        "attributes": attributes,
                    }
                )
