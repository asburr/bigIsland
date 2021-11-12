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
# There is a hierarchy of Hallelu. The first database operation is sent to
# the summit. The summit searches for a Hallelu that is running the cmd,
# in this case the child is returned to the user. Otherwise, when the cmd
# is not already running, a new Hallelu is created and this Hallelu is
# returned to the user.
#
# The user's next database operation is sent to the child Hallelu, not the
# top Hallelu.
#
# A worksheet is one or more database operations. Worksheets are tracked
# in the database by a user provided name. Subsequent operations are part
# of the same worksheet when they are sent with the same name. Operations
# are available on the worksheet, at any level within the heirarcy.
#
# Communication with Hallelu is using JSON sent over a UDP socket. Each
# Hallelu has just one UDP socket, communication with the same Hallelu
# will use the same socket for all Users.
# 
# 
import json
import os
from inspect import currentframe
from magpie.src.mworksheets import MWorksheets
from magpie.src.musage import MUsage
from magpie.src.mzdatetime import MZdatetime
from magpie.src.mudp import MUDP, MUDPBuildMsg
from hallelujah.jah import Jah
from multiprocessing import Process
import argparse
from time import sleep
import traceback
import socket


def Error(stack: list, error:str) -> str:
    cf = currentframe()
    return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error


class Hallelu():
    def __init__(self, identification: str,
                 worksheetdir: str, halleludir: str):
        self.id = identification
        self.halleludir = halleludir
        self.localHost = socket.gethostname()
        self.summitAddr, (self.ip, self.port) = self.readLocalHost()
        fn = "hall_" + self.id + ".json"
        if self.id == "summit":
            self.halls = {}  # <feed>: <addr>
            self.removeHalleluFiles()
            with open(os.path.join(self.halleludir,fn), "w") as f:
                json.dump({"port": self.port, "ip": self.ip, "cmd": None},f)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(5.0)
        address = (self.ip, self.port)
        try:
            self.s.bind(address)
        except:
            raise Exception("Hallelu failed to bind to address " + str(address) + " host public ip is " + str(MUDP.getIPAddressForTheInternet()))
        self.mudp = MUDP(self.s, clientMode=False)
        # Read archived worksheets.
        self.ws = MWorksheets(worksheetdir)
        self.ws.expandcmds()
        self.processes = []
        self.stop = False
        self.jah_count = 0
        if self.id != "summit":
            self.jahs = []  # <addr>
            # Add port number to the hallelu file.
            with open(os.path.join(self.halleludir,fn), "r") as f:
                j = json.load(f)
            with open(os.path.join(self.halleludir,fn), "w") as f:
                j["port"] = self.port
                json.dump(j,f)
            self.createJah(j)
        self.usage_tick = 0
        self.usage = MUsage()
        print(str(self.port)+":"+self.id+" Hallalelu says hello " + str(self.ip))

    # Return Summit address, Local address
    def readLocalHost(self) -> ((str, int), (str, int)):
        try:
            fn = os.path.join(self.halleludir,"hosts.json")
            with open(fn,"r") as f:
                j = json.load(f)
                summit = (j[self.localHost]["ip"], j[self.localHost]["port"])
                if self.id == "summit":
                    address = summit
                else:
                    address = (j[self.localHost]["ip"], 0)
                return (summit,address)
        except:
            traceback.print_exc()
            raise Exception("Failed to find summit hallelu, "+self.localHost+", in "+fn)

    def createJah(self, j: dict) -> None:
        self.jah_count += 1
        identification = self.id+"_"+str(self.jah_count)
        fn = os.path.join(self.halleludir,"jah_"+identification+".json" )
        j["port"] = 0
        with open(fn,"w") as f:
            json.dump(j,f)
        p = Process(target=Jah.child_main,
                    args=[identification, self.halleludir,self.ws.dir])
        self.processes.append(p)
        p.start()
        # wait for child to start.
        while not j["port"]:
            with open(fn,"r") as f:
                j = json.load(f)
            sleep(0.5)
        self.jahs.append((j["ip"],j["port"]))
        print(self.jahs[-1])

    def removeHalleluFiles(self) -> None:
        for fn in os.listdir(path=self.halleludir):
            if not fn.endswith(".json"):
                continue
            if fn == "hosts.json":
                # reset host usage.
                with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
                    j = json.load(f)
                    for host in j:
                        j[host] = {"port": j[host]["port"], "ip": j[host]["ip"]}
                if host not in j:
                    raise Exception("Missing "+host+" in hosts.json")
                if len(j[host]["ip"]) > 0 and j[host]["ip"] != MUDP.getIPAddressForTheInternet():
                    raise Exception(host+" in hosts.json, ip address has changed to "+MUDP.getIPAddressForTheInternet())
                with open(os.path.join(self.halleludir,"hosts.json"),"w") as f:
                    json.dump(j,f)
            elif fn.startswith("hall_"):
                os.remove(os.path.join(self.halleludir,fn))
            elif fn.startswith("jah_"):
                os.remove(os.path.join(self.halleludir,fn))

    def playWorksheets(self) -> None:
        for wsn in self.ws.titles():
            for cmd in self.ws.sheet(wsn):
                self.nextCmd(cmd)
                return  # TODO; duebgging stops playing the work sheer, remove to play all cmds.

    def getusage(self) -> None:
        if self.usage_tick:
            self.usage_tick -= 1
            return
        self.usage_tick = 60
        # Contact other summits to get host usage.
        with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
            j = json.load(f)
            txt = json.dumps({"_usage_": True})
            for host in j.keys():
                self.mudp.send(
                    content=txt,
                    eom=True,
                    msg=MUDPBuildMsg(
                        remoteAddr=(j[host]["ip"], j[host]["port"]),
                        requestId=MUDPBuildMsg.nextId()
                    )
                )

    def poll(self) -> None:
        if self.id == "summit":
            self.playWorksheets()
        while not self.stop:
            if self.id == "summit":
                self.getusage()
            didSomething = False
            for ((ip, port, requestId), content, eom) in self.mudp.recv():
                didSomething = True
                cmd = json.loads(content)
                if "__remote_address__" not in cmd:
                    # The remote_address is the originator and is stored in
                    # the command, so the response is sent to the originator.
                    cmd["__remote_address__"] = (ip, port)
                if "__request_id__" not in cmd:
                    # The request id is stored in the command, so the response
                    # is to the original request id.
                    cmd["__request_id__"] = requestId               
                self.nextCmd(cmd)
            if not didSomething:
                sleep(0.1)
        for p in self.processes:
            # Wait for child to terminate
            p.join()

    def localCmd(self, title: str, cmd: dict) -> None:
        print("localCmd " + title)
        if title == "_usage_":
            self.mudp.send(
                content=json.dumps({
                    "_usage_response_": {
                            "host": self.usage.host,
                            "cpuUsage": self.usage.cpuUsage(),
                            "diskUsage": self.usage.diskUsage(self.halleludir),
                            "memoryUsage": self.usage.memoryUsage(),
                            "timestamp": MZdatetime().strftime()
                            }
                    }
                ).encode('utf-8'),
                eom=True,
                msg=MUDPBuildMsg(
                        remoteAddr=cmd["__remote_address__"]),
                        requestId=cmd["__request_id__"]
                )
        elif title == "_usage_response_":
            # Update host.json with host usage response.
            with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
                h = json.load(f)
                cmd = cmd["_usage_response_"]
                for k in cmd.keys():
                    h[cmd["host"]][k] = cmd[k]
            with open(os.path.join(self.halleludir,"hosts.json"),"w") as f:
                json.dump(h,f)
        elif title == "_sample_":
            if self.id == "summit":
                # Send to Hallelu responsible for the feed.
                self.mudp.send(
                    content=json.dumps(cmd).encode('utf-8'),
                    eom=True,
                    msg=MUDPBuildMsg(
                        remoteAddr=self.halls[cmd["_sample_"]["feed"]],
                        requestId=cmd["__request_id__"]
                    ),
                )
            else:
                # Send to ONE of the Jahs responsible for holding the data.
                for jah in self.jahs:
                    self.mudp.send(
                        content=json.dumps(cmd).encode('utf-8'),
                        eom=True,
                        msg=MUDPBuildMsg(
                            remoteAddr=jah,
                            requestId=cmd["__request_id__"]
                        )
                    )
                    break
        else:
            raise Exception("Unexpected message " + str(cmd))

    # Create a Hallelu to manage the Jahs that run this new command.
    # TODO; waiting for the Hallelu to create itself will block the summit
    # hallelu from other tasks; have a thread create new Hallelu.
    def newHalleluCmd(self, cmd: dict) -> None:
        cmdtitle = self.ws.cmdName(cmd) + "_" + self.ws.cmdFeed(cmd)[0]
        fn = "hall_" + cmdtitle + ".json"
        if os.path.exists(os.path.join(self.halleludir,fn)):
            raise Exception("Duplicate cmd " + fn)
        j = {"port": 0, "ip": self.ip, "cmdtitle": cmdtitle, "cmd": cmd}
        with open(os.path.join(self.halleludir,fn),"w") as f:
            json.dump(j,f)
        p = Process(target=self.child_main,
                    args=[self.ip, cmdtitle, self.ws.dir, self.halleludir])
        self.processes.append(p)
        p.start()
        # wait for child to start.
        while not j["port"]:
            with open(os.path.join(self.halleludir,fn),"r") as f:
                j = json.load(f)
            sleep(0.5)
        for feed in self.ws.cmdFeed(cmd):
            self.halls[feed] = (j["ip"],j["port"])
            print(feed)
            print(self.halls[feed])

    def nextCmd(self, cmd: dict) -> None:
        title = self.ws.cmdName(cmd)
        if title.startswith("_"):
            self.localCmd(title,cmd)
        else:
            if self.id == "summit":
                self.newHalleluCmd(cmd)
            else:
                raise Exception("Unexpecting cmd " + str(cmd))

    @staticmethod
    def child_main(ip: str, identification: str,
                 worksheetdir: str, halleludir: str):
        try:
            h = Hallelu(identification=identification,
                    worksheetdir=worksheetdir,
                    halleludir=halleludir)
            h.poll()
        except:
            traceback.print_exc()
        print("Hall terminated " + str(h.port))

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Hallelu database controller")
        parser.add_argument('worksheetdir', help="Path to worksheet directory")
        parser.add_argument('halleludir', help="Path to hallelu directory")
        parser.add_argument('--id', help="Unique name for this Hallelu is the feed name for the cmd. The summit Hallelu has a name of summit")
        args = parser.parse_args()
        if args.id is None:
            args.id = "summit"
        h = Hallelu(identification=args.id, 
                worksheetdir=args.worksheetdir,
                halleludir=args.halleludir)
        h.poll()


if __name__ == "__main__":
    Hallelu.main()