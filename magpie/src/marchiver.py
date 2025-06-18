import os
import datetime
import shutil
import copy


class ArchiveSubDir:
    """ Archive of files in nested subdir for example YYYY-MM-DD, or just YYYY,
        or no subdir. """

    """ Flags to activate subdirs. """
    YYYY=1
    mm=2
    DD=4
    HH=8
    MM=16
    SS=32
    NumberFlags=6

    def __init__(self,nesting:int):
        """ Examples,
                ArchiveSubDir()                    # files
                ArchiveSubDir(YYYY)                # YYYY/files
                ArchiveSubDir(YYYY|SS)             # YYYY/SS/files
                ArchiveSubDir(YYYY|MM|DD)          # YYYY/MM/DD/files
                ArchiveSubDir(YYYY|MM|DD|HH|MM|SS) # YYYY/MM/DD/HH/MM/SSfiles
        """
        self.nesting = nesting
        self.dirs = []
        self.depth = 0
        self.flags={self.YYYY:"YYYY",self.mm:"mm",self.DD:"DD",self.HH:"HH",self.MM:"MM",self.SS:"SS"}
        self.flagsFormat={
            self.YYYY:lambda dt:'{:4d}'.format(dt.year),
            self.mm:lambda dt: '{:02d}'.format(dt.month),
            self.DD:lambda dt: '{:02d}'.format(dt.day),
            self.HH:lambda dt: '{:02d}'.format(dt.hour),
            self.MM:lambda dt: '{:02d}'.format(dt.minute),
            self.SS:lambda dt: '{:02d}'.format(dt.second),
        }
        for f in self.flags.keys():
            if self.nesting & f:
                self.depth += 1
        self.depth += 1 # File in subdir.

    def __str__(self) -> str:
        flags="&".join([
            self.flags[flag]
            for flag in self.flags.keys()
            if self.nesting & flag
        ])
        return f"dirs={self.dirs} flags={flags} depth={self.depth}"

    def setDatetime(self,dt:datetime) -> None:
        self.dirs=[]
        for flag,fmt in self.flagsFormat.items():
            if self.nesting & flag:
                self.dirs.append(fmt(dt))

    def set(self,other:"ArchiveSubDir"):
        """ Reconstruct from another. """
        self.__init__(other.depth)
        self.dirs = copy.copy(other.dirs)

    def containFilename(self) -> bool:
        """ Return True when subdir contains filename. """
        return len(self.dirs) == self.depth

    def getPath(self) -> str:
        """ Return path including the filenanme if there is one. """
        if self.dirs: return os.path.join(*self.dirs)
        return ""

    def hasFilename(self) -> bool:
        return self.depth == len(self.dirs) 

    def getDir(self) -> str:
        """ Return path except the filename if there is one. """
        if self.dirs:
            if self.hasFilename():
                return os.path.join(*self.dirs[0:-1])
            else:
                return os.path.join(*self.dirs)
        return ""

    def cmp(self,other:"ArchiveSubDir") -> int:
        """ Self is newer = 1, older = -1, equal = 0. """
        for x in zip(self.dirs,other.dirs):
            if x[0] < x[1]: return -1
            if x[0] > x[1]: return 1
        # Note: zip is until the end of the shortest list, so check length.
        slen=len(self.dirs)
        olen=len(other.dirs)
        if olen > slen: return 1  # wildcard in self.
        if slen > olen: return -1 # no wildcard in other.
        return 0

    def datetimeOffset(self,dt:datetime.datetime,offset:int) -> datetime.datetime:
        """ Return datetime with offset. """
        if not offset: return dt
        if self.nesting & self.SS:
            return dt + datetime.timedelta(seconds=offset)
        if self.nesting & self.MM:
            return dt + datetime.timedelta(minutes=offset)
        if self.nesting & self.HH:
            return dt + datetime.timedelta(hours=offset)
        if self.nesting & self.DD:
            return dt + datetime.timedelta(days=offset)
        if self.nesting & self.mm:
            return dt + datetime.timedelta(minutes=offset)
        if self.nesting & self.YYYY:
            return dt.replace(year=dt.year+offset)
        return dt

    def setNow(self, offset:int) -> None:
        """ Set archive subdir to now plus offset at lowest nesting. """
        self.setDatetime(self.datetimeOffset(datetime.datetime.utcnow(),offset))

    def setEpoch(self, epoch:int) -> None:
        """ epoch is in UTC TZ. """
        e=datetime.datetime.fromtimestamp(epoch)
        self.setDatetime(e)

    def add(self,name:str) -> bool:
        """ Add subdir name to dirs. """
        self.dirs.append(name)
        assert len(self.dirs) <= self.depth+1

    def remove(self):
        """ Remove last added subdir name from dirs. """
        assert len(self.dirs) > 0
        self.dirs.pop()


