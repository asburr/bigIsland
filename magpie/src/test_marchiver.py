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
import unittest
from tempfile import TemporaryDirectory
from magpie.src.marchiver import ArchiveSubDir, MArchiver
import os
import datetime
import shutil
from unittest.mock import MagicMock


class TestArchiver(unittest.TestCase):
    archivePath = None

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    @staticmethod
    def touch(fpath:str,mtimeEpoch:int):
        from pathlib import Path
        Path(fpath).touch()
        os.utime(path=fpath,times=(0.0,mtimeEpoch))
        # x=os.path.getmtime(fpath)
        # print(f"touch {fpath} {mtimeEpoch} {x}")

    def setUp(self):
        self.archivePath = TemporaryDirectory()
        self.inputPath = TemporaryDirectory()
        self.YearNesting = ArchiveSubDir.YYYY
        self.MonthNesting = self.YearNesting|ArchiveSubDir.mm
        self.DayNesting = self.MonthNesting|ArchiveSubDir.DD
        self.HourNesting = self.DayNesting|ArchiveSubDir.HH
        self.MinuteNesting = self.HourNesting|ArchiveSubDir.MM
        self.SecondNesting = self.MinuteNesting|ArchiveSubDir.SS
        self.files=[]
        self.archiveSubDirs=[]
        self.dt=[]
        self.archived=[]
    
    def setupNesting(self,nesting:int):
        self.archiver = MArchiver(self.archivePath.name,nesting,ageoff=3)
        archiveSubDir = self.archiver.getArchiveSubDir(0)
        dt = datetime.datetime.utcnow()
        # files[i] in the past by "i" days into inputPath.
        # archived[i] is the expected location of file[i].
        for i in range(4):
            self.files.append(os.path.join(self.inputPath.name,f"file{i}"))
            self.dt.append(archiveSubDir.datetimeOffset(dt,offset=-i))
            self.archiveSubDirs.append(self.archiver.getArchiveSubDir(offset=-i))
            self.touch(self.files[i],self.dt[i].timestamp())
            self.archived.append(os.path.join(
                self.archivePath.name,
                self.archiver.fileArchive(self.files[i]).getPath(),f"file{i}"))
        # files[j] in the past by "i" years into inputPath.
        for i in range(4,8):
            self.files.append(os.path.join(self.inputPath.name,f"file{i}"))
            self.dt.append(archiveSubDir.datetimeOffset(dt,offset=-i))
            self.archiveSubDirs.append(self.archiver.getArchiveSubDir(offset=-i))
            self.touch(self.files[i],self.dt[i].timestamp())
            self.archived.append(os.path.join(
                self.archivePath.name,
                self.archiver.fileArchive(self.files[i]).getPath(),f"file{i}"))
        shutil.disk_usage=MagicMock(return_value=(100,0,100)) # Total,used,free

    def printFiles(self):
        for i in range(8):
            print(f"{i}:{self.files[i]} {self.archived[i]} {self.archiveSubDirs[i]}")

    def listFiles(self):
        for x in MArchiver.ls(self.archiver.archivePath): print(x)

    def getArchive(self) -> list:
        return sorted([ x for x in self.archiver.walk()], key=lambda n:os.path.basename(n))
        
    def test_archiveFile(self):
        self.setupNesting(self.DayNesting)
        self.archiver.archive(self.files[0])
        self.assertEqual(self.getArchive(),self.archived[0:1])

    def test_ageOffYear(self):
        self.setupNesting(self.YearNesting)
        self.archiver = MArchiver(self.archivePath.name,self.YearNesting,ageoff=3)
        self.archiver.archive(self.files[0])
        self.archiver.archive(self.files[1])
        self.archiver.archive(self.files[2])
        self.assertEqual(self.getArchive(),self.archived[0:3])
        self.assertEqual(self.archiver.archive(self.files[3]),False)
        self.assertEqual(self.getArchive(),self.archived[0:3])

    def test_ageOffDay_archive(self):
        self.setupNesting(self.DayNesting)
        self.archiver.archive(self.files[0])
        self.archiver.archive(self.files[1])
        self.archiver.archive(self.files[2])
        self.assertEqual(self.getArchive(),self.archived[0:3])
        self.assertEqual(self.archiver.archive(self.files[3]),False)
        self.assertEqual(self.getArchive(),self.archived[0:3])

    def test_ageOffDay_purge(self):
        self.setupNesting(self.DayNesting)
        self.archiver.archive(self.files[0])
        self.archiver.archive(self.files[1])
        self.archiver.archive(self.files[2])
        self.archiver.archive(self.files[3])
        self.assertEqual(self.getArchive(),self.archived[0:3])
        self.archiver.setAgeoff(2)
        self.archiver.purge()
        self.assertEqual(self.getArchive(),self.archived[0:2])

    def test_Diskspace(self):
        self.setupNesting(self.DayNesting)
        self.archiver.setAgeoff(4)
        self.archiver.archive(self.files[0])
        before = self.getArchive()
        shutil.disk_usage=MagicMock(return_value=(100,50,50)) # total,used,free
        self.archiver.purge()
        self.assertEqual(self.getArchive(),before)
        shutil.disk_usage=MagicMock(return_value=(100,100,0)) # total,used,free
        self.archiver.purge()
        self.assertEqual(self.getArchive(),[])
        self.archiver.archive(self.files[0])
        self.assertEqual(self.getArchive(),[])

    def test_purgeFile(self):
        self.setupNesting(self.DayNesting)
        self.archiver.setAgeoff(4)
        self.archiver.archive(self.files[0])
        self.archiver.archive(self.files[1])
        self.archiver.archive(self.files[2])
        self.assertEqual(self.getArchive(),self.archived[0:3])
        self.archiver.purgeFile(None)
        self.assertEqual(self.getArchive(),self.archived[0:2])
        offset = self.archiver.getArchiveSubDir(0)
        self.archiver.purgeFile(offset)
        self.assertEqual(self.getArchive(),self.archived[0:1])

    def tearDown(self):
        self.archivePath.cleanup()
        self.inputPath.cleanup()