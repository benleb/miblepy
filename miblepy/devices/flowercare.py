
# supported devices
#   VegTrug Plant Sensor (???)
#   Mi Flora? (???)

from datetime import datetime
from typing import Any, Dict

from btlewrap.bluepy import BluepyBackend
from miflora.miflora_poller import MiFloraPoller

from miblepy import ATTRS, MI_BATTERY, MI_CONDUCTIVITY, MI_LIGHT, MI_MOISTURE, MI_TEMPERATURE


SUPPORTED_ATTRS = [ATTRS.BRIGHTNESS, ATTRS.BATTERY, ATTRS.TEMPERATURE, ATTRS.MOISTURE, ATTRS.CONDUCTIVITY, ATTRS.TIMESTAMP]


def fetch_data(mac: str, interface: str, **kwargs) -> Dict[str, Any]:
    """Get data from one Sensor."""

    poller = MiFloraPoller(mac, BluepyBackend, adapter=interface, retries=1)

    data = {
        ATTRS.BATTERY.value: poller.parameter_value(MI_BATTERY),
        ATTRS.TEMPERATURE.value: "{0:.1f}".format(poller.parameter_value(MI_TEMPERATURE)),
        ATTRS.BRIGHTNESS.value: poller.parameter_value(MI_LIGHT),
        ATTRS.MOISTURE.value: poller.parameter_value(MI_MOISTURE),
        ATTRS.CONDUCTIVITY.value: poller.parameter_value(MI_CONDUCTIVITY),
        ATTRS.TIMESTAMP.value: datetime.now().isoformat(),
    }

    return data
