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
import os.path
import json
import re
import time
import uuid
import posix

# ProcessFile exists while a file is being processed.
# The name of the ProcessFile includes the name of the file being
# processed, starts with the prefix and followed by the file name.
# i.e. processfile = <prefix><filename>
class ProcessFile():
    processFilePrefix = ".processfile_"
    processFilePrefixLen = len(".processfile_")

    @staticmethod
    def factory(de: posix.DirEntry, filePath: str) -> (bool, "ProcessFile"):
        if not de.name.startswith(ProcessFile.processFilePrefix):
            return False, None
        if len(de.name) == ProcessFile.processFilePrefixLen:
            return True, None
        file = os.path.join(filePath,de.name[ProcessFile.processFilePrefixLen:])
        if not os.path.isfile(file):
            os.remove(de.path)
            return True, None
        pf = ProcessFile(
            processFileDir=os.path.dirname(de.path),
            filePath=filePath
        )
        if pf.isExpired():
            os.remove(de.path)
            return True, None
        return True, pf

    @staticmethod
    def fileToProcessFile(filename: str) -> str:
        return ProcessFile.processFilePrefix+filename

    def __init__(self, processFileDir: str, filePath: str):
        self.processFilePath = os.path.join(processFileDir,".processfile_"+os.path.basename(filePath))
        if os.path.isfile(self.processFilePath):
            with open(self.processFilePath,"r") as f:
                self.__dict__ = json.loads(next(f,"{}"))
            self.fileSync = True
        else:
            self.fileSync = False
            self.uuid = str(uuid.uuid4())
            self.path = filePath
            self.found = int(time.time())
            self.processing = 0
            self.processed = 0
            self.write()

    # Return True when the processfile on disk has the same UUID
    # as the processfile in memory, i.e. this process owns the
    # processfile on disk.
    def ownFile(self) -> bool:
        with open(self.processFilePath,"r") as f:
            line = next(f)
            if len(line) == 0:
                return True
            d = json.loads(line)
            return d["uuid"] == self.uuid

    def remove(self) -> None:
        os.remove(self.processFilePath)
        self.processFilePath = None

    # Return True when this FILES has the same processfile, returns False
    # when another FILES has taken control of the processFile.
    def write(self) -> bool:
        """
        Write handles the problem of two FILES at the same time want to own
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
                if not self.ownFile():
                    return
                # Cannot have an empty processfile, so create a tempfile
                # and use the atomic rename command.
                tempfile = self.processFilePath+"_"+uuid.uuid4()
                with open(tempfile,"w") as f:
                    json.dump(self.__dict__,f)
                    os.rename(tempfile,self.processFilePath)
                    return True
            with open(self.processFilePath,"a+") as f:
                line = json.dumps(self.__dict__,f)+"\n"
                f.write(line)
            self.fileSync = self.ownFile()
        except Exception:
            # WindowsOS raises an Exception in the second process that
            # appends to the same file.
            # No exception on Linux, two processes can write to the same file.
            # Relevant note about Linux: If the O_APPEND flag of the file
            # status flags is set, the file offset shall be set to the end of
            # the file prior to each write and no intervening file modification
            # operation shall occur between changing the file offset and the
            # write operation.
            pass

    def processing(self) -> None:
        self.processing = time.time()
        self.write()

    def isExpired(self) -> bool:
        return self.processing + 600 < time.time()

    def isProcessing(self) -> bool:
        return self.processing != 0

    def isDone(self) -> bool:
        return self.processed != 0


# Files uses os.path.getmtime(), it returns an accurate timestamp for the
# last time a directory was changed. Initially, Files scans all of the
# directories, and caches in memory the path to the file that have not
# been processed before. Next execution of Files, looks for changes in
# the known directories. A different directory modified time, requires a
# rescan of that directory looking for the new or removed files, and
# the in memory cache is updated.
class Files(Cmd):
    def __init__(self, cmd: dict):
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

    def setPath(self,path:str) -> None:
        if not path.startswith(self.path):
            raise Exception("Path must start with "+self.path+" path="+path)
        self.cntPath = path
        if self.coupled:
            self.cntProcPath = path
        else:
            self.cntProcPath = os.path.join(self.readonly,path[len(self.path):])
        self.cntDepth = self.pathDepth(path) - self.depth

    def srtPath(self) -> None:
        self.cntPath = self.path
        self.cntProcPath = self.readonly
        self.cntDepth = self.depth

    def nxtPath(self,de: posix.DirEntry) -> bool:
        if self.cntDepth == 0:
            raise False
        if self.coupled:
            self.cntProcPath = de.path
        else:
            self.cntProcPath = os.path.join(self.readonly,de.path[len(self.path):])
        self.cntPath = de.path
        self.depth -= 1

    def prvPath(self) -> bool:
        if self.cntDepth > self.depth:
            raise False
        self.cntPath = os.path.dirname(self.cntPath)
        if self.coupled:
            self.cntProcPath = self.cntPath
        else:
            self.cntProcPath = os.path.dirname(self.cntProcPath)
        self.depth += 1

    def __str__(self) -> str:
        return "path=%s readonly=%s depth=%d feeds=%s" % (
                self.path,
                str(self.readonly),
                self.depth,
                str(self.feeds))

    def schema(self) -> list:
        return ["stream", "process-file",]

    def sample(self, feedName: str, n:int) -> (bool, dict):
        i = 0
        if feedName:
            for feed in self.feeds:
                if feed["feed"] == feedName:
                    if i > n:
                        break
                    for modifiedTime in sorted(feed["order"]):
                        for pn in feed["order"][modifiedTime]:
                            i += 1
                            if i > n:
                                break
                            yield (i == n, pn)
        else:
            j = n / len(self.feeds)
            if j == 0:
                j = 1
            kfeeds = {}
            for feed in self.feeds:
                f = feed["feed"]
                kfeeds[f] = 0
                for modifiedTime in sorted(feed["order"]):
                    if i > n:
                        break
                    for pn in feed["order"][modifiedTime]:
                        i += 1
                        if i > n:
                            break
                        yield (i == n, {"feed": f, "file": pn})
                        if kfeeds[f] == j:
                            break
                        kfeeds[f] += 1
                    if kfeeds[f] == j:
                        break
            for feed in self.feeds:
                f = feed["feed"]
                j = 0
                for modifiedTime in sorted(feed["order"]):
                    if i > n:
                        break
                    for pn in feed["order"][modifiedTime]:
                        if i > n:
                            break
                        if j > kfeeds[f]:
                            i += 1
                            if i > n:
                                break
                            yield (i == n,{"stream": f, "file": pn})
        if i < n:
            yield(True, None)

    # Avoid re-scanning a directory that has not changed by tracking
    # directory's modification time in path_mtimes, which changes
    # when directory changes i.e. something added/removed in the directory.
    def execute(self) -> None:
        if len(self.path_mtimes) == 0:
            self.srtPath()
            self.initialDirScan()
        else:
            self.maintenanceDirScan()

    def removeNest(self, dir: str) -> None:
        for de in os.scandir(dir):
            if de.is_dir():
                self.removeNest(de.path)
            else:
                os.remove(de.path)
        os.remove(dir)

    def addFileToFeed(self, path: str, mtime: int) -> None:
        print("addFileToFeed "+path)
        for feed in self.feeds:
            o = feed["order"]
            if feed["regex"].match(path):
                print(str(mtime)+" "+path)
                o.setdefault(mtime,set()).add(path)
                return True
        return False

    # Read files into memory, process subdir upto self.depth.
    # Keep track of path's modified timestamp.
    def initialDirScan(self) -> None:
        print("initialDirScan %s %s %d" % (self.cntProcPath,self.cntPath,self.cntDepth))
        if not os.path.isdir(self.cntPath):
            raise Exception("No such directory "+self.cntPath)
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
                self.prvPath(de)
        if not self.coupled:
            self.cleanupProcessPath(processfiles)

    # Scan processpath, cleanup processfile using factory(). 
    def cleanupProcessPath(self,
       processpath: str, filepath: str, processfiles: set)  -> None:
        for de in os.scandir(processpath):
            if de.path not in processfiles:
                ProcessFile.factory(de,filepath)
            if de.is_dir():
                if not os.path.isdir(filepath):
                    self.recursiveRemove(os.path.join(processpath,de.name))

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
    def purgeCacheForModifiedDir(self, dirpath: str) -> None:
        for feed in self.feeds:
            o = feed["order"]
            newo = {}
            for mtime, l in o.items():
                # Dont rebuild the set unless it is needed.
                rebuild = False
                for path in l:
                    if path.startswith(dirpath):
                        rebuild = True
                        break
                if rebuild:
                    newl = set()
                    for path in l:
                        if not path.startswith(dirpath):
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
    def maintenanceDirScan(self) -> None:
        print("maintenanceDirScan")
        path_mtimes = self.path_mtimes
        self.path_mtimes = {}
        
        for filepath, mtime in path_mtimes.items():
            current_mtime = os.path.getmtime(filepath)
            print("path="+filepath+" mtime="+str(current_mtime))
            if mtime != current_mtime: # Directory has changed.
                print("dir changed "+filepath)
                processpath = self.getProcessPath(filepath)
                self.cleanupProcessPath(processpath,filepath,set())
                self.purgeCacheForModifiedDir(filepath)
                self.path_mtimes[filepath] = current_mtime
                for de in os.scandir(filepath):
                    if de.is_file():
                        self.addFileToFeed(de.path, os.path.getmtime(de.path))
                    elif (de.is_dir()
                          and de.path not in path_mtimes
                          and self.pathDepth(de.path) <= self.depth
                    ):
                        self.setPath(filepath)
                        self.initialDirScan()
        tmp = self.path_mtimes
        self.path_mtimes = path_mtimes
        for k,v in tmp.items():
            self.path_mtimes[k] = v

    @staticmethod
    def main():
        """
        parser = argparse.ArgumentParser(description="Wi")
        parser.add_argument('--dir', help="worksheet dir")
        parser.add_argument('--hdir', help="hall dir")
        parser.add_argument('-d', '--debug', help="activate debugging", action="store_true")
        args = parser.parse_args()
        """
        cmd = {
        "root": "test",
        "path": {
            "path": "test/Hallelulajah/pcap",
            "depth": 1,
            "readonly": "test/Hallelulajah/pcap_processed",
            "feeds": [
                {"feed": "test.pcap", "regex": ".*\\.pcap"},
                {"feed": "test.new", "regex": ".*"}
            ]
        }
        }
        files = Files(cmd)
        print(files)
        for i in range(10):
            print(i)
            files.execute()
            for (b,d) in files.sample(feedName=None,n=10):
                print("yield")
                print(b)
                print(d)
            print(files)
            time.sleep(3)
        

if __name__ == "__main__":
    Files.main()
