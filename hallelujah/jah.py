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

import tarfile
import os. os.path
# import ZipFile
# import gzip
import pandas as pd
from discovery.src.CSVParser import CSVParser

class Jah:
    fileHandlers = {
        ".xls": __readxls,
        ".__dir__": __readdir,
        ".__xls__": __read__xls__,
        ".tar.gz": __readtargz,
        '.__tar.gz__': __read__targz__
    }

    def __init__(self):
        pass

    # Finds the fileHandler to read the file from Network or Local disk.
    def __readfile(self, fn: str, desc: dict) -> any:
        (root, ext) = os.path.splitext(fn)
        extentions = ""
        while len(ext) > 0:
            extentions = ext + extentions
            if extentions in self.fileHandlers:
                return self.fileHandlers(fn, desc)
        return None

    def __readdir(self, fn: str, desc: dict) -> any:
        dir = fn[:-4]
        d = {}
        for de in os.scandir(dir):
            if de.is_dir() or de.is_file():
                sr = de.stat()
                d[de.name] = {
                    "path": de.path,
                    "isdir": de.is_dir(),
                    "size": sr.st_size,
                    "modify_epoch": sr.st_mtime,
                    "access_epoch": sr.st_atime,
                    "mod": sr.st_mode,
                    "uid": sr.st_uid,
                    "gid": sr.st_gid
                }
        return d

    def __readxls(self, fn: str, desc: dict) -> any:
        with pd.ExcelFile(fn) as e:
            d = {"sheets": []}
            for sn in e.sheet_names:
                d["sheets"].append(sn+".__xls__")
            return d

    def __read__xls__(self, fn: str, desc: dict) -> any:
        sn = fn[:-8]
        return e.parse(sheet=sn).to_json()

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

    def __parse(self, f: any, offset:int until: int) -> any:
        

    def __parsetsv(self, f: any, offset:int, until: int) -> any:
        return CSVParser("tsv").toJSON_FD(f,offset,until)
    
    def __parsecsv(self, f: any, offset:int, until: int) -> any:
        return CSVParser("csv").toJSON_FD(f,offset,until)
