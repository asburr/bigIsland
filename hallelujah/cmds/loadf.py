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
import tarfile
import os.path
# import ZipFile
# import gzip
import pandas as pd
from magpie.src.musage import MUsage
from discovery.src.CSVParser import CSVParser


class Loadf(Cmd):
    """
    Loadf: Loads data from a file
    """
    def __init__(self, cmd: dict):
        super().__init__()
        self.fileHandlers = {
            ".xls": self.__readxls,
            ".tar.gz": self.__readtargz,
            '.__tar.gz__': self.__read__targz__
        }
        self.cmd:dict = cmd["loadf"]
        self.snapshot = self.cmd["snapshot"]
        self.inputData = self.cmd["inputFeed"]
        self.outputData = self.cmd["outputFeed"]
        self.outputStats = self.cmd["outputStatsFeed"]
        inputSchema = self.cmd["inputSchema"]
        self.parse = None
        if "tshark" in inputSchema:
            self.parse = self.readTshark
        elif "csv" in inputSchema:
            self.parse = self.readCSV
        elif "xls" in inputSchema:
            self.parse = self.readXLS
        elif "feed" in inputSchema:
            tmp = inputSchema["feed"]
            self.feedName = tmp["feed"]
            tmp = tmp["format"]
            self.sqlOracleTable = False
            self.csv = False
            if "sqlOracleTable" in tmp:
                pass
            elif "csv" in tmp:
                pass
            else:
                raise Exception("Unknown format {format}")
        else:
            raise Exception("Unknown inutSchema {inputSchema}")

    def execute(self, musage: MUsage) -> None:
        return

    # Finds the fileHandler to read the file from Network or Local disk.
    def __readfile(self, fn: str, desc: dict) -> any:
        (root, ext) = os.path.splitext(fn)
        extentions = ""
        while len(ext) > 0:
            extentions = ext + extentions
            if extentions in self.fileHandlers:
                return self.fileHandlers(fn, desc)
        return None

    def __readxls(self, fn: str, desc: dict) -> any:
        with pd.ExcelFile(fn) as e:
            d = {"sheets": []}
            for sn in e.sheet_names:
                d["sheets"].append(sn)
                d[sn] = e.parse(sheet=sn).to_json()
            return d

    def __readtargz(self, fn: str, desc: dict) -> any:
        with tarfile.open(fn, "r:gz") as tar:
            d = {}
            for m in tar:
                if m.isfile():
                    d[m.name+".__tar.gz__"] = {
                        "file": m.name,
                        "tar": fn,
                        "filesize": m.size,
                        "offset": 0,
                        "until": m.size
                    }
            return d

    def __read__targz__(self, fn: str, desc: dict) -> any:
        with tarfile.open(desc["tar"], "r:gz") as tar:
            with tar.extractfile(desc["file"]) as f:
                return self.__parse(
                    f=f,
                    offset=desc["offset"],
                    until=desc["until"])
        return None

    def __parse(self, f: any, offset:int, until: int) -> any:
        pass

    def __parsetsv(self, f: any, offset:int, until: int) -> any:
        yield from CSVParser("tsv").toJSON_FD(f,offset,until)

    def __parsecsv(self, f: any, offset:int, until: int) -> any:
        yield from CSVParser("csv").toJSON_FD(f,offset,until)
