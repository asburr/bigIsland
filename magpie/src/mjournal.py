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


class MJournal:
    """ Journal is chain of changes, stored in a directory with each file
        documenting the change,
          {
            __previous__: None,
            __this__: None,
            __next__: None,
            __change__: None
          }
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
        if not os.path.isdir(dir):
            os.mkdir(self.dir)
        if purge:
            shutil.rmtree(dir)
            os.mkdir(self.dir)
        self.__headPath = os.path.join(self.dir,self.__head__)
        self.__currentPath = os.path.join(self.dir,self.__current__)
        if os.path.isfile(self.__currentPath):
            with open(self.__currentPath, "r") as f:
                self.logfile = os.path.join(self.dir,f"{json.load(f)}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
        else: # No current, create the head.
            self.__emptyHead()
        self.audit()

    def empty(self) -> bool:
        with open(self.__headPath, "r") as f:
            headUuid = json.load(f)
        if self.current() != headUuid: # More than one change.
            return False
        with open(os.path.join(self.dir,f"{headUuid}.log"), "r") as f:
            head = json.load(f)
        if head[self.__next__]: # More than one change.
            return False
        return True # No changes, only head.

    def __emptyHead(self):
        """ Create a new chain, an empty chain, with current pointing to head """
        loguuid = str(uuid.uuid4())
        self.logfile = os.path.join(self.dir,f"{loguuid}.log")
        with open(self.logfile, "w") as f:
            self.log = {
                self.__previous__: "",
                self.__this__: loguuid,
                self.__next__: "",
                self.__change__: {}
            }
            json.dump(self.log,f)
        os.mkdir(os.path.join(self.dir,loguuid))
        with open(self.__currentPath, "w") as f:
            json.dump(loguuid,f)
        with open(self.__headPath, "w") as f:
            json.dump(loguuid,f)
        
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
        with open(self.__currentPath, "r") as f:
            current = json.load(f)
        with open(self.__headPath, "r") as f:
            uuid = json.load(f)
        __headPath = os.path.join(self.dir,f"{uuid}.log")
        with open(__headPath, "r") as f:
            head = json.load(f)     
        if not head[self.__next__]:
            return "No changes"
        nextp = os.path.join(self.dir,f"{head[self.__next__]}.log")
        with open(nextp, "r") as f:
            log = json.load(f)
        s=""
        while log:
            if log[self.__this__] == current:
                s+=f"{log[self.__this__]} current"
            else:
                s+=f"{log[self.__this__]}"
            if log[self.__next__]:
                with open(os.path.join(self.dir,f"{log[self.__next__]}.log"), "r") as f:
                    log = json.load(f)
            else:
                log = None
        return s

    def head(self) -> str:
        with open(self.__headPath, "r") as f:
            return json.load(f)

    def current(self) -> str:
        """ UUID for the current change. """
        if self.log[self.__this__] != self.__head__:
            return self.log[self.__this__]
        return None

    def currentPath(self) -> str:
        """ Path for the current change. """
        if self.log[self.__this__] != self.__head__:
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
        """ Path to the change. """
        # Insert order: (3)ThisLog -> (1)NewLog -> (2)NextLog.
        nextUuid = self.log[self.__next__]
        thisUuid = self.log[self.__this__]
        # 1 Newlog is created first and linked to next and previous.
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

    def delete(self) -> bool:
        """ Delete the next change """
        # Delete the log: this->next(delete)->next
        if not self.log[self.__next__]:
            # No next to delete.
            return False
        # 1 nextlog is to be deleted.
        nextlogfile = os.path.join(self.dir,f"{self.log[self.__next__]}.log")
        with open(nextlogfile, "r") as f:
            nextlog = json.load(f)
        # 1 next is linked backward, over the deleted change.
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
        # 2 Update current change to beyond the deleted change.
        with open(self.logfile, "w") as f:
            json.dump(self.log,f)
        # Delete the change.
        os.unlink(nextlogfile)
        shutil.rmtree(os.path.join(self.dir,nextlog[self.__this__]))
        return True

    def rewind(self):
        """ Rewinds to the head of the changes. """
        with open(self.__headPath, "r") as f:
            uuid = json.load(f)
        self.logfile = os.path.join(self.dir,f"{uuid}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        with open(self.__currentPath, "w") as f:
            json.dump(uuid,f)

    def up(self) -> bool:
        """ Moves up to the next change """
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
        """ Moves down to the previous change """
        previous = self.log[self.__previous__]
        print(self.log)
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
            ("add",{"test": "testing"}),("print",None),
            ("add",{"test": "testing"}),("print",None),
            ("del",False),
            ("rewind",None),("print",None),
            ("up",True),("print",None),
            ("up",True),("print",None),
            ("up",False),("print",None),
            ("down",True),("print",None),
            ("down",True),("print",None),
            ("down",False),("print",None),
            ("rewind",None),
            ("del",True),("print",None),
            ("del",True),("print",None),
            ("del",False),("print",None),
            ("rewind",None),
            ("add",{"test": "testing"}),("print",None),
            ("del",False),
            ("rewind",None),
            ("del",True),("print",None),
        ]:
            if cmd == "stop":
                return
            if cmd == "print":
                print(journal)
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