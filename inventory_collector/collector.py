#!/usr/bin/env python3
"""Entrypoint and main logic implementation."""
import argparse
import datetime
import json
import os
import sys
import tarfile

import requests
import yaml
from juju import jasyncio
from juju.errors import JujuAPIError, JujuError
from juju.model import Controller

from inventory_collector import Config, ConfigError, ConfigMissingKeyError

ENDPOINTS = ["dpkg", "snap", "kernel"]


def parse_config(config_path: str) -> Config:
    """Load and parse application config file.

    :param config_path: Path to the application config
    :return: `Config` object holding application configuration
    """
    try:
        with open(config_path, "r", encoding="UTF-8") as conf_file:
            config_data = yaml.safe_load(conf_file)
            config = Config.from_dict(config_data)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse config file: {exc}") from exc
    except IOError as exc:
        raise ConfigError(f"Failed to read config file '{config_path}'") from exc
    except ConfigMissingKeyError as exc:
        raise ConfigError(f"Config is missing required key '{exc.key_name}'") from exc

    return config


def create_tars(config: Config):
    """Pre-create all tar files that will hold collection results."""
    output_dir = config.settings.collection_path
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    for model in config.models:
        tar_name = (
            f"{config.settings.customer}_@_{config.settings.site}_@"
            f"_{model}_@_{timestamp}.tar"
        )
        tar_path = os.path.join(
            output_dir,
            tar_name,
        )
        with tarfile.open(tar_path, "w", encoding="UTF-8"):
            pass
        # tar_file = tarfile.open(tar_path, "w")
        # tar_file.close()


def collect(config: Config):
    """Query exporter endpoints and collect data."""
    output_dir = config.settings.collection_path
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    for target in config.targets:
        url = f"http://{target.endpoint}/"
        for endpoint in ENDPOINTS:
            try:
                content = requests.get(url + endpoint)
            except requests.ConnectionError:
                continue
            path = os.path.join(
                output_dir,
                f"{endpoint}_@_{target.hostname}_@_{timestamp}",
            )
            with open(path, "w", encoding="UTF-8") as file:
                file.write(content.text)
            tar_name = (
                f"{target.customer}_@_{target.site}_@_{target.model}_@_{timestamp}.tar"
            )
            tar_path = os.path.join(
                output_dir,
                tar_name,
            )
            with tarfile.open(tar_path, "a:", encoding="UTF-8") as tar_file:
                tar_file.add(path)
            os.remove(path)


async def get_controller(config: Config) -> Controller:
    controller = Controller()
    await controller.connect(
        endpoint=config.juju_controller.endpoint,
        username=config.juju_controller.username,
        password=config.juju_controller.password,
        cacert=config.juju_controller.ca_cert,
    )
    return controller


async def juju_data(config: Config, controller: Controller):
    """Query Juju controller and collect information about models."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    customer = config.settings.customer
    site = config.settings.site
    output_dir = config.settings.collection_path

    model_uuids = await controller.model_uuids()

    for model_name in model_uuids.keys():
        model = await controller.get_model(model_name)
        status = await model.get_status()
        try:
            bundle = await model.export_bundle()
        except JujuAPIError as exc:
            if str(exc) == "nothing to export as there are no applications":
                bundle = "{}"
            else:
                raise exc
        await model.disconnect()
        status_path = os.path.join(
            output_dir,
            f"juju_status_@_{model_name}_@_{timestamp}",
        )
        bundle_path = os.path.join(
            output_dir,
            f"juju_bundle_@_{model_name}_@_{timestamp}",
        )
        with open(status_path, "w", encoding="UTF-8") as file:
            file.write(status.to_json())
        tar_name = f"{customer}_@_{site}_@_{model_name}_@_{timestamp}.tar"
        tar_path = os.path.join(
            output_dir,
            tar_name,
        )
        with tarfile.open(tar_path, "a:", encoding="UTF-8") as tar_file:
            tar_file.add(status_path)
        os.remove(status_path)

        bundle_yaml = yaml.load_all(bundle, Loader=yaml.FullLoader)
        for data in bundle_yaml:
            bundle_json = json.dumps(data)
            # skip SAAS; multiple documents, we need to import only the bundle
            if "offers" in bundle_json:
                continue
            with open(bundle_path, "w", encoding="UTF-8") as file:
                file.write(bundle_json)
            tar_name = f"{customer}_@_{site}_@_{model_name}_@_{timestamp}.tar"
            tar_path = os.path.join(
                output_dir,
                tar_name,
            )
            with tarfile.open(tar_path, "a:", encoding="UTF-8") as tar_file:
                tar_file.add(bundle_path)
            os.remove(bundle_path)

    await controller.disconnect()


def main():
    """Run inventory collector."""
    arg_parser = argparse.ArgumentParser("Collect inventory data")
    arg_parser.add_argument(
        "-c",
        "--config",
        help="Configuration file path.",
        default="/var/snap/inventory-collector/current/config.yaml",
    )
    arg_parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=False,
        help="Verifies succesfull connection to the controller but no output "
             "is produced.",
    )
    args = arg_parser.parse_args()

    try:
        config = parse_config(args.config)
    except ConfigError as exc:
        print(f"Failed to load config: {exc}")
        sys.exit(1)

    try:
        controller: Controller = jasyncio.run(get_controller(config))
    except JujuError as exc:
        print(f"Failed to connect to juju controller: {exc}")
        sys.exit(1)

    if args.dry_run:
        jasyncio.run(controller.disconnect())
        print("OK.")
        sys.exit(0)

    create_tars(config)
    collect(config)
    jasyncio.run(juju_data(config, controller))


if __name__ == "__main__":
    main()