class Guide():
    """ Base for walking all files. """
    def __init__(self,nesting:int):
        self.subdir=ArchiveSubDir(nesting)
    
    def isYield(self) -> bool:
        return self.subdir.containFilename()

    def yieldValue(self) -> ArchiveSubDir:
        """ Value to yield for this subdir. """
        yield self.subdir

    def isStepInto(self) -> bool:
        """ Step into self.subdir. """
        return True

    def continueNext(self) -> bool:
        """ Continue scanning directory. """
        return True

    def isPostStepInto(self) -> bool:
        """ After scanning directory, will step into self.subdir. """
        return False


class GuideRange(Guide):
    """ Walking files inclusively between the range of newer and older. """
    def __init__(self, nesting:int, newer:ArchiveSubDir=None, older:ArchiveSubDir=None):
        super().__init__(nesting)
        self.older = older
        self.newer = newer

    def isStepInto(self) -> bool:
        if self.newer:
            newer = (self.subdir.cmp(self.newer) >= 0)
        else:
            newer = True
        if self.older:
            older = (self.subdir.cmp(self.older) <= 0)
        else:
            older = True
        return newer and older


class GuideFileFromOldestArchive(Guide):
    """ Find first file in oldest archive. """
    def __init__(self, nesting:int):
        super().__init__(nesting)
        self.oldest = None
        self.done = False

    def isStepInto(self,nesting:int) -> bool:
        """ Don't step into subdir, but find oldest in current subdir. """
        if not self.oldest:
            self.oldest = ArchiveSubDir(nesting)
            self.oldest.set(self.subdir)
        elif self.subdir.cmp(self.oldest) < 0:
            self.oldest.set(self.subdir)
        return False

    def isPostStepInto(self) -> bool:
        """ Post loop, step into oldest subdir. """
        if not self.oldest: return False
        if self.fn: return False
        self.subdir.set(self.oldest)
        return True

    def yieldValue(self) -> ArchiveSubDir:
        self.done = True
        yield from super().yieldValue()

    def continueNext(self) -> bool:
        """ Stop after the first file. """
        return not self.done


