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
from abc import abstractmethod
from magpie.src.musage import MUsage
from discovery.src.discovery import SchemaDiscovery

class Feed:
    """ A data feed. """
    def __init__(self,name:str): self.name = name
    def __str__(self): return self.name
    def __eq__(self,o): return str(o) == str(self)
    def __gt__(self,o): return str(o) > str(self)
    def __lt__(self,o): return str(o) < str(self)


class Feeds:
    """ Mapping of feed name to Feed. """
    def __init__(self):
        self.feeds:dict = {}
    def add(self,feed:Feed) -> None:
        """ Add a Feed. """
        if feed.name in self.feeds: raise Exception(f"{feed.name} exists")
        self.feeds[feed.name]=feed
    def get(self,feedName: str) -> Feed:
        """ Get a Feed object. """
        return self.feeds.get(feedName)
    def yields(self) -> Feed:
        """ Iterate through the Feed objects. """
        for feed in self.feeds.values(): yield feed
    def sanity(self) -> None:
        """ At least one feed. """
        if len(self.feeds) == 0:
            raise Exception("No feeds!")
    def __str__(self): return f"{self.feeds}"
    def __eq__(self,o): return str(o) == str(self)
    def __gt__(self,o): return str(o) > str(self)
    def __lt__(self,o): return str(o) < str(self)    


class Cmd:
    """
    Cmd: Abstract class for hallelujah commands.
    Ages off the schema after a week (168 hours).
    """
    def __init__(self):
        self.disco:SchemaDiscovery = SchemaDiscovery(ageoff_hour_limit=168)
        self.debug:bool = False
        self.feeds = Feeds()

    def schema(self) -> any:
        """
        Returns the schema as created by self.disco. Schema is a description
        of the structure of the inputted data as seen so far by this command.
        self.execute() must load inputted data into self.disco.load().
        """
        return self.disco.r

    @abstractmethod
    def data(self, feedName: str, n:int) -> list:
        """
        Returns a sample of n data items from feedName.
        """
        raise Exception("abstract should be implemented in subclass")
        # for example,
        return [f"data{i}" for i in range(n)] # list of n fake data items.
        return [] # Empty list when nothing to return.

    def execute(self, musage: MUsage) -> None:
        """
        Executes the command for all of the available input, until there is
        nothing to do, or when resources (musage) are exhausted.
        """
        if self.stopExecution(musage): return
        for data_json in self.process():
            self.disco.load(data_json)
            if self.stopExecution(musage): return

    @abstractmethod
    def process(self) -> object:
        """
        Returns a json compatable Object resulting from one execution of the command.
        """
        raise Exception("abstract should be implemented in subclass")
        # Examples,
        return [1,2,3] # processed something into a json compatable list.
        return None # Nothing to process.

    def stopExecution(self, musage: MUsage) -> bool:
        """
        stopExecution: Stops executing command when host resources are about 70%.
        """
        return ((musage.cpuUsage() > 70)
             or (musage.memoryUsage() > 70))