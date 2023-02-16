"""Implementation of collector functions from various data sources."""
import datetime
import json
import os
import tarfile
from tempfile import TemporaryFile

import requests
import yaml
from juju.errors import JujuAPIError
from juju.controller import Controller

from inventory_collector import Config
from inventory_collector.exception import CollectionError

ENDPOINTS = ["dpkg", "snap", "kernel"]

TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d%H%M%S")


def get_exporter_data(config: Config) -> None:
    """Query exporter endpoints and collect data."""
    output_dir = config.settings.collection_path
    for target in config.targets:
        url = f"http://{target.endpoint}/"
        for endpoint in ENDPOINTS:
            try:
                content = requests.get(url + endpoint)
                content.raise_for_status()
            except requests.exceptions.RequestException as exc:
                raise CollectionError(f"Failed to collect data from target '{target.endpoint}': f{exc}")

            path = os.path.join(
                output_dir,
                f"{endpoint}_@_{target.hostname}_@_{TIMESTAMP}",
            )
            with open(path, "w", encoding="UTF-8") as file:
                file.write(content.text)
            tar_name = (
                f"{target.customer}_@_{target.site}_@_{target.model}_@_{TIMESTAMP}.tar"
            )
            tar_path = os.path.join(
                output_dir,
                tar_name,
            )
            with tarfile.open(tar_path, "a:", encoding="UTF-8") as tar_file:
                tar_file.add(path)
            os.remove(path)


async def get_controller(config: Config) -> Controller:
    """Return connected instance of Juju Controller."""
    controller = Controller()
    await controller.connect(
        endpoint=config.juju_controller.endpoint,
        username=config.juju_controller.username,
        password=config.juju_controller.password,
        cacert=config.juju_controller.ca_cert,
    )
    return controller


async def get_juju_data(config: Config, controller: Controller):
    """Query Juju controller and collect information about models."""
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
            f"juju_status_@_{model_name}_@_{TIMESTAMP}",
        )
        bundle_path = os.path.join(
            output_dir,
            f"juju_bundle_@_{model_name}_@_{TIMESTAMP}",
        )
        with open(status_path, "w", encoding="UTF-8") as file:
            file.write(status.to_json())
        tar_name = f"{customer}_@_{site}_@_{model_name}_@_{TIMESTAMP}.tar"
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
            tar_name = f"{customer}_@_{site}_@_{model_name}_@_{TIMESTAMP}.tar"
            tar_path = os.path.join(
                output_dir,
                tar_name,
            )
            with tarfile.open(tar_path, "a:", encoding="UTF-8") as tar_file:
                tar_file.add(bundle_path)
            os.remove(bundle_path)

    await controller.disconnect()
