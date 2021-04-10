from abc import ABC, abstractmethod
from typing import Iterable


class Input(ABC):

    def __init__(self, cfg: dict):
        self.query = ""

    @staticmethod
    @abstractmethod
    def usage() -> dict:
        raise Exception("Abstract")

    @staticmethod
    def checkUsage(usage: dict) -> str:
        error = ""
        for key in usage["required"]:
            if key not in usage["params"]:
                error += "ERROR " + key + " is required but not in params\n"
        for key in usage["defaults"].keys():
            if key not in usage["params"]:
                error += "ERROR " + key + " has a default but not in params\n"
        for key, val in usage["map"].items():
            if val not in usage["return"]:
                error += "ERROR " + val + " is mapped but not in return\n"
        return error

    @staticmethod
    @abstractmethod
    def name() -> str:
        raise Exception("Abstract")

    @staticmethod
    @abstractmethod
    def exec(params: dict, scratchPad: dict) -> Iterable[dict]:
        raise Exception("Abstract")