class MArchiver():
    """ Archive files by file modified time in subdirs.
    """
    def __init__(self,
                 archivePath:str,
                 nesting:int=(ArchiveSubDir.YYYY |
                              ArchiveSubDir.mm |
                              ArchiveSubDir.DD),
                 ageoff:int=3,
                 diskPercentage=70):
        """ archivePath: root dir for the archive.
            nesting: flags to control ArchiveSubDir
            ageoff: ageoff interms of the lowest nesting.
        """
        self.archivePath = archivePath
        self.nesting=nesting
        self.ageoff=ageoff
        self.setDiscThreshold(diskPercentage)
        self._getThreshold() # Test nesting and ageoff.
        # archiveDev: device containing the root dir.
        self.archiveDev = os.lstat(archivePath).st_dev

    def __str__(self) -> str:
        return f"archive={self.archivePath} threshold={self._getThreshold()}"

    @classmethod
    def notItem(cls,entry) -> bool:
        """ Helper: Return True when entry is hidden. """
        return entry.name.startswith(".")
        # not entry.is_file() and not entry.is_dir() )

    @classmethod
    def ls(cls,p:str) -> (datetime.datetime,str):
        """ Helper: walk dir and subdir, yielding file mtime + path. """
        with os.scandir(p) as it:
            for entry in it:
                if entry.name.startswith("."): continue
                x = os.path.join(p,entry.name)
                if entry.is_dir():
                    yield from cls.ls(x)
                else:
                    mtime = os.path.getmtime(x)
                    dt = datetime.datetime.fromtimestamp(mtime)
                    yield (dt, x)

    @classmethod
    def _isemptyDir(cls,p:str) -> bool:
        """ Helper: Return True when path is an empty dir """
        with os.scandir(p) as it: return not any(it)

    def setAgeoff(self,ageoff:int):
        self.ageoff = ageoff
        self._getThreshold() # Test nesting and ageoff.

    def archive(self, fn:str) -> bool:
        """ Move file (fn) into the archive. """
        if not os.path.exists(fn): return False
        archiveSubDir = self.fileArchive(fn)
        if archiveSubDir.cmp(self._getThreshold()) <= 0: return False
        filesize=os.path.getsize(fn)
        while self._exceedDiscUsage(filesize):
            if not self.purgeFile(archive=archiveSubDir): return False
        archive = self._getPath(archiveSubDir.getDir())
        os.makedirs(archive, exist_ok=True)
        self._fileRename(fn,os.path.join(archive,os.path.basename(fn)))
        return True

    def _getThreshold(self) -> ArchiveSubDir:
        archiveSubDir = ArchiveSubDir(self.nesting)
        archiveSubDir.setNow(-self.ageoff)
        return archiveSubDir

    def purgeFile(self,archive:ArchiveSubDir=None) -> bool:
        """ Delete the oldest file.
            Delete the oldest day archive when it is empty after file delete.
            If archive, delete file only when it is older than archive.
            Return True when a file was purged.
        """
        oldest = self._oldest()
        while oldest:
            p = self._getPath(oldest.getPath())
            if not oldest.containFilename(): # Delete empty subdir.
                shutil.rmtree(p)
                oldest = self._oldest()
                continue
            if archive and archive.cmp(oldest) < 0: return False
            os.remove(p)
            p = self._getPath(oldest.getDir())
            if not next(self.ls(p),None): # Delete empty subdir.
                shutil.rmtree(p)
            return True

    def purge(self) -> bool:
        """ Purge oldest subdirs in the archive. Purge when filesystem has
            exceeded the disc usage. Or, purge when the oldest day has
            exceeded the age off limit.
            Return True when one or more subdirs were purged.
        """
        retval = False
        while self._exceedDiscUsage():
            oldest = self._oldest()
            if not oldest: return retval
            shutil.rmtree(self._getPath(oldest.getDir()))
            retval = True
        threshold = self._getThreshold()
        oldest = self._oldest()
        while oldest:
            if oldest.cmp(threshold) > 0: return retval
            shutil.rmtree(self._getPath(oldest.getDir()))
            retval = True
            oldest = self._oldest()
        return retval

    def walk(self) -> str:
        """ Walk all files in the archive. """
        for d in self._walk(guide=Guide(self.nesting)):
            yield self._getPath(d.getPath())

    def setDiscThreshold(self,threshold:int):
        if threshold < 20 or threshold > 100:
            raise Exception(f"Dont understand threshold percentage of {threshold}")
        self.discThreshold = threshold

    def oldest(self) -> str:
        """ Return path to oldest file in the archive. """
        oldest = self._oldest()
        if oldest: return self._getPath(oldest[0].getDir(),oldest[1])
        return None

    def getArchiveSubDir(self,offset:int) -> ArchiveSubDir:
        """ Helper: get ArchiveSubDir for archive nesting. """
        archiveSubDir = ArchiveSubDir(self.nesting)
        dt = datetime.datetime.utcnow()
        dt = archiveSubDir.datetimeOffset(dt,offset)
        archiveSubDir.setDatetime(dt)
        return archiveSubDir

    def fileArchive(self,fn:str) -> ArchiveSubDir:
        """ Helper: get ArchiveSubDir from the utc mtime of file at fn. """
        mtime = os.path.getmtime(fn)
        dt = datetime.datetime.fromtimestamp(mtime)
        archiveSubDir = ArchiveSubDir(self.nesting)
        archiveSubDir.setDatetime(dt)
        return archiveSubDir

    def _getPath(self,*args) -> str:
        """ Helper: add archive root to args, to return full a path."""
        return os.path.join(self.archivePath, *args)

    def _exceedDiscUsage(self,filesize:int=0) -> bool:
        """ Helper: return True when disc usage exceeds limits. """
        if not self.discThreshold: return False
        (total,used,free) = shutil.disk_usage(self.archivePath)
        used += filesize
        p=int(used*100/total)
        return p > self.discThreshold

    def _fileRename(self,fn:str,to:str) -> None:
        """ Helper: rename works on the same device, otherwise
            use the more expensive copy/remove. """
        if os.lstat(fn).st_dev == self.archiveDev:
            os.rename(fn,to)
        else:
            shutil.copyfile(fn,to)
            os.remove(fn)

    def _walk(self, guide:Guide) -> ArchiveSubDir:
        """ Helper: Walk a dir in the archive. """
        p = self._getPath(guide.subdir.getDir())
        with os.scandir(p) as it:
            for entry in it:
                if self.notItem(entry): continue
                guide.subdir.add(entry.name)
                if guide.subdir.containFilename():
                    yield from guide.yieldValue()
                else:
                    yield from self._walk(guide)
                if not guide.continueNext(): return
                guide.subdir.remove()
        if guide.isPostStepInto(): yield from self._walk(guide)

    def _oldest(self) -> ArchiveSubDir:
        """ Helper: return the oldest file in the archive. """
        i = self._walk(GuideFileFromOldestArchive(self.nesting))
        return next(i,None)