"""Module containing exceptions used by inventory-collector."""


class ConfigError(Exception):
    """Error occurred when reading config file."""


class ConfigMissingKeyError(ConfigError):
    """Config file is missing a required key"""

    def __init__(self, key_name: str) -> None:
        """Initiate exception instance."""
        super().__init__()
        self.key_name = key_name
