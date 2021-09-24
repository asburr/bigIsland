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

import socket
import select
import tarfile
import os.path
# import ZipFile
# import gzip
import pandas as pd
from discovery.src.CSVParser import CSVParser
from magpie.src.mworksheets import MWorksheets
import json
from time import sleep
from abc import ABC, abstractmethod
import re


class Cmd(ABC):
    @abstractmethod
    def sample(self, feedName: str, n:int) -> dict:
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
                "order": {}
            })

    def sample(self, feedName: str, n:int) -> dict:
        i = 0
        if feedName:
            feed = self.feeds[feedName]
            for modifiedTime in feed["order"]:
                for pn in feed["order"][modifiedTime]:
                    yield pn
                    i += 1
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
                        yield {"stream": f, "file": pn}
                        if kfeeds[f] == j:
                            break
                        kfeeds[f] += 1
                        i += 1
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
                            yield {"stream": f, "file": pn}
                            i += 1
                            if i == n:
                                return

    def execute(self) -> None:
        self._scandir(self.depth)
        print(list(self.sample(None,10)))

    def _scandir(self, depth: int) -> None:
        for de in os.scandir(self.path):
            if de.is_file():
                sr = de.stat()
                pn = os.path.join(de.path, de.name)
                if pn not in self.files:
                    for feed in self.feeds:
                        if feed["regex"].match(pn):
                            self.files.add(pn)
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

    def sample(self, feedName: str, n:int) -> dict:
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



class Jah:
    def __init__(self, identification: str, halleludir: str):
        self.id = identification
        self.halleludir = halleludir
        fn = os.path.join(self.halleludir,"jah_" + self.id + ".json")
        with open(fn, "r") as f:
            j = json.load(f)
        self.stop = False
        self.ip = j["ip"]
        self.port = j["port"]
        self.init_socket()
        # Add port number to the hallelu file.
        with open(fn, "r") as f:
            j = json.load(f)
        with open(fn, "w") as f:
            j["port"] = self.port
            json.dump(j,f)
        self.cmd = j["cmd"]
        self.cmdname = MWorksheets.cmdName(self.cmd)
        if self.cmdname == "files":
            self.op = Files(self.cmd[self.cmdname])
        else:
            raise Exception("unknonw command " + self.cmdname)
        self.msgid = 0
        self.msgSeq = 0

    def init_socket(self) -> None:
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(0)  # Blocks for 5 seconds when nothing to process.
        # '' is ENYADDR, 0 causes bind to select a random port.
        # IPv6 requires socket.bind((host, port, flowinfo, scope_id))
        self.s.bind((self.ip, self.port))
        if not self.port:
            # bind selected a random port, get it!
            self.port = self.s.getsockname()[1]
        print(self.id +":"+str(self.port)+" Jah says hello " + str(self.ip))

    def poll(self) -> None:
        while not self.stop:
            j = self.receiveCmd()
            if not self.runCmd(j):
                sleep(0.1)

    def receiveCmd(self) -> dict:
        ready = select.select([self.s], [], [], 1)
        if not ready[0]:
            return None
        (data, ip_port) = self.s.recvfrom(4096)
        try:
            j = json.loads(data.decode('utf-8'))
        except json.JSONDecodeError as err:
            print("Failed to parse cmds from " + str(ip_port))
            print(err)
            return None
        except Exception as e:
            print("Failed to parse cmds " + str(e) + " from " + str(ip_port))
            return None
        errors = self.ws.verifycmd(j)
        if errors:
            print("Failed to parse cmds " + errors + " from " + str(ip_port))
            return None
        j["__remote_address__"] = ip_port
        return j

    def runCmd(self, remotecmd: any) -> bool:
        if remotecmd is not None:
            cmdname = MWorksheets.cmdName(remotecmd)
            if cmdname == "_sample_":
                self.sample(remotecmd[cmdname])
            else:
                raise Exception("Unknown command " + cmdname)
            return True
        else:
            if self.cmdname == "files":
                self.op.execute()
            return True
        return False

    def startSend(self, begintxt: str):
        self.msgSeq = 0
        self.msgId += 1
        if self.msgId > 255:
            self.msgId = 0
        self.txt = "%2x%2x"+begintxt % (self.msgid, self.msgSeq)

    def send(self, addr, begintxt: str, txt: str, conttxt: str, endtxt: str) -> None:
        if len(self.txt) + len(txt) + len(endtxt) > 65527:
            self.txt += endtxt
            self.s.sendto(self.txt.encode('utf-8'), addr)
            self.msgSeq += 1
            if self.msgSeq > 255:
                self.msgSeq = 0
            self.txt = ("%2x%2x"+begintxt + txt) % (self.msgid, self.msgSeq)
        else:
            self.txt + conttxt + txt
        
    def flush(self, addr, endtxt: str) -> None:
        self.txt += endtxt
        self.s.sendto(self.txt.encode('utf-8'), addr)
        self.txt = None

    def sample(self, cmd: any) -> None:
        addr = cmd["__remote_address__"]
        begintxt = "{\"_sample_response_\":["
        endtxt = "]}"
        self.startsend(begintxt)
        for sample in self.op.sample(cmd["N"]):
            self.send(addr,begintxt, json.dumps(sample), ",", endtxt)
        self.flush(addr,endtxt)

    @staticmethod
    def child_main(identification: str, halleludir: str) -> None:
        jah = Jah(identification, halleludir)
        jah.poll()
