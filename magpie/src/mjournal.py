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
import copy
from magpie.src.mlogger import MLogger, mlogger
from magpie.src.mzdatetime import MZdatetime


class MJournalChange:
    """ A change. """
    __type__ = "type"
    __when__ = "when"

    def __init__(self,when:MZdatetime):
        if when is None:
            self.when=MZdatetime()
        else:
            self.when = when

    def json(self):
        d={self.__type__: self.__class__.__name__}
        for k, v in self.__dict__.items():
            d[k] = v
        d[self.__when__] = d[self.__when__].strftime(short=True)
        return d

    def fromJson(j: dict, factoryClass) -> "MJournalChange":
        return factoryClass.make(j)

    def __str__(self) -> str:
        return self.__class__.__name__+" "+self.when.strftime(short=True)

    def msgParams(self) -> dict:
        """ Database message parameters for this change. """
        return {}
    
    def msgType(self) -> str:
        """ Database message type for this change. """
        return ""
    
    def reversed(self) -> "MJournalChange":
        """ Reverse the change to undo. """
        return ""


class MJournalRebase(MJournalChange):
    """ A rebase to a new root, this in itself is not a change. """
    def __init__(self, sourcePath:str, when:MZdatetime = None):
        super().__init__(when)
        self.sourcePath = sourcePath
        pass
    
    def __str__(self):
        return self.when.strftime(short=True)+" newbase "

    def msgType(self) -> str:
        return None


class MJournalChangeTest(MJournalChange):
    def __init__(self, label:str, when:str=None):
        super().__init__(when)
        self.label=label


class MJournalChangeFactory:
    def jsonToDict(j:dict) -> dict:
        x=copy.copy(j)
        x[MJournalChange.__when__] = MZdatetime.strptime(j[MJournalChange.__when__])
        del x[MJournalChange.__type__]
        return x

    def make(j:dict) -> "MJournalChange":
        if not j:
          return None
        t = j[MJournalChange.__type__]
        if t == "MJournalRebase":
            return MJournalRebase(**MJournalChangeFactory.jsonToDict(j))
        raise Exception(f"Not implemented for {t}")


class MJournalChangeTestFactory(MJournalChangeFactory):
    def make(j: dict):
        if not j:
            return None
        t = j[MJournalChange.__type__]
        if t == "MJournalChangeTest":
            return MJournalChangeTest(**MJournalChangeFactory.jsonToDict(j))
        return super().make(j)


