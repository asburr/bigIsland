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

from magpie.src.mudp import MUDP
import tarfile
import os.path
import traceback
# import ZipFile
# import gzip
import pandas as pd
from discovery.src.CSVParser import CSVParser
from discovery.src.JSONParser import JSONSchema
from magpie.src.mworksheets import MWorksheets
from magpie.src.mudp import MUDPBuildMsg
import json
from abc import ABC, abstractmethod
import re
import socket
from time import sleep


class Cmd(ABC):
    @abstractmethod
    def headers(self) -> list:
        raise Exception("Not implemented")

    @abstractmethod
    def schema(self) -> list:
        raise Exception("Not implemented")

    @abstractmethod
    def sample(self, feedName: str, n:int) -> (bool, dict):
        raise Exception("Not implemented")

    @abstractmethod
    def execute(self) -> None:
        raise Exception("Not implemented")


class Files(Cmd):
    def __init__(self, cmd: dict):
        self.path=cmd["path"]["path"]
        self.depth=cmd["path"]["depth"]
        self.files = set()
        self.feeds = []
        for feed in cmd["path"]["feeds"]:
            self.feeds.append({
                "feed": feed["feed"],
                "regex": re.compile(feed["regex"], re.IGNORECASE),
                "order": {},
                "schema": JSONSchema()
            })

    def schema(self) -> list:
        return ["stream", "filename"]

    def sample(self, feedName: str, n:int) -> (bool, dict):
        i = 0
        if feedName:
            for feed in self.feeds:
                if feed["feed"] == feedName:
                    for modifiedTime in feed["order"]:
                        for pn in feed["order"][modifiedTime]:
                            i += 1
                            yield (i == n, pn)
                            if i == n:
                                return
        else:
            j = n / len(self.feeds)
            if j == 0:
                j = 1
            kfeeds = {}
            for feed in self.feeds:
                f = feed["feed"]
                kfeeds[f] = 0
                for modifiedTime in feed["order"]:
                    for pn in feed["order"][modifiedTime]:
                        i += 1
                        yield (i == n, {"feed": f, "file": pn})
                        if kfeeds[f] == j:
                            break
                        kfeeds[f] += 1
                        if i == n:
                            return
                    if kfeeds[f] == j:
                        break
            for feed in self.feeds:
                f = feed["feed"]
                j = 0
                for modifiedTime in feed["order"]:
                    for pn in feed["order"][modifiedTime]:
                        if j > kfeeds[f]:
                            i += 1
                            yield (i == n,{"stream": f, "file": pn})
                            if i == n:
                                return

    def execute(self) -> None:
        self._scandir(self.depth)
        # print(list(self.sample(None,10)))

    def _scandir(self, depth: int) -> None:
        for de in os.scandir(self.path):
            if de.is_file():
                sr = de.stat()
                pn = os.path.join(de.path, de.name)
                if pn not in self.files:
                    for feed in self.feeds:
                        if feed["regex"].match(pn):
                            self.files.add(pn)
                            feed["schema"].gather("", pn)
                            feed["order"].setdefault(
                                sr.st_mtime,[]).append(pn)
                            break
            elif de.is_dir() and depth > 0:
                self._scandir(depth=depth-1)

class Loadf(Cmd):
    def __init__(self, cmd: dict):
        self.fileHandlers = {
            ".xls": self.__readxls,
            ".__xls__": self.__read__xls__,
            ".tar.gz": self.__readtargz,
            '.__tar.gz__': self.__read__targz__
        }

    def schema(self) -> list:
        return []

    def sample(self, feedName: str, n:int) -> (bool, dict):
        return

    def execute(self) -> None:
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

    def __parse(self, f: any, offset:int, until: int) -> any:
        pass

    def __parsetsv(self, f: any, offset:int, until: int) -> any:
        return CSVParser("tsv").toJSON_FD(f,offset,until)

    def __parsecsv(self, f: any, offset:int, until: int) -> any:
        return CSVParser("csv").toJSON_FD(f,offset,until)



class Jah():
    def __init__(self, identification: str, halleludir: str, worksheetdir: str):
        host = socket.gethostname()
        try:
            fn = os.path.join(halleludir,"hosts.json")
            with open(fn,"r") as f:
                j = json.load(f)
                self.summit_addr = (j[host]["ip"], j[host]["port"])
        except:
            raise Exception("Failed to find summit hallelu, "+host+", in "+fn)
        self.ip = MUDP.getIPAddressForTheInternet()
        self.port = 0
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(5.0)
        # '' is ENYADDR, 0 causes bind to select a random port.
        # IPv6 requires socket.bind((host, port, flowinfo, scope_id))
        self.s.bind((self.ip, self.port))
        self.port = self.s.getsockname()[1]
        self.id = identification
        self.halleludir = halleludir
        fn = os.path.join(self.halleludir,"jah_" + self.id + ".json")
        with open(fn, "r") as f:
            j = json.load(f)
            self.cmd = j["cmd"]
        with open(fn, "w") as f:
            j["ip"] = self.ip
            j["port"] = self.port
            json.dump(j,f)
        self.ws = MWorksheets(worksheetdir)
        self.stop = False
        self.cmdname = MWorksheets.cmdName(self.cmd)
        if self.cmdname == "files":
            self.op = Files(self.cmd[self.cmdname])
        else:
            raise Exception("unknown command " + self.cmdname)
        self.mudp = MUDP(socket=self.s, clientMode=False)
        print(str(self.port)+":"+self.id+" jah says hello " + str(self.ip))

    def runCmd(self, remotecmd: any, requestId: int) -> bool:
        if remotecmd is not None:
            cmdname = MWorksheets.cmdName(remotecmd)
            if cmdname == "_sample_":
                self.sample(remotecmd, requestId)
            else:
                raise Exception("Unknown command " + cmdname)
            return True
        else:
            if self.cmdname == "files":
                self.op.execute()
            return True
        return False

    def sample(self, cmd: any, requestId: int) -> None:
        cmd = cmd["_sample_"]
        msg=MUDPBuildMsg(
                remoteAddr=cmd["__remote_address__"],
                requestId=requestId)
        self.mudp.send(
            content=json.dumps({
                "_sample_response_": {
                    "schema": self.op.schema()
                }
            }),
            eom=False, msg=msg
        )
        for eom, sample in self.op.sample( cmd["feed"], cmd["N"]):
            if self.mudp.cancelledRequestId(requestId):
                break
            self.mudp.send(
                content=json.dumps(sample),
                eom=eom, msg=msg
            )

    def poll(self) -> None:
        while not self.stop:
            didSomething = False
            for ((ip, port, requestId), content, eom) in self.mudp.recv():
                didSomething = True
                cmd = json.loads(content)
                self.runCmd(cmd, requestId)
            if not didSomething:
                sleep(0.1)
        for p in self.processes:
            # Wait for child to terminate
            p.join()

    @staticmethod
    def child_main(identification: str, halleludir: str, worksheetdir: str) -> None:
        try:
            jah = Jah(identification, halleludir, worksheetdir)
            jah.poll()
        except:
            traceback.print_exc()
        print("Jah terminated " + str(jah.port))

