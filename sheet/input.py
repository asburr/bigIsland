from abc import ABC, abstractmethod
from typing import Iterable


class Input(ABC):

    def __init__(self, cfg: dict):
        self.query = ""

    @staticmethod
    @abstractmethod
    def usage(self) -> dict:
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

    def _translate_params(self, params: dict) -> dict:
        d = {}
        paramFields = self.usage()["params"]
        transFields = self.usage()["map"]
        for field in params.keys():
            if not params[field]:
                continue
            if field in paramFields:
                if field in transFields:
                    d[transFields[field]] = params[field]
        return d

    def _build_query(self, translated_params: dict) -> str:
        filt = ""
        for field in translated_params:
            if filt:
                filt += " and "
            filt += field + "=\"" + translated_params[field] + "\""
        if filt:
            self.query += filt
        return filt

    def _get_param(self, params: dict, field: str) -> str:
        v = params[field]
        del params[field]
        if self.query:
            self.query += "and "
        self.query += field + "=" + v
        return v

    @staticmethod
    @abstractmethod
    def name() -> str:
        raise Exception("Abstract")

    @abstractmethod
    def exec(self, params: dict, scratchPad: dict) -> Iterable[dict]:
        raise Exception("Abstract")