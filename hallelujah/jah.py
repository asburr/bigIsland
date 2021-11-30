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
import os.path
import traceback
# import ZipFile
# import gzip
from magpie.src.mworksheets import MWorksheets
from magpie.src.mudp import MUDPBuildMsg
import json
import socket
from cmds.files import Files
# from cmds.loadf import Loadf
from time import sleep

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

    def runCmd(self, remotecmd: any, requestId: int) -> None:
        cmdname = MWorksheets.cmdName(remotecmd)
        if cmdname == "_sample_":
            self.sample(remotecmd, requestId)
        else:
            raise Exception("Unknown command " + cmdname)

    def sample(self, cmd: any, requestId: int) -> None:
        cmd = cmd["_sample_"]
        msg=MUDPBuildMsg(
                remoteAddr=cmd["__remote_address__"],
                requestId=requestId)
        addrReqId=cmd["__remote_address__"] + (requestId,)
        self.mudp.send(
            content=json.dumps({
                "_sample_response_": {
                    "schema": self.op.schema()
                }
            }),
            eom=False, msg=msg
        )
        for eom, sample in self.op.sample( cmd["feed"], cmd["N"]):
            if self.mudp.cancelledRequestId(addrReqId):
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
                self.op.execute()
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

