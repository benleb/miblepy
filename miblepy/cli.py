#!/usr/bin/env python3

import click

from miblepy import CONFIG_FILE, MAX_RETRIES, Miblepy, __name__ as mbp_name, __version__ as mbp_version, hl


CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.pass_context
@click.option("--version", default=False, is_flag=True, help=f"show {mbp_name} version")
@click.option("-d", "--debug", default=False, is_flag=True, help="enable debug output")
def cli(ctx: click.Context, version: bool, debug: bool) -> None:
    """fetch data from ble sensors and push it to a mqtt broker

      https://github.com/benleb/miblepy
    """

    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    if not ctx.invoked_subcommand:

        if version:
            click.echo(f"{mbp_name} {hl(mbp_version)} | https://github.com/benleb/miblepy | @benleb")
            exit(0)

        click.echo(ctx.get_help())


@cli.command()
@click.pass_context
@click.option(
    "-c", "--config", default=CONFIG_FILE, type=click.Path(file_okay=True), required=False, help="path to config file",
)
@click.option(
    "-r", "--retries", default=MAX_RETRIES, type=int, help="times we try to get data from a sensor",
)
def fetch(ctx: click.Context, config: str, retries: int) -> None:
    Miblepy(config_file_path=config, retries=retries, debug=ctx.obj["debug"]).go()


if __name__ == "__main__":
    cli(obj={})
