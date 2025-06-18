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
    """
    Cmd: Abstract class for database commands.
    """
    def __init__(self):
        """
        Cmd ages off the schema after a week (168 hours).
        """
        print("Init of cmd")
        self.disco = SchemaDiscovery(ageoff_hour_limit=168)
        print(self.disco)
        self.testReceiver = None

    def schema(self) -> any:
        """
         schema: The schema is created by self.disco, and is a description
         of the structure of the inputted data as seen so far by this command.
         self.execute() must load inputted data into self.disco.load().
         return self.disco.r
         Is a generator, yielding False and first sample, and yielding True
         and last sample.
         """
        return self.disco.r

    @abstractmethod
    def data(self, feedName: str, n:int) -> list:
        """
        data: Returns a list of the number of data items requested from the feed.
        """
        raise Exception("Not implemented")

    @abstractmethod
    def execute(self, musage: MUsage) -> bool:
        """
         execute: Runs one execution of the command. Executes the command
         for all of the available input, until there is nothing to
         do, or when self.stopExecution(musage) is True.
         When processed something and more may be available, return True.
         When nothing to process and needing to sleep, return False.
         """
        raise Exception("Not implemented")

    def stopExecution(self, musage: MUsage) -> bool:
        """
        stopExecution: Stops executing command when host resources are about 70%.
        """
        return ((musage.cpuUsage() > 70)
             or (musage.memoryUsage() > 70))