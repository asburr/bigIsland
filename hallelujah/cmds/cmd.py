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
#
from abc import ABC, abstractmethod


class Cmd(ABC):
    @abstractmethod
    def schema(self) -> list:
        raise Exception("Not implemented")

    @abstractmethod
    def sample(self, feedName: str, n:int) -> (bool, dict):
        raise Exception("Not implemented")

    @abstractmethod
    def execute(self) -> None:
        raise Exception("Not implemented")