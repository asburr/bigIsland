"""
This file is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
 
This file is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
 
See the GNU General Public License, <https://www.gnu.org/licenses/>.
"""
import os
import json
import uuid
import argparse


class MJournal:
    """ Journal is a directory of changes.
        current is the most recent change, it can be undone and then redone.
        A change is,
          {
            __previous__: None,
            __this__: None,
            __next__: None,
            __change__: None
          }
        They are chained together, linked by Previous and Next.
        Each change is identified by a uuid. With the file name, uuid.log.
        The named uuid, is reserved to be used as a filename or subdir and
        is not used by MJournal.
    """
    __previous__ = "previous"
    __this__ = "this"
    __next__ = "next"
    __change__ = "change"
    # head and current are file names for the head of the changes and the
    # current change.
    __head__ = "head"
    __current__ = "current"

    def __init__(self, dir: str):
        self.dir = dir
        if not os.path.isdir(dir):
            os.mkdir(self.dir)
        self.headPath = os.path.join(self.dir,self.__head__)
        self.currentPath = os.path.join(self.dir,self.__current__)
        if os.path.isfile(self.currentPath):
            with open(self.currentPath, "r") as f:
                self.logfile = os.path.join(self.dir,f"{json.load(f)}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
        else: # No current, create an empty head.
            self.logfile = self.headPath
            with open(self.logfile, "w") as f:
                self.log = {
                    self.__previous__: "",
                    self.__this__: self.__head__,
                    self.__next__: "",
                    self.__change__: None
                }
                json.dump(f,self.log)
            with open(self.currentPath, "w") as f:
                json.dump(f,self.__head__)

    def current(self) -> str:
        """ Return UUID for current version of the worksheets """
        if self.log[self.__this__] != self.__head__:
            return self.log[self.__this__]
        return None

    def currentPath(self) -> str:
        """ Return path to current change. """
        if self.log[self.__this__] != self.__head__:
            return os.path.join(self.dir,self.log[self.__this__])
        return None

    def currentChange(self) -> any:
        return self.log[self.__change__]
        
    def Next(self) -> str:
        """ Return UUID for the next change """
        return self.log[self.__next__]

    def nextPath(self) -> str:
        """ Return path to the next change. """
        if self.log[self.__next__]:
            return os.path.join(self.dir,self.log[self.__next__])
        return None

    def add(self, change: any) -> str:
        """ Return path to where a shapshot may be saved for the added change. """
        # Insert the log: (1)ThisLog -> (2)NewLog -> (3)NextLog
        nextUuid = self.log[self.__next__]
        thisUuid = self.log[self.__this__]
        # 2
        newUuid = str(uuid.uuid4())
        newlog = {
            self.__previous__: thisUuid,
            self.__this__: newUuid,
            self.__next__: nextUuid,
            self.__change__: change
        }
        newlogfile = os.path.join(self.dir,f"{newUuid}.log")
        with open(newlogfile, "w") as f: # (2)
            json.dump(f,newlog)
        # 3
        nextlogfile = os.path.join(self.dir,f"{nextUuid}.log")
        with open(nextlogfile, "r") as f:
            nextlog = json.load(f)
        nextlog[self.__previous__] = newUuid
        with open(nextlogfile, "w") as f: # (2)
            json.dump(f,nextlog)
        # 1
        self.log[self.__next__] = newUuid
        with open(self.logfile, "w") as f:
            json.dump(f,self.log)
        with open(self.currentPath, "w") as f:
            json.dump(f,newUuid)
        self.log = newlog
        self.logfile = newlogfile
        return os.path.join(self.dir,newUuid)

    def delete(self) -> bool:
        """ Delete the next change """
        # Delete the log: this->next(delete)->next
        if not self.log[self.__next__]:
            # No next to delete.
            return False
        nextlogfile = os.path.join(self.dir,f"{self.log[self.__next__]}.log")
        with open(nextlogfile, "r") as f:
            nextlog = json.load(f)
        if nextlog[self.__next__]:
            nextnextlogfile = os.path.join(self.dir,f"{nextlog[self.__next__]}.log")
            with open(nextnextlogfile, "r") as f:
                nextnextlog = json.load(f)
            nextnextlog[self.__previous__] = self.log[self.__this__]
            with open(nextnextlogfile, "w") as f:
                json.dump(f,nextnextlog)
            self.log[self.__next__] = nextnextlog[self.__this__]
        else:
            self.log[self.__next__] = ""
        with open(self.logfile, "w") as f:
            json.dump(f,self.log)
        os.unlink(nextlogfile)
        return True

    def rewind(self):
        """ Rewinds to the first change. """
        with open(self.headPath, "r") as f:
            headlog = json.load(f)
        first = headlog[self.__next__]
        if not first:
            return
        else:
            with open(self.currentPath, "w") as f:
                json.dump(f,first)
            self.logfile = os.path.join(self.dir,f"{first}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)

    def up(self) -> bool:
        """ Moves up to the next change """
        Next = self.log[self.__next__]
        if not Next:
            return False
        else:
            with open(self.currentPath, "w") as f:
                json.dump(f,Next)
            self.logfile = os.path.join(self.dir,f"{Next}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
            return True

    def down(self) -> bool:
        """ Moves down to the previous change """
        previous = self.log[self.__previous__]
        if not previous:
            return False
        else:
            with open(self.currentPath, "w") as f:
                json.dump(f,previous)
            self.logfile = os.path.join(self.dir,f"{previous}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
            return True

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Worksheet")
        parser.add_argument('dir', help="worksheet dir")
        parser.add_argument('backup', help="worksheet backup dir")
        args = parser.parse_args()


if __name__ == "__main__":
    MJournal.main()