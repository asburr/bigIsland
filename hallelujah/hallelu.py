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
from multiprocessing import Process
import argparse
from time import sleep


def Error(stack: list, error:str) -> str:
    cf = currentframe()
    return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error


class Hallelu:
    def __init__(self, port: int, ip: str, identification: str,
                 worksheetdir: str, halleludir: str):
        self.processes = []
        self.ws = MWorksheets(worksheetdir)
        self.halleludir = halleludir
        self.stop = False
        self.ip = ip
        self.port = port
        self.id = identification
        self.init_socket(ip,port)
        fn = "hall_" + self.id + ".json"
        if self.id == "summit":
            # Delete any past hallelu files.
            self.removeHalleluFiles()
            with open(os.path.join(self.halleludir,fn), "w") as f:
                json.dump(f,{"port": self.port, "ip": self.ip, "cmd": None})
        else:
            # Add port number to the hallelu file.
            with open(os.path.join(self.halleludir,fn), "r") as f:
                j = json.load(f)
            with open(os.path.join(self.halleludir,fn), "w") as f:
                j["port"] = self.port
                json.dump(f,j)
            self.createJah(j)

    @staticmethod
    def getIPAddressForTheInternet() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ret = s.getsockname()[0]
        s.close()
        return ret

    def createJah(self, cmd: dict) -> None:
        with open(os.path.join(self.halleludir,"jahs_"+self.id+".json"),"r") as f:
        # TODO; create jah process.
        # - create in hallelu dir a jah file with cmd
        # - spawn jah
        # - wait for jah to start up.
        # TODO; how to create on other computers?
        #       Summit Hallelu should know which host is least busy,
        #       using keep-alives between the Hallelu.
        #       Requests from children can go directly to the summit Hallelu
        #       on another host.
        #         Child --request host--> Summit
        #         Child --exec command-->host
        pass

    def removeHalleluFiles(self) -> None:
        for fn in os.listdir(path=self.halleludir):
            if not fn.endswith(".json"):
                continue
            if fn == "hosts.json":
                # reset host usage.
                with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
                    j = josn.load(f)
                    for host in j:
                        j[host] = {}
                with open(os.path.join(self.halleludir,"hosts.json"),"w") as f:
                    json.dumps(f,j)
                conitnue
            if not fn.startswith("hall_"):
                continue
            os.remove(os.path.join(self.halleludir,fn))
        
    def init_socket(self,ip: str, port: int):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(5)  # Blocks for 5 seconds when nothing to process.
        # '' is ENYADDR, 0 causes bind to select a random port.
        # IPv6 requires socket.bind((host, port, flowinfo, scope_id))
        self.s.bind((self.ip, self.port))
        if not self.port:
            # bind selected a random port, get it!
            self.port = self.s.getsockname()[1]

    def playWorksheets(self) -> None:
        for title in self.ws_titles:
            i = self.ip
            p = self.port
            for cmd in self.ws.cmds(title):
                i, p = self.nextcmd(i, p, cmd)

    def getusage(self) -> None:
        if self.id != "summit":
            return
        if self.usage_tick:
            self.usage_tick -= 1
            return
        self.usage_tick = 60
        # Contact other hosts, get usage.
        with open(os.path.join(self.halleludir,"hosts.json"),"r") as f:
            j = json.load(f)
            for host in j:
                # TODO; send usage request to hall.

    def poll(self) -> None:
        if self.id == "summit":
            self.playWorksheets()
        while not self.stop:
            self.getusage()
            j = self.receiveCmd()
            if not self.localcmd(j):
                self.nextcmd(j)
        for p in self.processes:
            # Wait for child to terminate
            p.join()

    def receiveCmd(self) -> dict:
        ready = select.select([self.s], [], [], 1)
        if not ready[0]:
            return None
        (data, ip) = self.s.recvfrom(4096)
        try:
            j = json.loads(data.decode('utf-8'))
        except json.JSONDecodeError as err:
            print("Failed to parse cmds from " + str(ip))
            print(err)
            return None
        except Exception as e:
            print("Failed to parse cmds " + str(e) + " from " + str(ip))
            return None
        return j

    def localCmd(self, j: dict) -> bool:
        if self.ws.cmdTitle(j):
            # Follow-on commands are those with titles.
            return False
        msg = json.dumps(j).encode('utf-8')
        with open(os.path.join(self.halleludir,"jahs_"+self.id+".json"),"r") as f:
            j = json.load(f)
            for jah in j:
                sock.sendto(msg, (j["ip"], j["port"]))
        return True

    def nextcmd(self, cmd: dict) -> (str, int):
        if cmd == None:
            return
        cmdtitle = self.ws.cmdTitle(cmd)
        fn = "hall_" + cmdtitle + ".json"
        j = {"port": 0, "ip": self.ip, "cmd": cmd}
        if os.path.exists(os.path.join(self.halleludir,fn)):
            with open(os.path.join(self.halleludir,fn),"r") as f:
                j = json.load(f)
            return (j["ip"], j["port"])
        with open(os.path.join(self.halleludir,fn),"w") as f:
            json.dump(f,j)
        p = Process(target=self.main,
                    args=(self.worksheetdir, cmdtitle, "-i "+self.ip))
        self.processes.add(p)
        p.start()
        while not j["port"]:
            with open(os.path.join(self.halleludir,fn),"r") as f:
                j = json.load(f)
            sleep(0.5)
        return (j["ip"], j["port"])

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Hallelu database controller")
        parser.add_argument('worksheetdir', help="Path to worksheet directory")
        parser.add_argument('halleludir', help="Path to hallelu directory")
        parser.add_argument('id', help="Unique name for this Hallelu is the feed name for the cmd. The summit Hallelu has a name of summit", nargs='?', const="summit", type=str)
        parser.add_argument('-p', '--port', help="Override automatic port allocation, use this port instead")
        parser.add_argument('-i', '--ip', help="Limit comms to a particular interface by specifying the IP address for that interface, otherwise packets on all interfaces are processed.")
        args = parser.parse_args()
        if args.ip == None:
            # IPv4: '' is INADDR_ANY i.e. all interfaces.
            args.ip = ''
        if args.port == None:
            # port 0 means select any port, random selection.
            args.port = 0
        print("Hallelu " + str(args.ip) + ":" + str(args.port))
        h = Hallelu(port=args.port, ip=args.ip, identification=args.id, 
                worksheetdir=args.worksheetdir,
                halleudir=args.halleludir)
        h.poll()


if __name__ == "__main__":
    Hallelu.main()