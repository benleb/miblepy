# miblepy

**miblepy** fetches data from various (Xiaomi/Mijia/Mi) Bluetooth LE devices and push it to a MQTT broker. For every device supported, there are already libraries or anything else to fetch the data from - and they work perfectly! But as they are separated and often run as distinct (cron)jobs, which are not aware of each other, the fight for the BLE interface starts...  
**miblepy** solves this by acting as a coordinator/wrapper for all these separate libs. It utilizes them to actually fetch the data in a coordinated, sequential manner.  

Currently this is a private project tailored to my needs - but open for PRs :)

## Usage

As this is just a private project, there is not much documentation - besides the code itself ;)

* clone this repo & cd to it `git clone https://github.com/benleb/miblepy.git && cd miblepy`
* copy `miblepy.toml` to `~/.miblepy.toml` and adjust settings
* install requirements via
  * poetry: `poetry install`
  * pip: `pip install --upgrade .`
* run `miblepy` to start fetching from configured sensors

---

To continously fetch data from sensors you can choose...

* a systemd service/timer: TODO
* a cronjob
* an automation provided by your smart home system (home assistant for example)

## Supported devices

* VegTrug / Mi Flora plant sensors (Flower Care)
* (Xiaomi?) Mijia Bluetooth Temperature Humidity sensors with LCD (LYWSD03MMC)
* ~~Xiaomi Mi Body Composition Scale 2 (XMTZC05HM)~~ WIP

## Support a new device

To support a new device is very easy! Just a single python file should be placed in the `devices/` folder which:

* has a `SUPPORTED_ATTRS` variable containing all supported attributes (see `miblepy/__init__.py` for available `ATTRS`).
* a function with this signature, called by miblepy for each device  

```python
def fetch_data(mac: str, interface: str) -> Dict[str, Any]
```

Check the already available plugins to see some examples.

## Thanks to

* [@ChristianKuehnel](https://github.com/ChristianKuehnel) | [plantgw](https://github.com/ChristianKuehnel/plantgateway)  
miblepy's idea is based on his plantgw project

---

* [@open-homeautomation](https://github.com/open-homeautomation) | [miflora](https://github.com/open-homeautomation/miflora)  
Library to interact with FlowerCare/MiFlora devices
* [@JsBergbau](https://github.com/JsBergbau) | [MiTemperature2](https://github.com/JsBergbau/MiTemperature2)  
Library to interact with Mi Bluetooth LCD Thermometers
* [@lolouk44](https://github.com/lolouk44) | [xiaomi_mi_scale](https://github.com/lolouk44/xiaomi_mi_scale)  
Library to interact with Mi Body Composition Scale 2
