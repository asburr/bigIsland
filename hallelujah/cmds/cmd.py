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
from magpie.src.musage import MUsage
from discovery.src.discovery import SchemaDiscovery

class Cmd(ABC):

    # Cmd ages off the schema after a week (168 hours).
    def __init__(self):
        self.disco = SchemaDiscovery(ageoff_hour_limit=168)
        self.testReceiver = None

    # The schema is created by self.disco, and is a description
    # of the structure of the inputted data as seen so far by this command.
    # self.execute() must load inputted data into self.disco.load().
    def schema(self) -> any:
        return self.disco.r

    # Is a generator, yielding False and first sample, and yielding True
    # and last sample.
    @abstractmethod
    def sample(self, feedName: str, n:int) -> (bool, dict):
        raise Exception("Not implemented")

    # Returns a list of the number of data items requested from the feed.
    @abstractmethod
    def data(self, feedName: str, n:int) -> list:
        raise Exception("Not implemented")

    # Runs one execution of the command. Executes the command
    # for all of the available input, until there is nothing to
    # do, or when self.stopExecution(musage) is True.
    # When processed something and more may be available, return True.
    # When needing to sleep, return False.
    @abstractmethod
    def execute(self, musage: MUsage) -> bool:
        raise Exception("Not implemented")

    def stopExecution(self, musage: MUsage) -> bool:
        return ((musage.cpuUsage() > 70)
             or (musage.memoryUsage() > 70))
