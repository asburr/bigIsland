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
from hallelujah.cmds.cmd import Cmd
import os.path
import json
import re
import time
import uuid
import posix
import traceback


class ProcessFile():
    """
    ProcessFile exists while a file is being processed.
    The name of the ProcessFile includes the name of the file being
    processed, starts with the prefix and followed by the file name.
    i.e. processfile = <prefix><filename>
    """
    processFilePrefix = ".processfile_"
    processFilePrefixLen = len(".processfile_")

    def __init__(self, processFileDir: str, filePath: str):
        """
        Create a processFile for filePath.
        Reads processFile when it already exists, otherwise creates a
        new processFile using atomicWrite() which prevents two processes
        creating the same file. fileSync is False when another process
        created the processFile first, and ProcessFile should not be
        used in this case.
        """
        self.processFilePath = processFilePath = os.path.join(
            processFileDir,
            ProcessFile.processFilePrefix+os.path.basename(filePath)
        )
        if os.path.isfile(processFilePath):
            self.fileSync = False
            with open(processFilePath,"r") as f:
                self.__dict__ = json.loads(next(f,"{}"))
            self.fileSync = len(self.__dict__) > 0
            # Something wrong with file, could be empty, remove it.
            if not self.fileSync:
                os.remove(processFilePath)
        else:
            self.fileSync = False
            self.uuid = str(uuid.uuid4())
            self.path = filePath
            self.found = int(time.time())
            self.processing = 0
            self.processed = 0
            self.fileSync = self.atomicWrite()

    def __str__(self) -> str:
        if self.fileSync:
            return "%d,%s,%s"%(self.fileSync,self.uuid,self.path)
        return "%d"%self.fileSync

    @staticmethod
    def factory(pfentry: posix.DirEntry, filePath: str) -> (bool, "ProcessFile"):
        """
        factory() creates ProcessFile object from an existing file (dirEntry).
        Return False when entry is not a the name of a process file.
        Return True and None when process file expired/no-associated-file and dirEntry is deleted.
        Return True and ProcessFile when process file exists/was-created.
        """
        if not pfentry.name.startswith(ProcessFile.processFilePrefix):
            return False, None
        if len(pfentry.name) == ProcessFile.processFilePrefixLen:
            return False, None
        file = os.path.join(filePath,pfentry.name[ProcessFile.processFilePrefixLen:])
        if not os.path.isfile(file):
            os.remove(pfentry.path)
            return True, None
        pf = ProcessFile(
            processFileDir=os.path.dirname(pfentry.path),
            filePath=filePath
        )
        if not pf.fileSync:
            return True, None
        if pf.isExpired():
            os.remove(pfentry.path)
            return True, None
        return True, pf

    @staticmethod
    def fileToProcessFile(filename: str) -> str:
        return ProcessFile.processFilePrefix+filename

    def ownFile(self) -> bool:
        """
        Return True when the processfile on disk has the same UUID
        as the processfile in memory, i.e. this process owns the
        processfile on disk.
        """
        with open(self.processFilePath,"r") as f:
            line = next(f)
            if len(line) == 0:
                return True
            d = json.loads(line)
            return d["uuid"] == self.uuid

    def remove(self) -> None:
        os.remove(self.processFilePath)
        self.processFilePath = None

    def atomicWrite(self) -> bool:
        """
        Return True when this FILES has the same processfile, returns False
        when another FILES has taken control of the processFile.
        atomicWrite handles the problem of two FILES at the same time want to own
        the same file, and both writing the same process-file at the same
        time.
        The solution is Linux specific: Both processes write to the same
        file using the append mode,  and both write their information into
        the same file, for example,
            with open("test","a+") as f:
                s=json.dumps({"uuid": str(uuid.uuid4())})+"\n"
                f.write(s)
        And the file contains:
            {"uuid": "a543f775-e1d7-4434-8ea7-97c2a0fdffcb"}
            {"uuid": "0ccf3e89-eabd-4005-99ef-f57a72f1ea67"}
        Obviously one of the processes got there first, their UUID value
        is first in the file, and the other UUID from the other process
        is second in the file.
        So, both processes read test to see if their UUID is the first in
        the file, for example,
            with open("crappy","r") as f:
               print(json.loads(next(f)))
            {'uuid': 'a543f775-e1d7-4434-8ea7-97c2a0fdffcb'}
        When the UUID matches, the process has the file. When the UUID does
        not match, the process does not have the file.
        """
        try:
            if os.path.isfile(self.processFilePath):
                return self.ownFile()
            with open(self.processFilePath,"a+") as f:
                line = json.dumps(self.__dict__)+"\n"
                f.write(line)
            return self.ownFile()
        except Exception:
            traceback.print_exc()
            # WindowsOS raises an Exception in the second process that
            # appends to the same file.
            # No exception on Linux, two processes can write to the same file.
            # Relevant note about Linux: If the O_APPEND flag of the file
            # status flags is set, the file offset shall be set to the end of
            # the file prior to each write and no intervening file modification
            # operation shall occur between changing the file offset and the
            # write operation.
            return False

    def processing(self) -> None:
        if not self.fileSync:
            return
        self.processing = time.time()
        # delete and recreate would leave an empty processfile, instead create
        # a tempfile and use the atomic rename command.
        tempfile = self.processFilePath+"_"+uuid.uuid4()
        with open(tempfile,"w") as f:
            json.dump(self.__dict__,f)
            os.rename(tempfile,self.processFilePath)

    def isExpired(self) -> bool:
        return self.processing + 600 < time.time()

    def isProcessing(self) -> bool:
        return self.processing != 0

    def isDone(self) -> bool:
        return self.processed != 0


