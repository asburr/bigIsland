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
import socket
import select
import json
import os
from inspect import currentframe
from magpie.src.mworksheets import MWorksheets
from magpie.src.musage import MUsage
from magpie.src.mzdatetime import MZdatetime
from hallelujah.jah import Jah
from multiprocessing import Process
import argparse
from time import sleep


def Error(stack: list, error:str) -> str:
    cf = currentframe()
    return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error


class Hallelu:
    def __init__(self, identification: str,
                 worksheetdir: str, halleludir: str):
        # Read archived worksheets.
        self.ws = MWorksheets(worksheetdir)
        self.ws.expandcmds()
        self.processes = []
        self.halleludir = halleludir
        self.stop = False
        self.usage = MUsage()
        self.id = identification
        self.ip = self.getIPAddressForTheInternet()
        self.port = 0
        if self.id == "summit":
            # The summit port number is static, read it from cfg.
            with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
                j = json.load(f)
                self.port = j[self.usage.host]["port"]
        self.init_socket()
        self.jah_count = 0
        self.usage_tick = 0
        fn = "hall_" + self.id + ".json"
        if self.id == "summit":
            # Delete any past hallelu files.
            self.removeHalleluFiles()
            with open(os.path.join(self.halleludir,fn), "w") as f:
                json.dump({"port": self.port, "ip": self.ip, "cmd": None},f)
        else:
            # Add port number to the hallelu file.
            with open(os.path.join(self.halleludir,fn), "r") as f:
                j = json.load(f)
            with open(os.path.join(self.halleludir,fn), "w") as f:
                j["port"] = self.port
                json.dump(j,f)
            self.createJah(j)

    @staticmethod
    def getIPAddressForTheInternet() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ret = s.getsockname()[0]
        s.close()
        return ret

    def createJah(self, j: dict) -> None:
        self.jah_count += 1
        identification = str(self.jah_count)
        fn = os.path.join(self.halleludir,"jah_"+identification+".json" )
        j["port"] = 0
        with open(fn,"w") as f:
            json.dump(j,f)
        p = Process(target=Jah.child_main,
                    args=[identification, self.halleludir])
        self.processes.append(p)
        p.start()
        # wait for child to start.
        while not j["port"]:
            with open(fn,"r") as f:
                j = json.load(f)
            sleep(0.5)

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
                x = {"port": 16085, "ip": self.getIPAddressForTheInternet()}
                if host not in j:
                    raise Exception("Missing "+host+" in hosts.json, please add "+str(x))
                if j[host]["ip"] != x["ip"]:
                    raise Exception(host+" in hosts.json, ip address has changed to "+x["ip"])
                with open(os.path.join(self.halleludir,"hosts.json"),"w") as f:
                    json.dump(j,f)
            elif fn.startswith("hall_"):
                os.remove(os.path.join(self.halleludir,fn))
            elif fn.startswith("jah_"):
                os.remove(os.path.join(self.halleludir,fn))

    def init_socket(self) -> None:
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(0)  # Blocks for 5 seconds when nothing to process.
        # '' is ENYADDR, 0 causes bind to select a random port.
        # IPv6 requires socket.bind((host, port, flowinfo, scope_id))
        self.s.bind((self.ip, self.port))
        if not self.port:
            # bind selected a random port, get it!
            self.port = self.s.getsockname()[1]
        print(self.id+":"+str(self.port)+" Hallelu says hello " + str(self.ip))

    def playWorksheets(self) -> None:
        for wsn in self.ws.titles():
            for cmd in self.ws.sheet(wsn):
                self.nextCmd(cmd)
                return  # TODO; remove to play all cmds.

    def getusage(self) -> None:
        if self.id != "summit":
            return
        if self.usage_tick:
            self.usage_tick -= 1
            return
        self.usage_tick = 60
        # Contact other summits to get host usage.
        with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
            j = json.load(f)
            txt = json.dumps({"_usage_": True})
            msg = txt.encode('utf-8')
            for host in j.keys():
                addr = (j[host]["ip"], j[host]["port"])
                self.s.sendto(msg, addr)

    def poll(self) -> None:
        if self.id == "summit":
            self.playWorksheets()
        while not self.stop:
            self.getusage()
            j = self.receiveCmd()
            if j:
                self.nextCmd(j)
            else:
                sleep(0.1)
        for p in self.processes:
            # Wait for child to terminate
            p.join()

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

    def halleluCmd(self, title: str, cmd: dict) -> None:
        if title == "_usage_":
            # Request for host usage.
            msg = json.dumps({
                    "_usage_response_": {
                            "host": self.usage.host,
                            "cpuUsage": self.usage.cpuUsage(),
                            "diskUsage": self.usage.diskUsage(self.halleludir),
                            "memoryUsage": self.usage.memoryUsage(),
                            "timestamp": MZdatetime().strftime()
                            }
                    }).encode('utf-8')
            self.s.sendto(msg, cmd["__remote_address__"])
        elif title == "_usage_response_":
            # Update host.json with host usage response.
            with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
                h = json.load(f)
                cmd = cmd["_usage_response_"]
                for k in cmd.keys():
                    h[cmd["host"]][k] = cmd[k]
            with open(os.path.join(self.halleludir,"hosts.json"),"w") as f:
                json.dump(h,f)
        else:
            raise Exception("Unexpected message " + str(cmd))

    # Create a Hallelu to manage the Jahs that run this new command.
    def newHalleluCmd(self, cmd: dict) -> None:
        cmdtitle = self.ws.cmdName(cmd) + "_" + self.ws.cmdFeed(cmd)[0]
        fn = "hall_" + cmdtitle + ".json"
        if os.path.exists(os.path.join(self.halleludir,fn)):
            raise Exception("Dulicate cmd " + fn)
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

    def nextCmd(self, cmd: dict) -> None:
        title = self.ws.cmdName(cmd)
        if title.startswith("_"):
            self.halleluCmd(title,cmd)
        else:
            if self.id == "summit":
                self.newHalleluCmd(cmd)
            else:
                raise Exception("Unexpecting cmd " + str(cmd))

    @staticmethod
    def child_main(ip: str, identification: str,
                 worksheetdir: str, halleludir: str):
        h = Hallelu(identification=identification,
                worksheetdir=worksheetdir,
                halleludir=halleludir)
        h.poll()

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