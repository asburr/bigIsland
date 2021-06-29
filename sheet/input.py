# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This file is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# See the GNU General Public License, <https://www.gnu.org/licenses/>.
from abc import ABC, abstractmethod
from sheet.ci import Result
import pandas as pd


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
        return error

    @staticmethod
    @abstractmethod
    def name() -> str:
        raise Exception("Abstract")

    @abstractmethod
    def constraints(self, result: Result) -> str:
        raise Exception("Abstract")
        
    @abstractmethod
    def exec(self, result: Result, params: dict) -> pd.DataFrame:
        raise Exception("Abstract")