class Files(Cmd):
    """
    Files: uses os.path.getmtime(), it returns an accurate timestamp for the
    last time a directory was changed. Initially, Files scans all of the
    directories, and caches in memory the path to the file that have not
    been processed before. Next execution of Files, looks for changes in
    the known directories. A different directory modified time, requires a
    rescan of that directory looking for the new or removed files, and
    the in memory cache is updated.
    """
    def __init__(self, cmd: dict):
        super().__init__()
        self.path=cmd["path"]["path"]
        self.readonly=cmd["path"].get("readonly",self.path)
        self.depth=cmd["path"]["depth"]
        self.feeds = []
        for feed in cmd["path"]["feeds"]:
            self.feeds.append({
                "feed": feed["feed"],
                "regex": re.compile(feed["regex"], re.IGNORECASE),
                "order": {}
            })
        if len(self.feeds) == 0:
            raise Exception("Files has no feeds!")
        self.path_mtimes = {}  # Modified times for root path and subdirs.
        self.cntPath = self.path
        self.cntProcPath = self.readonly
        self.coupled = self.path == self.readonly
        self.cntDepth = self.depth
        self.debug = False

    # Starts Files at the root paths.
    def srtPath(self) -> None:
        self.cntPath = self.path
        self.cntProcPath = self.readonly
        self.cntDepth = self.depth

    # Change dir for Files, to a path within the root path.
    def setPath(self,path:str) -> None:
        if not path.startswith(self.path):
            raise Exception("Path must start with "+self.path+" path="+path)
        self.cntPath = path
        if self.coupled:
            self.cntProcPath = path
        else:
            # path.join returns 2nd param when it starts with a slash(/),
            # so +1 is needed.
            self.cntProcPath = os.path.join(self.readonly,path[len(self.path)+1:])
        self.cntDepth = self.pathDepth(path) - self.depth

    # Change dir for Files, into a subdir of the current dir.
    def nxtPath(self,de: posix.DirEntry) -> bool:
        if self.cntDepth == 0:
            return False
        if self.coupled:
            self.cntProcPath = de.path
        else:
            # path.join returns 2nd param when it starts with a slash(/),
            # so +1 is needed.
            self.cntProcPath = os.path.join(self.readonly,de.path[len(self.path)+1:])
        self.cntPath = de.path
        self.cntDepth -= 1

    # Change dir for Files, out of a subdir and back into the parent dir.
    def prvPath(self) -> None:
        if self.cntDepth > self.depth:
            raise Exception("too many prvPath compared to nxtPath "+str(self.cntDepth))
        self.cntPath = os.path.dirname(self.cntPath)
        if self.coupled:
            self.cntProcPath = self.cntPath
        else:
            self.cntProcPath = os.path.dirname(self.cntProcPath)
        self.cntDepth += 1

    def __str__(self) -> str:
        return "path=%s readonly=%s depth=%d feeds=%s" % (
                self.path,
                str(self.readonly),
                self.depth,
                str(self.feeds))

    def data(self, feedName: str, n:int) -> list:
        ret = []
        if n <= 0:
            return ret
        i = 0
        for feed in self.feeds:
            if feed["feed"] == feedName:
                for modifiedTime in sorted(feed["order"]):
                    j = len(ret)
                    for pn in feed["order"][modifiedTime]:
                        pf = ProcessFile(
                            processFileDir=self.cntProcPath,
                            filePath=pn
                        )
                        if pf.fileSync:
                            i += 1
                            ret.append(pn)
                            if i == n:
                                break
                    # Remove process file that are to be returned.
                    for pn in ret[j:]:
                        feed["order"][modifiedTime].remove(pn)
                    if i == n:
                        return ret
        return ret

    def execute(self) -> bool:
        """
        Avoid re-scanning a directory that has not changed by tracking
        directory's modification time in path_mtimes, which changes
        when directory changes i.e. something added/removed in the directory.
        """
        if len(self.path_mtimes) == 0:
            self.srtPath()
            self.initialDirScan()
        else:
            self.maintenanceDirScan()
        return False  # 

    @classmethod
    def removeNest(cls, dir: str) -> None:
        for de in os.scandir(dir):
            if de.is_dir():
                cls.removeNest(de.path)
            else:
                os.remove(de.path)
        os.rmdir(dir)

    def addFileToFeed(self, path: str, mtime: int) -> None:
        for feed in self.feeds:
            o = feed["order"]
            if feed["regex"].match(path):
                self.disco.load(path)
                o.setdefault(mtime,set()).add(path)
                return True
        return False

    # Read files into memory, process subdir upto self.depth.
    # Keep track of path's modified timestamp.
    def initialDirScan(self) -> None:
        # print("initialDirScan %s %s %d" % (self.cntProcPath,self.cntPath,self.cntDepth))
        if not os.path.isdir(self.cntPath):
            # raise Exception("No such directory "+self.cntPath)
            return
        if not os.path.isdir(self.cntProcPath):
            os.mkdir(path=self.cntProcPath)
        self.path_mtimes[self.cntPath] = os.path.getmtime(self.cntPath)
        processfiles = set()
        # scandir returns hidden files (dot files), but not current dir (.)
        # and parent dir (..).
        for de in os.scandir(self.cntPath):
            if de.is_file():
                # When coupled, scandir also finds the process files. Process
                # File factory removes the file when it should not exist and
                # returns False, and returns the ProcessFile object and True
                # when it exists.
                if self.coupled:
                    (isPFilename, pFile) = ProcessFile.factory(de,self.cntPath)
                    if isPFilename:
                        if pFile:
                            processfiles.add(pFile.path)
                        continue
                self.addFileToFeed(de.path, os.path.getmtime(de.path))
            elif de.is_dir() and self.cntDepth > 0:
                self.nxtPath(de)
                self.initialDirScan()
                self.prvPath()
        if not self.coupled:
            self.cleanupProcessPath(processfiles)

    # Scan processpath, cleanup processfile using factory(). 
    def cleanupProcessPath(self, processfiles: set)  -> None:
        for de in os.scandir(self.cntProcPath):
            if de.path not in processfiles:
                ProcessFile.factory(de,self.cntPath)
            if de.is_dir():
                if not os.path.isdir(self.cntPath):
                    self.recursiveRemove(os.path.join(self.cntProcPath,de.name))

    # No os.path.depth()?
    def pathDepth(self, path: str) -> int:
        depth = 0
        while len(path) > 0:
            depth += 1
            path=os.path.dirname(path)
        return depth

    # To be called when a directory has changed, to purge from memory all
    # of the files in the directory. This is accomplished by looking through
    # the feeds, the mtimes in each feed, and purge when the dirpath is in
    # the filepath.
    def purgeCacheForModifiedDir(self) -> None:
        for feed in self.feeds:
            o = feed["order"]
            newo = {}
            for mtime, l in o.items():
                # Dont rebuild the set unless it is needed.
                rebuild = False
                for path in l:
                    if path.startswith(self.cntPath):
                        rebuild = True
                        break
                if rebuild:
                    newl = set()
                    for path in l:
                        if not path.startswith(self.cntPath):
                            newl.add(path)
                    if len(newl) > 0:
                        newo[mtime] = newl
                else:
                    newo[mtime] = l
            feed["order"] = newo

    # Check the directory's mtime in memory with the mtime on disk, to detect
    # changes in the directory.
    # Purge the in memory cache for the directory, and rebuild this cache, and
    # resync the processFiles too. Also, run the initialDirScan for any new
    # subdirs.
    def maintenanceDirScan(self) -> bool:
        path_mtimes = self.path_mtimes
        self.path_mtimes = {}
        for filepath, mtime in path_mtimes.items():
            try:
                current_mtime = os.path.getmtime(filepath)
            except FileNotFoundError:  # Directory removed!
                continue
            if mtime != current_mtime: # Directory has changed.
                # print("dir changed "+filepath)
                self.setPath(filepath)
                self.cleanupProcessPath(set())
                self.purgeCacheForModifiedDir()
                self.path_mtimes[filepath] = current_mtime
                for de in os.scandir(filepath):
                    if de.is_file():
                        self.addFileToFeed(de.path, os.path.getmtime(de.path))
                    elif (de.is_dir()
                          and de.path not in path_mtimes
                          and self.pathDepth(de.path) <= self.depth
                    ):
                        self.nxtPath(de)
                        self.initialDirScan()
        tmp = self.path_mtimes
        self.path_mtimes = path_mtimes
        for k,v in tmp.items():
            self.path_mtimes[k] = v