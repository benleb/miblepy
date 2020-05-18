#!/usr/bin/env python3

import click

from miblepy import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_MAX_RETRIES,
    Miblepy,
    __name__ as miblepy_name,
    __version__ as miblepy_version,
    hl,
)


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.command(context_settings=CONTEXT_SETTINGS)
@click.option(
    "-c",
    "--config",
    default=DEFAULT_CONFIG_FILE,
    type=click.Path(file_okay=True),
    required=False,
    help="path to config file",
)
@click.option(
    "-r",
    "--retries",
    default=DEFAULT_MAX_RETRIES,
    type=click.IntRange(0, 10, clamp=True),
    help="times we try to get data from a sensor",
)
@click.option("--version", default=False, is_flag=True, help=f"show {miblepy_name} version")
@click.option("-d", "--debug", default=False, is_flag=True, help="enable debug output")
def cli(config: str, retries: int, version: bool, debug: bool) -> None:
    """fetch data from ble sensors and push it to a mqtt broker

      https://github.com/benleb/miblepy
    """

    if version:
        click.echo(f"{miblepy_name} {hl(miblepy_version)} | https://github.com/benleb/miblepy | @benleb")
        exit(0)

    Miblepy(config_file_path=config, retries=retries, debug=debug).go()


if __name__ == "__main__":
    cli()
