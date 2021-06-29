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


class Parser(ABC):
    @abstractmethod
    def toJSON(self, file: str) -> any:
        raise Exception("Abstract")

    @abstractmethod
    def parse(self, file: str) -> list:
        raise Exception("Abstract")
    
