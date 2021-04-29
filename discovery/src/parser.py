#!/usr/bin/env python3
from abc import ABC, abstractmethod


class Parser(ABC):
    @abstractmethod
    def toJSON(self, file: str) -> any:
        raise Exception("Abstract")

    @abstractmethod
    def parse(self, file: str) -> list:
        raise Exception("Abstract")
    