class MJournal:
    """ MJournal is chain of changes, stored in a directory with each file
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
        
        Change has a copy of the worksheet used to reinstate the change.
        Applying all changes has current being the end of changes.
        Undo reads the current worksheet and then moves to the prev change.
        When at the first change, there is no prev change and cannot go beyond
        the first change.
        When at the last change, there is no next change and cannot go beyond
        the last change.
        Problem when on the first change, how to know if that change has been
        undo?? Current should be None, then know not to undo any further.
        No problem when on the last change, that change has been redone! 
    """
    __previous__ = "previous"
    __this__ = "this"
    __next__ = "next"
    __change__ = "change"
    # head and current are file names for the head of the changes and the
    # current change.
    __head__ = "head"
    __current__ = "current"

    def __init__(self, dir: str, changeFactoryClass, purge:bool = False):
        """ There is a head and it has the client files before any changes.
            Head links to the first change.
        """
        self.dir = dir
        self.__headPath = os.path.join(self.dir,self.__head__)
        self.__currentPath = os.path.join(self.dir,self.__current__)
        self.changeFactoryClass = changeFactoryClass
        if os.path.exists(dir) and (purge or not os.path.exists(self.__currentPath)):
            shutil.rmtree(dir)
        if not os.path.isdir(dir):
            self.__newJournal()
        with open(self.__currentPath, "r") as f:
            self.logfile = os.path.join(self.dir,f"{json.load(f)}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        self.audit()

    def isempty(self) -> bool:
        """ There is always a head, so empty is when log is head (not previous) has no next. """
        return not self.log[self.__previous__] and not self.log[self.__next__]

    def __newJournal(self) -> None:
        """ Creates a new journal in an empty directory. """
        os.mkdir(self.dir)
        self.log = {
            self.__previous__: "",
            self.__this__: str(uuid.uuid4()),
            self.__next__: "",
            self.__change__: None
        }
        self.logfile = os.path.join(self.dir,f"{self.log[self.__this__]}.log")
        self.logpath = os.path.join(self.dir,f"{self.log[self.__this__]}")
        if os.path.isdir(self.logpath):
            shutil.rmtree(self.logpath)
        os.mkdir(self.logpath)
        with open(self.logfile, "w") as f:
            json.dump(self.log,f)
        with open(self.__headPath, "w") as f:
            json.dump(self.log[self.__this__],f)
        with open(self.__currentPath, "w") as f:
            json.dump(self.log[self.__this__],f)

    def trash(self) -> bool:
        """ Delete the existing journal and recreate as an empty journal. """
        shutil.rmtree(self.dir)
        self.__newJournal()

    def audit(self):
        """ Audit change directory. """
        change = True
        while change == True:
            change = False
            for name in os.listdir(path=self.dir):
                p = os.path.join(self.dir,name)
                if os.path.isfile(p) and not name.startswith("."):
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
                        elif name.endswith(".log"):
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
                elif os.path.isdir(p):
                    logp = os.path.join(self.dir,f"{name}.log")
                    if not os.path.isfile(logp):
                        if MLogger.isWarning():
                            mlogger.warning(f"subdir {p} without {logp}, removing subdir")
                        shutil.rmtree(p)
                        change = True
                        continue

    def __str__(self) -> str:
        """ Show changes in undo order, current, then redo order. """
        if self.isempty():
            return ">> No changes <<"
        # newbase
        with open(self.__currentPath, "r") as f:
            current = json.load(f)
        cur = current
        undo=0
        while cur:
            undo += 1
            with open(os.path.join(self.dir,f"{cur}.log"), "r") as f:
                cur = json.load(f)
            log = cur
            cur = cur[self.__previous__]
        s=""
        redo=0
        while log:
            label=[]
            prev = log[self.__previous__]
            if prev: # don't show head.
                ths = log[self.__this__]
                if ths == current and undo != 1:
                    raise Exception(f"start {undo} {redo}")
                if log[self.__change__][MJournalChange.__type__] == "MJournalRebase":
                    label.append("BASE")                    
                elif undo:
                    label.append("UNDO "+str(undo))
                else:
                    label.append("REDO "+str(redo))
                s+="\n"
                if label:
                    label=(",".join(label))
                    s+=f"{label}"
                if log[self.__change__]:
                  s+=f"\n{json.dumps(log[self.__change__],indent=2)}"
            if undo:
                undo = undo - 1
                if not undo:
                    redo = 1
            else:
                redo = redo + 1
            if log[self.__next__]:
                with open(os.path.join(self.dir,f"{log[self.__next__]}.log"), "r") as f:
                    log = json.load(f)
            else:
                log = None
        return s

    def getChanges(self) -> list:
        """ Get changes in order. """
        retval = []
        if self.isempty():
            return retval
        with open(self.__headPath, "r") as f:
            uuid = json.load(f)
        __headPath = os.path.join(self.dir,f"{uuid}.log")
        with open(__headPath, "r") as f:
            log = json.load(f)
            retval.append(log)
        while log[self.__next__]:
            with open(os.path.join(self.dir,f"{log[self.__next__]}.log"), "r") as f:
                log = json.load(f)
                retval.append(log)
        return retval

    def head(self) -> str:
        """ UUID for the first change. """
        if os.path.isfile(self.__headPath):
            with open(self.__headPath, "r") as f:
                return json.load(f)
        return None

    def headPath(self) -> str:
        """ Path for the first change. """
        head = self.head()
        if head:
            return os.path.join(self.dir,head)
        return None

    def atHead(self) -> bool:
        """ True when current is head """
        return self.head() == self.log[self.__this__]

    def moveToHead(self) -> None:
        """ Move to first change """
        if self.atHead():
            return
        headuuid = self.head()
        self.logfile = os.path.join(self.dir,f"{headuuid}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        with open(self.__currentPath, "w") as f:
            json.dump(headuuid,f)

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

    def currentChange(self) -> MJournalChange:
        """ Change for the current change. """
        return MJournalChange.fromJson(self.log[self.__change__],self.changeFactoryClass)

    def next(self) -> str:
        """ UUID for the next change """
        if self.log:
            return self.log[self.__next__]
        return self.head()

    def nextPath(self) -> str:
        """ Path for the next change. """
        n = self.next()
        if n:
            return os.path.join(self.dir,n)
        return None

    def nextChange(self) -> MJournalChange:
        """ Change for the next change. """
        n = self.next()
        if n:
            nextlogfile = os.path.join(self.dir,f"{n}.log")
            with open(nextlogfile, "r") as f:
                nextlog = json.load(f)
            return MJournalChange.fromJson(nextlog[self.__change__],self.changeFactoryClass)
        return None

    def previous(self) -> str:
        """ UUID for the previous change """
        if self.log:
            if self.log[self.__previous__]:
                return self.log[self.__previous__]
        return None

    def previousChange(self) -> MJournalChange:
        """ Change for the previous change. """
        p = self.previous()
        if p:
            previouslogfile = os.path.join(self.dir,f"{p}.log")
            with open(previouslogfile, "r") as f:
                previouslog = json.load(f)
            return MJournalChange.fromJson(previouslog[self.__change__],self.changeFactoryClass)
        return None

    def previousPath(self) -> str:
        """ Path for the previous change. """
        p = self.previous()
        if p:
            return os.path.join(self.dir,p)
        return None

    def add(self, change: MJournalChange) -> str:
        """
        A new change after the most resent change to become the
        current change.
        Insert order: (3)ThisLog -> (1)NewLog -> (2)NextLog.
        """
        newUuid = str(uuid.uuid4())
        newlogfile = os.path.join(self.dir,f"{newUuid}.log")
        nextUuid = self.log[self.__next__]
        thisUuid = self.log[self.__this__]
        # 1 Newlog is created first and linked to next and previous.
        newlog = {
            self.__previous__: thisUuid,
            self.__this__: newUuid,
            self.__next__: nextUuid,
            self.__change__: change.json()
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
        Insert change as the first, make it the current change too.
        """
        self.moveToHead()
        return self.add(change)

    def delete(self) -> str:
        """
        Delete the current change, return path to the new current change.
        """
        if self.atHead():
            # No change to delete at the head of the journal.
            return None
        previousuuid = self.log[self.__previous__]
        nextuuid = self.log[self.__next__]
        uuid = self.log[self.__this__]
        previousfile = os.path.join(self.dir,f"{previousuuid}.log")
        with open(previousfile, "r") as f:
            previouslog = json.load(f)
        previouslog[self.__next__] = nextuuid
        with open(previousfile, "w") as f:
            json.dump(previouslog,f)
        if nextuuid:
            nextfile = os.path.join(self.dir,f"{nextuuid}.log")
            with open(nextfile, "r") as f:
                nextlog = json.load(f)
            nextlog[self.__previous__] = previousuuid
            with open(nextfile, "w") as f:
                json.dump(nextlog,f)
        os.unlink(os.path.join(self.dir,f"{uuid}.log"))
        shutil.rmtree(os.path.join(self.dir,uuid),ignore_errors=True)
        self.up()
        return os.path.join(self.dir,self.log[self.__this__])

    def prune(self):
        """ Deletes changes prior to Current, making current the new root. """
        current = self.current()
        self.rewind()
        while self.current() != current:
            self.delete()

    def rewind(self):
        """ Rewinds to the oldest change which is the first change after head. """
        with open(self.__headPath, "r") as f:
            headuuid = json.load(f)
        headfile = os.path.join(self.dir,f"{headuuid}.log")
        with open(headfile, "r") as f:
            headlog = json.load(f)
        uuid = headlog[self.__next__]
        if not uuid:
            self.log = headlog
            self.logfile = headfile
            uuid = headuuid
        else:
            self.logfile = os.path.join(self.dir,f"{uuid}.log")
            with open(self.logfile, "r") as f:
                self.log = json.load(f)
        with open(self.__currentPath, "w") as f:
            json.dump(uuid,f)

    def up(self) -> bool:
        """ Moves up to the newer change, think redo! """
        nextuuid = self.log[self.__next__]
        if not nextuuid:
            return False
        with open(self.__currentPath, "w") as f:
            json.dump(nextuuid,f)
        self.logfile = os.path.join(self.dir,f"{nextuuid}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        return True

    def down(self) -> bool:
        """ Moves down to the older change, think undo! """
        previousuuid = self.log[self.__previous__]
        if not previousuuid:
            return False
        with open(self.__currentPath, "w") as f:
            json.dump(previousuuid,f)
        self.logfile = os.path.join(self.dir,f"{previousuuid}.log")
        with open(self.logfile, "r") as f:
            self.log = json.load(f)
        return True

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Journal")
        parser.add_argument('dir', help="Journal dir")
        args = parser.parse_args()
        shutil.rmtree(args.dir)
        journal = MJournal(args.dir,MJournalChangeTestFactory)
        variables={"h":journal.headPath()}
        for cmd, data in [
            ("add",(MJournalChangeTest("test1"),"1")),("print",None),
            ("add",(MJournalChangeTest("test2"),"2")),("print",None),
            ("audit", None),
            ("del","1"), # Delete test2, returns test1.
            ("rewind",None),("print",None),
            ("down",True),("down",False),("print",None),
            ("up",True),("up",False),("print",None),
            ("rewind",None),
            ("del","h"), # Delete test1, return head.
            ("audit", None),("print",None),
            ("del",None),
            ("rewind",None),("print",None),
            ("add",(MJournalChangeTest("test3"),"3")),("print",None),
            ("insertRoot",(MJournalChangeTest("test4"),"4")),("print",None),
            ("insertRoot",(MJournalChangeTest("test5"),"5")),("print",None),
            ("audit", None),
            ("up",True),
            ("up",True),
            ("up",False),("print",None),
            ("down",True),
            ("down",True),
            ("down",True),
            ("down",False),("print",None),
            ("up",True),
            ("up",True),
            ("up",True),
            ("del","4"),("print",None),
            ("del","5"),("print",None),
            ("rewind",None),
            ("del","h"),
            ("audit", None),
            ("del",None),
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
                changePath=journal.add(data[0])
                variables[data[1]] = changePath
                with open(os.path.join(changePath,"tdump"),"w") as f:
                    json.dump(data[0].json(),f)
            elif cmd == "insertRoot":
                changePath=journal.insertRoot(data[0])
                variables[data[1]] = changePath
                with open(os.path.join(changePath,"tdump"),"w") as f:
                    json.dump(data[0].json(),f)
            elif cmd == "del":
                retval = journal.delete()
                if not data:
                    if retval != data:
                        raise Exception(f"Failed del {retval} != {data}")
                elif retval != variables[data]:
                    raise Exception(f"Failed del {retval} != {variables[data]}")
            elif cmd == "rewind":
                journal.rewind()
            elif cmd == "up":
                retval = journal.up()
                if retval != data:
                    raise Exception(f"Failed up {retval} != {data}")
            elif cmd == "down":
                retval = journal.down()
                if retval != data:
                    raise Exception(f"Failed down {retval} != {data}")
            else:
                raise Exception(f"Unknown cmd {cmd}")
                

if __name__ == "__main__":
    MJournal.main()