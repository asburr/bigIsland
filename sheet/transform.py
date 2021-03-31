from abc import ABC, abstractmethod
from typing import Iterable


class Transform(ABC):

    def __init__(self, cfg: dict):
        self.query = ""

    @staticmethod
    @abstractmethod
    def usage(self) -> dict:
        raise Exception("Abstract")

    @staticmethod
    @abstractmethod
    def name() -> str:
        raise Exception("Abstract")

    @abstractmethod
    def exec(self, params: dict, scratchPad: dict) -> Iterable[dict]:
        raise Exception("Abstract")
