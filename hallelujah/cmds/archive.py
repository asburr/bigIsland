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
from magpie.src.marchiver import MArchiver, ArchiveSubDir
import itertools


class Archive(Cmd):
    """
    File archiver
    """
    def __init__(self, cmd: dict):
        super().__init__()
        self.inpath = cmd["inPath"]
        nesting = 0
        if cmd["year"]: nesting |= ArchiveSubDir.YYYY
        if cmd["month"]: nesting |= ArchiveSubDir.mm
        if cmd["day"]: nesting |= ArchiveSubDir.DD
        if cmd["hour"]: nesting |= ArchiveSubDir.HH
        if cmd["minute"]: nesting |= ArchiveSubDir.MM
        if cmd["second"]: nesting |= ArchiveSubDir.SS
        self.archive = MArchiver(
            cmd["archiveRootPath"],
            nesting=nesting,
            ageoff=cmd["purge"],
            diskPercentage=cmd["diskUsage"]
            )

    def execute(self) -> None:
        filepath=next(MArchiver.ls(self.inpath),None)
        if not filepath: return False
        self.archive.archive(filepath)
        return True

    def data(self, feedName: str, n:int) -> list:
        """ Return oldest n files in the archive. """
        return [x for x in itertools.islice(self.archive.oldests(),n)]