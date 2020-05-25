# miblepy

<!-- 
[![PyPI - Downloads](https://img.shields.io/pypi/dm/miblepy)](https://pypi.org/project/miblepy/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/miblepy)](https://pypi.org/project/miblepy/)
[![PyPI](https://img.shields.io/pypi/v/miblepy)](https://pypi.org/project/miblepy/)

[![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/benleb/miblepy?sort=date)](https://hub.docker.com/r/benleb/miblepy)
[![Docker Automated build](https://img.shields.io/docker/automated/benleb/miblepy)](https://hub.docker.com/r/benleb/miblepy)
[![Docker Build Status](https://img.shields.io/docker/build/benleb/miblepy)](https://hub.docker.com/r/benleb/miblepy)
[![Docker Pulls](https://img.shields.io/docker/pulls/benleb/miblepy)](https://hub.docker.com/r/benleb/miblepy)

[![DeepSource](https://static.deepsource.io/deepsource-badge-light-mini.svg)](https://deepsource.io/gh/benleb/miblepy/?ref=repository-badge) -->

**miblepy** fetches data from various (Xiaomi/Mijia/Mi) Bluetooth LE devices and push it to a MQTT broker. For every device supported, there are already libraries or anything else to fetch the data from - and they work perfectly. But as they are separated and often run as distinct (cron)jobs, which are not aware of each other, or even as daemons... the fight for the BLE interface starts...  

**miblepy** solves this by acting as a "coordinator" to fetch the data in a controlled, sequential way.

Currently this is a private project tailored to my needs - but open for PRs

## Usage

**miblepy** is available as [pip](#via-pip) package and [Docker image](#docker).

### Install

#### via pip

```bash
pip install miblepy
```

#### manual

* clone this repo & cd to it  

  ```bash
  git clone https://github.com/benleb/miblepy.git && cd miblepy
  ```

* install via
  * poetry

    ```bash
    poetry install
    ```

  * pip

    ```bash
    pip install .
    ```

### Configuration

Copy `mible.toml` to `~/.mible.toml` and adjust settings to your needs. `~/.mible.toml` is the default location where `mible` expects your configuration. You can change this via `--config`.

### Run

Start a single round of fetching from your configured sensors in `~/.mible.toml`

```bash
mible fetch
```

try `mible --help` to get more info.

To continously fetch data from your sensors check out the systemd [timer](https://github.com/benleb/miblepy/blob/master/miblepy.timer) and [service](https://github.com/benleb/miblepy/blob/master/miblepy.service). You can also use a classic cronjob or even an automation provided by your smart home system (home assistant for example)

### Docker

The `:latest` tag is built from master, other tags can be found on [Docker Hub](https://hub.docker.com/r/benleb/miblepy)

Mount your miblepy config to `/miblepy/mible.toml`

```bash
docker run --privileged --volume "mible.toml:/miblepy/mible.toml:ro" benleb/miblepy
```

## Supported devices

* VegTrug / Mi Flora plant sensors (Flower Care)
* (Xiaomi?) Mijia Bluetooth Temperature Humidity sensors with LCD (LYWSD03MMC)
* (Xiaomi?) Mi Body Composition Scale 2 (XMTZC05HM / XMTZC02HM)

## Support a new device

* **TODO**

Check the already available plugins to see some examples.

## Thanks to

* [@ChristianKuehnel](https://github.com/ChristianKuehnel) | [plantgw](https://github.com/ChristianKuehnel/plantgateway)
miblepy's idea is based on his plantgw project
* [@open-homeautomation](https://github.com/open-homeautomation) | [miflora](https://github.com/open-homeautomation/miflora)
Library to interact with FlowerCare/MiFlora devices
* [@JsBergbau](https://github.com/JsBergbau) | [MiTemperature2](https://github.com/JsBergbau/MiTemperature2)
Library to interact with Mi Bluetooth LCD Thermometers
* [@lolouk44](https://github.com/lolouk44) | [xiaomi_mi_scale](https://github.com/lolouk44/xiaomi_mi_scale)
Library to interact with Mi Body Composition Scale 2
