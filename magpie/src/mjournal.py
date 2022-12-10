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
from magpie.src.mlogger import MLogger, mlogger
from magpie.src.mzdatetime import MZdatetime


class MJournalChange:
    """
    A change.
    """
    def __init__(self):
        self.when = MZdatetime().strftime()
        pass

    def json(self):
        d={"type": self.__class__.__name__}
        for k, v in self.__dict__.items():
            d[k] = v
        return d


class MJournal:
    """ Journal is chain of changes, stored in a directory with each file
        documenting a change,
          {
            __previous__: None,
            __this__: None,
            __next__: None,
            __change__: None
          }
        Head is the oldest, previous gets the older change, next gets the
        newer change.
        A UUID uniquely identifies the change, and the change file is named
        after the uuid, uuid.log. There is a subdir that is also named after
        the UUID. The subdir is not used by MJournal but is reserved for
        clients to store files before the change, for example, making a copy
        of files before they are changed.
    """
    __previous__ = "previous"
    __this__ = "this"
    __next__ = "next"
    __change__ = "change"
    # head and current are file names for the head of the changes and the
    # current change.
    __head__ = "head"
    __current__ = "current"

    def __init__(self, dir: str, purge:bool = False):
        """ There is a head and it has the client files before any changes.
            Head links to the first change.
        """
        self.dir = dir
        if purge:
            shutil.rmtree(dir)
        if not os.path.isdir(dir):
            os.mkdir(self.dir)
        self.__headPath = os.path.join(self.dir,self.__head__)
        self.__currentPath = os.path.join(self.dir,self.__current__)
        if os.path.isfile(self.__currentPath):
            with open(self.__currentPath, "r") as f:
                self.logfile = os.path.join(self.dir,f"{json.load(f)}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
        else:
            self.lofile = None
            self.log = None
        self.audit()

    def empty(self) -> bool:
        return not os.path.isfile(self.__headPath)

    def audit(self):
        """ Audit change directory. """
        change = True
        while change == True:
            change = False
            for name in os.listdir(path=self.dir):
                p = os.path.join(self.dir,name)
                if os.path.isfile(p):
                    with open(p, "r") as f:
                        if name == self.__head__:
                            head = json.load(f)
                            headp = os.path.join(self.dir,f"{head}.log")
                            if not os.path.isfile(headp):
                                if MLogger.isError():
                                    mlogger.error(f"head ref to {headp} which does not exist")
                                if MLogger.isWarning():
                                    mlogger.warning("creating an empty head")
                                self.__emptyHead()
                        elif name == self.__current__:
                            current = json.load(f)
                            currentp = os.path.join(self.dir,f"{current}.log")
                            if not os.path.isfile(currentp):
                                if MLogger.isError():
                                    mlogger.error(f"current ref to {currentp} which does not exist")
                                with open(self.__headPath, "r") as f:
                                    head = json.load(f)
                                    if MLogger.isWarning():
                                        mlogger.warning(f"Current moved to head {head}")
                                    with open(self.__currentPath, "w") as f:
                                        json.dump(head,f)
                        else:
                            log = json.load(f)
                            if log[self.__next__]:
                                nextp = os.path.join(self.dir,f"{log[self.__next__]}.log")
                                if not os.path.isfile(nextp):
                                    if MLogger.isWarning():
                                        mlogger.warning(f"removing change {p} with next {nextp} that does not exist")
                                    os.unlink(p)
                                    change = True
                                    continue
                            if log[self.__previous__]:
                                previousp = os.path.join(self.dir,f"{log[self.__previous__]}.log")
                                if not os.path.isfile(previousp):
                                    if MLogger.isWarning():
                                        mlogger.warning(f"removing change {p} with previous {previousp} that does not exist")
                                    os.unlink(p)
                                    change = True
                                    continue
                else: # subdir.
                    logp = os.path.join(self.dir,f"{name}.log")
                    if not os.path.isfile(logp):
                        if MLogger.isWarning():
                            mlogger.warning(f"subdir {p} without {logp}, removing subdir")
                        shutil.rmtree(p)
                        change = True
                        continue

    def __str__(self) -> str:
        """ End of the list to head. """
        if not os.path.isfile(self.__headPath):
            return "No changes"
        with open(self.__currentPath, "r") as f:
            current = json.load(f)
        with open(self.__headPath, "r") as f:
            uuid = json.load(f)
        __headPath = os.path.join(self.dir,f"{uuid}.log")
        with open(__headPath, "r") as f:
            log = json.load(f)     
        while log[self.__next__]:
            with open(os.path.join(self.dir,f"{log[self.__next__]}.log"), "r") as f:
                log = json.load(f)
        s=""
        while log:
            s+=f"{log[self.__previous__]} < {log[self.__this__]}:{log[self.__change__]} > {log[self.__next__]}"
            if log[self.__this__] == current:
                s+=" current\n"
            else:
                s+="\n"
            if log[self.__previous__]:
                with open(os.path.join(self.dir,f"{log[self.__previous__]}.log"), "r") as f:
                    log = json.load(f)
            else:
                log = None
        return s

    def head(self) -> str:
        """ UUID for the first change. """
        if not os.path.isfile(self.__headPath):
            with open(self.__headPath, "r") as f:
                return json.load(f)
        return None

    def current(self) -> str:
        """ UUID for the current change. """
        if self.log:
            return self.log[self.__this__]
        return None

    def currentPath(self) -> str:
        """ Path for the current change. """
        if self.log:
            return os.path.join(self.dir,self.log[self.__this__])
        return None

    def currentChange(self) -> any:
        """ Change for the current change. """
        return self.log[self.__change__]

    def next(self) -> str:
        """ UUID for the next change """
        return self.log[self.__next__]

    def nextChange(self) -> any:
        """ Change for the next change. """
        if self.log[self.__next__]:
            nextlogfile = os.path.join(self.dir,f"{self.log[self.__next__]}.log")
            with open(nextlogfile, "r") as f:
                nextlog = json.load(f)
            return nextlog[self.__change__]
        return None

    def nextPath(self) -> str:
        """ Path for the next change. """
        if self.log[self.__next__]:
            return os.path.join(self.dir,self.log[self.__next__])
        return None

    def previous(self) -> str:
        """ UUID for the previous change """
        if self.log[self.__previous__] != self.__head__:
            return self.log[self.__previous__]
        return None

    def previousPath(self) -> str:
        """ Path for the previous change. """
        if self.log[self.__previous__] != self.__head__:
            return os.path.join(self.dir,self.log[self.__previous__])
        return None

    def add(self, change: any) -> str:
        """
        A new change after the most resent change to become the
        current change.
        Insert order: (3)ThisLog -> (1)NewLog -> (2)NextLog.
        """
        newUuid = str(uuid.uuid4())
        newlogfile = os.path.join(self.dir,f"{newUuid}.log")
        if not os.path.isfile(self.__headPath):
            with open(newlogfile, "w") as f:
                newlog = {
                    self.__previous__: "",
                    self.__this__: newUuid,
                    self.__next__: "",
                    self.__change__: change
                }
                json.dump(newlog,f)
            with open(self.__headPath, "w") as f:
                json.dump(newUuid,f)
        else:
            nextUuid = self.log[self.__next__]
            thisUuid = self.log[self.__this__]
            # 1 Newlog is created first and linked to next and previous.
            newlog = {
                self.__previous__: thisUuid,
                self.__this__: newUuid,
                self.__next__: nextUuid,
                self.__change__: change
            }
            with open(newlogfile, "w") as f:
                json.dump(newlog,f)
            # 2 Nextlog is linked back to the newlog.
            if nextUuid:
                nextlogfile = os.path.join(self.dir,f"{nextUuid}.log")
                with open(nextlogfile, "r") as f:
                    nextlog = json.load(f)
                nextlog[self.__previous__] = newUuid
                with open(nextlogfile, "w") as f:
                    json.dump(nextlog,f)
            # 3 thislog is linked forward to newlog.
            self.log[self.__next__] = newUuid
            with open(self.logfile, "w") as f:
                json.dump(self.log,f)
        # Newlog is current.
        with open(self.__currentPath, "w") as f:
            json.dump(newUuid,f)
        self.log = newlog
        self.logfile = newlogfile
        # Finally, create the change path and return it.
        uuidPath =  os.path.join(self.dir,newUuid)
        os.mkdir(uuidPath)
        return uuidPath

    def insertRoot(self, change: MJournalChange) -> str:
        """
        Insert change as the new root, make it the current change too.
        """
        newUuid = str(uuid.uuid4())
        newlogfile = os.path.join(self.dir,f"{newUuid}.log")
        newlog = {
            self.__previous__: "",
            self.__this__: newUuid,
            self.__next__: "",
            self.__change__: change.json()
        }
        if os.path.isfile(self.__headPath):
            with open(self.__headPath, "r") as f:
                headuuid = json.load(f)
            headlogfile = os.path.join(self.dir,f"{headuuid}.log")
            with open(headlogfile, "r") as f:
                headlog = json.load(f)
            headlog[self.__previous__] = newUuid
            with open(headlogfile, "w") as f:
                json.dump(headlog,f)
            newlog[self.__next__] = headuuid
        with open(newlogfile, "w") as f:
            json.dump(newlog,f)
        with open(self.__headPath, "w") as f:
            json.dump(newUuid,f)
        with open(self.__currentPath, "w") as f:
            json.dump(newUuid,f)
        uuidPath =  os.path.join(self.dir,newUuid)
        os.mkdir(uuidPath)
        self.log  = newlog
        self.logfile = newlogfile
        return uuidPath

    def delete(self) -> bool:
        """
        Delete the current change.
        1/ Current has a previous change, current is the older change.
        2/ Or, Current has a next change, current is the newer change.
        3/ Or, when no other change, chain is empty.
        """
        oldlog = self.log
        if not oldlog:
            return False
        oldlogfile = self.logfile
        self.log = None
        self.logfile = None
        previousuuid = oldlog[self.__previous__]
        nextuuid = oldlog[self.__next__]
        if previousuuid:
            previousfile = os.path.join(self.dir,f"{previousuuid}.log")
            with open(previousfile, "r") as f:
                previouslog = json.load(f)
            previouslog[self.__next__] = nextuuid
            with open(previousfile, "w") as f:
                json.dump(previouslog,f)
            self.log = previouslog
            self.logfile = previousfile
        if nextuuid:
            nextfile = os.path.join(self.dir,f"{nextuuid}.log")
            with open(nextfile, "r") as f:
                nextlog = json.load(f)
            nextlog[self.__previous__] = previousuuid
            with open(nextfile, "w") as f:
                json.dump(nextlog,f)
            if not self.log:
                self.log = nextlog
                self.logfile = nextfile
        os.unlink(oldlogfile)
        shutil.rmtree(os.path.join(self.dir,oldlog[self.__this__]))
        if self.log:
            with open(self.__currentPath, "w") as f:
                json.dump(self.log[self.__this__],f)
            with open(self.__headPath, "r") as f:
                headuuid = json.load(f)
            if headuuid == oldlog[self.__this__]:
                with open(self.__headPath, "w") as f:
                    json.dump(self.log[self.__this__],f)
        else:
            os.unlink(self.__headPath)
            os.unlink(self.__currentPath)
        return True

    def prune(self):
        """ Deletes changes prior to Current, making current the new root. """
        current = self.current()
        self.rewind()
        while self.current() != current:
            self.delete()

    def rewind(self):
        """ Rewinds to the oldest change. """
        if not os.path.isfile(self.__headPath):
            return
        with open(self.__headPath, "r") as f:
            uuid = json.load(f)
        self.logfile = os.path.join(self.dir,f"{uuid}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        with open(self.__currentPath, "w") as f:
            json.dump(uuid,f)

    def up(self) -> bool:
        """ Moves up to the newer change """
        next = self.log[self.__next__]
        if not next:
            return False
        with open(self.__currentPath, "w") as f:
            json.dump(next,f)
        self.logfile = os.path.join(self.dir,f"{next}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        return True

    def down(self) -> bool:
        """ Moves down to the older change """
        previous = self.log[self.__previous__]
        if not previous:
            return False
        with open(self.__currentPath, "w") as f:
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
            ("add",{"test1": "testing"}),("print",None),
            ("add",{"test2": "testing"}),("print",None),
            ("audit", None),
            ("del",True),
            ("rewind",None),("print",None),
            ("up",False),
            ("down",False),
            ("rewind",None),
            ("del",True),("print",None),
            ("audit", None),
            ("del",False),
            ("rewind",None),("print",None),
            ("add",{"test3": "testing"}),("print",None),
            ("insertRoot",{"test4": "testing"}),("print",None),
            ("insertRoot",{"test5": "testing"}),("print",None),
            ("audit", None),
            ("del",True),("print",None),
            ("del",True),("print",None),
            ("rewind",None),
            ("del",True),
            ("audit", None),
            ("del",False),
        ]:
            if data is not None:
                print(f"{cmd} {data}")
            else:
                print(f"{cmd}")
            if cmd == "stop":
                return
            if cmd == "print":
                print(journal)
                continue
            if cmd == "audit":
                journal.audit()
                continue
            if cmd == "add":
                changePath=journal.add(data)
                with open(os.path.join(changePath,"tdump"),"w") as f:
                    json.dump(data,f)
            elif cmd == "insertRoot":
                changePath=journal.insertRoot(data)
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