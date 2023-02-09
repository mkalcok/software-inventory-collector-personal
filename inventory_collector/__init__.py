"""Implementation for client collecting inventory data.

Intended to work with https://github.com/dparv/charm-inventory-exporter
"""
from .config import Config
from .exception import ConfigError, ConfigMissingKeyError
