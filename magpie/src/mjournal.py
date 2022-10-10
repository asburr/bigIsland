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
import shutil


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
        Changes are chained together, linked by Previous and Next.
        Each change is uniquely identified by a UUID.
        Each change is in a file named uuid.log.
        Each change has a subdir named uuid, this subdir is not used by
        MJournal, but the subdir is reserved for clients to store
        files associated with the change. Although the subdir may contain
        anything, the intent is a copy before the change to support rollback.
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
        self.headPath = os.path.join(self.dir,f"{self.__head__}.log")
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
                    self.__change__: {}
                }
                json.dump(self.log,f)
            with open(self.currentPath, "w") as f:
                json.dump(self.__head__,f)
        self.audit()

    def audit(self):
        """ Audit changes. Checking for next and previous reference files that exist.
            And, that subdir exists. Deleting changes with bad next and previous
            references, and bad subdir.
        """
        change = True
        while change == True:
            change = False
            for name in os.listdir(path=self.dir):
                p = os.path.join(self.dir,name)
                if os.path.isfile(p):
                    with open(p, "r") as f:
                        if name == self.__current__:
                            current = json.load(f)
                            currentp = os.path.join(self.dir,f"{current}.log")
                            if not os.path.isfile(currentp):
                                print(f"WARNING: current {currentp} does not exist")
                                with open(self.headPath, "r") as f:
                                    head = json.load(f)
                                if not head[self.__next__]:
                                    print("WARNING: Current moved to empty head")
                                    with open(self.currentPath, "w") as f:
                                        json.dump(self.__head__,f)
                                else:
                                    print("WARNING: Current moved to the first change")
                                    with open(self.currentPath, "w") as f:
                                        json.dump(head[self.__next__],f)
                        else:
                            log = json.load(f)
                            if log[self.__next__]:
                                nextp = os.path.join(self.dir,f"{log[self.__next__]}.log")
                                if not os.path.isfile(nextp):
                                    print(f"WARNING: removing change {p} with next {nextp} that does not exist")
                                    os.unlink(p)
                                    change = True
                                    continue
                            if log[self.__previous__]:
                                previousp = os.path.join(self.dir,f"{log[self.__previous__]}.log")
                                if not os.path.isfile(previousp):
                                    print(f"WARNING: removing change {p} with previous {previousp} that does not exist")
                                    os.unlink(p)
                                    change = True
                                    continue
                else:
                    logp = os.path.join(self.dir,f"{name}.log")
                    if not os.path.isfile(logp):
                        print(f"WARNING: removing subdir {p} that is without {logp}")
                        shutil.rmtree(p)
                        change = True
                        continue

    def print(self) -> None:
        with open(self.currentPath, "r") as f:
            current = json.load(f)
        with open(self.headPath, "r") as f:
            head = json.load(f)
        if not head[self.__next__]:
            print("No changes")
            return
        p = os.path.join(self.dir,f"{head[self.__next__]}.log")
        with open(p, "r") as f:
            log = json.load(f)
        while log:
            print()
            if log[self.__this__] == current:
                print(f"{log[self.__this__]} current")
            else:
                print(f"{log[self.__this__]}")
            if log[self.__next__]:
                with open(os.path.join(self.dir,f"{log[self.__next__]}.log"), "r") as f:
                    log = json.load(f)
            else:
                log = None

    def current(self) -> str:
        """ Return UUID for current version of the worksheets """
        if self.log[self.__this__] != self.__head__:
            return self.log[self.__this__]
        return None

    def currentPath(self) -> str:
        """ Return path to subdir for the current change. """
        if self.log[self.__this__] != self.__head__:
            return os.path.join(self.dir,self.log[self.__this__])
        return None

    def currentChange(self) -> any:
        return self.log[self.__change__]
        
    def Next(self) -> str:
        """ Return UUID for the next change """
        return self.log[self.__next__]

    def nextPath(self) -> str:
        """ Return path to the subdir for the next change. """
        if self.log[self.__next__]:
            return os.path.join(self.dir,self.log[self.__next__])
        return None

    def add(self, change: any) -> str:
        """ Return path to subdir for the added change. """
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
            json.dump(newlog,f)
        # 3
        if nextUuid:
            nextlogfile = os.path.join(self.dir,f"{nextUuid}.log")
            with open(nextlogfile, "r") as f:
                nextlog = json.load(f)
            nextlog[self.__previous__] = newUuid
            with open(nextlogfile, "w") as f: # (2)
                json.dump(nextlog,f)
        # 1
        self.log[self.__next__] = newUuid
        with open(self.logfile, "w") as f:
            json.dump(self.log,f)
        with open(self.currentPath, "w") as f:
            json.dump(newUuid,f)
        self.log = newlog
        self.logfile = newlogfile
        uuidPath =  os.path.join(self.dir,newUuid)
        os.mkdir(uuidPath)
        return uuidPath

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
                json.dump(nextnextlog,f)
            self.log[self.__next__] = nextnextlog[self.__this__]
        else:
            self.log[self.__next__] = ""
        with open(self.logfile, "w") as f:
            json.dump(self.log,f)
        os.unlink(nextlogfile)
        shutil.rmtree(os.path.join(self.dir,nextlog[self.__this__]))
        return True

    def rewind(self):
        """ Rewinds to the head of the changes. """
        with open(self.currentPath, "w") as f:
            json.dump(self.__head__,f)
        self.logfile = os.path.join(self.dir,f"{self.__head__}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)

    def up(self) -> bool:
        """ Moves up to the next change """
        Next = self.log[self.__next__]
        if not Next:
            return False
        else:
            with open(self.currentPath, "w") as f:
                json.dump(Next,f)
            self.logfile = os.path.join(self.dir,f"{Next}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
            return True

    def down(self) -> bool:
        """ Moves down to the previous change """
        previous = self.log[self.__previous__]
        print(self.log)
        if not previous:
            return False
        else:
            with open(self.currentPath, "w") as f:
                json.dump(previous,f)
            self.logfile = os.path.join(self.dir,f"{previous}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
            return True

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Journal")
        parser.add_argument('dir', help="Journal dir")
        args = parser.parse_args()
        shutil.rmtree(args.dir)
        journal = MJournal(args.dir)
        for cmd, data in [
            ("add",{"test": "testing"}),
            ("print",None),
            ("add",{"test": "testing"}),
            ("print",None),
            ("del",False),
            ("rewind",None),
            ("print",None),
            ("up",True),
            ("print",None),
            ("up",True),
            ("print",None),
            ("up",False),
            ("print",None),
            ("down",True),
            ("print",None),
            ("down",True),
            ("print",None),
            ("down",False),
            ("print",None),
            ("rewind",None),
            ("del",True),
            ("print",None),
            ("del",True),
            ("print",None),
            ("del",False),
            ("print",None),
            ("rewind",None),
            ("add",{"test": "testing"}),
            ("print",None),
            ("del",False),
            ("rewind",None),
            ("del",True),
            ("print",None),
        ]:
            if cmd == "print":
                journal.print()
                continue
            if data:
                print(f"{cmd} {data}")
            else:
                print(f"{cmd}")
            if cmd == "add":
                changePath=journal.add(data)
                with open(os.path.join(changePath,"tdump"),"w") as f:
                    json.dump(data,f)
            elif cmd == "del":
                if journal.delete() != data:
                    raise Exception(f"Failed del != {data}")
            elif cmd == "rewind":
                journal.rewind()
            elif cmd == "up":
                if journal.up() != data:
                    raise Exception(f"Failed up != {data}")
            elif cmd == "down":
                if journal.down() != data:
                    raise Exception(f"Failed down != {data}")
            else:
                raise Exception(f"Unknown cmd {cmd}")
                

if __name__ == "__main__":
    MJournal.main()