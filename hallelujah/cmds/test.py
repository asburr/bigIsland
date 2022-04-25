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
from cmd import Cmd


class Test(Cmd):
    """
 Test: Just returns helloworld for each execution.
    """
    def __init__(self, cmd: dict):
        super().__init__()
        self.data = []

    def execute(self) -> None:
        self.data.append("hello world")

    def data(self, feedName: str, n:int) -> list:
        retval = self.data
        self.data = []
        return retval