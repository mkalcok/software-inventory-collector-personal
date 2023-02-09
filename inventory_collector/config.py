"""Module containing inventory-exporter configuration classes."""
from dataclasses import dataclass
from typing import Dict, List

from inventory_collector.exception import ConfigMissingKeyError


@dataclass
class _ConfigSettings:
    """Definition for 'settings' subsection of main config."""
    collection_path: str
    juju_data: str
    customer: str
    site: str

    @classmethod
    def from_dict(cls, source: Dict) -> '_ConfigSettings':
        """Factory method that creates object from raw dict data.

        :param source: Data from 'settings' subsection of main config.
        :return: Initiated instance of this class.
        """
        try:
            collection_path = source["collection_path"]
            juju_data = source["juju_data"]
            customer = source["customer"]
            site = source["site"]
        except KeyError as exc:
            raise ConfigMissingKeyError(f"settings.{exc.args[0]}") from exc
        return cls(
            collection_path=collection_path,
            juju_data=juju_data,
            customer=customer,
            site=site,
        )


@dataclass
class _ConfigTarget:
    """Definition for 'target' subsection of main config."""
    endpoint: str
    hostname: str
    customer: str
    site: str
    model: str

    @classmethod
    def from_dict(cls, source: Dict) -> '_ConfigTarget':
        """Factory method that creates object from raw dict data.

        :param source: Data from 'target' subsection of main config.
        :return: Initiated instance of this class.
        """
        try:
            endpoint = source["endpoint"]
            hostname = source["hostname"]
            customer = source["customer"]
            site = source["site"]
            model = source["model"]
        except KeyError as exc:
            raise ConfigMissingKeyError(f"target.{exc.args[0]}") from exc
        return cls(
            endpoint=endpoint,
            hostname=hostname,
            customer=customer,
            site=site,
            model=model,
        )


@dataclass
class Config:
    """Object representation of a complete config file."""
    settings: _ConfigSettings
    models: List[str]
    targets: List[_ConfigTarget]

    @classmethod
    def from_dict(cls, source: Dict) -> 'Config':
        """Factory method that takes a raw dictionary data from yaml config.

        :param source: Dictionary data loaded from confi file.
        :return: Initiated instance of this class, representing complete configuration.
        """
        try:
            settings = _ConfigSettings.from_dict(source["settings"])
            models = source["models"]
            targets = [_ConfigTarget.from_dict(target) for target in source["targets"]]
        except KeyError as exc:
            raise ConfigMissingKeyError(f"{exc.args[0]}") from exc
        except ConfigMissingKeyError as exc:
            raise ConfigMissingKeyError(f"{exc.key_name}") from exc
        return cls(settings=settings, models=models, targets=targets)
