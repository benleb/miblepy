from abc import ABC, abstractmethod
from typing import Any, Dict


class MibleDevicePlugin(ABC):
    def __init__(self, mac: str, interface: str, **kwargs: Any):
        self.mac = mac
        self.interface = interface

        if alias := kwargs.get("alias"):
            self.alias = alias
        else:
            self.alias = mac

        super().__init__()

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def plugin_description(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch_data(self, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError
