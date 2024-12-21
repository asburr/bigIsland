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
import json
import os
import socket
from magpie.src.mTimer import mTimer
from magpie.src.musage import MUsage
from magpie.src.mzdatetime import MZdatetime
from hallelujah.root import RootHJ
from hallelujah.jah import Jah
from hallelujah.hallelu import Hallelu
from multiprocessing import Process
import argparse
from magpie.src.mlogger import MLogger, mlogger
from magpie.src.mworksheets import MWorksheets
from magpie.src.mudp import MUDPKey


class TrackAttempts:
    def __init__(self):
        self.leftAttempts = 0
        self.rightAttempts = 0
        self.attempts = 0

    def newHere(self) -> int:
        """
        Return 0 to add here, -1 to search for a congregation
        on the left, 1 to search for a congregation on the right.
        """
        if self.attempts < self.leftAttempts:
            if self.attempts < self.rightAttempts:
                self.attempts += 1
                return 0
        if self.leftAttempts < self.rightAttempts:
            self.leftAttempts += 1
            return -1
        else:
            self.rightAttempts += 1
            return 1

    def json(self):
        return self.__dict__
    
    def fromJson(self,j:dict):
        self.__dict__ = j


class Cluster():
    """
    Cluster of three congregations for redundancy,
    Parent and their children on the left and right.
    Redundancy is provided by alternative paths through the congregations.
    Each congregation knows the cluster it is a member of.
    Alternative paths:
    o parent: 
    o left:
    o right:
    """
    def __init__(self, path: str, connectaddr: (str, int)):
        self.commandAttempts = TrackAttempts()
        self.sheetAttempts = TrackAttempts()
        self.congregationAttempts = TrackAttempts()
        if not os.path.exists(path):
            os.mkdir(path)
        self.path = os.path.join(path, 'cluster.json')
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                j = json.load(f)
            self.commandAttempts.fromJson(j["TrackAttempts"][0])
            self.sheetAttempts.fromJson(j["TrackAttempts"][1])
            self.congregationAttempts.fromJson(j["TrackAttempts"][2])
            del j["TrackAttempts"]
            for k,v in j.items():
                self.__dict__[k] = v
            if self.connect != connectaddr:
                self.connect = connectaddr
                self.save()
        else:
            self.leftCongregationAddress = None
            self.rightCongregationAddress = None
            # parent cluster is needed when direct parent is not responding!
            self.parents = []
            self.connect = connectaddr
            self.save()

    def save(self):
        j = {}
        for k,v in self.__dict__.items():
            print(k)
            print(type(v))
            if type(v) in [str,type(None),list]:
                j[k] = self.__dict__[k]
        j["TrackAttempts"]=[
            self.commandAttempts.json(),
            self.sheetAttempts.json(),
            self.congregationAttempts.json()
        ]
        print(j)
        with open(self.path, "w") as f:
            json.dump(j, f)
        
    def parent(self) -> str:
        if not self.parents:
            return None
        return self.parents[0]

    def right(self) -> str:
        return self.rightCongregationAddress

    def left(self) -> str:
        return self.leftCongregationAddress

    def addRight(self, address:str) -> bool:
        if not self.rightCongregationAddress:
            self.rightCongregationAddress = address
            self.save()
            return True
        return False

    def addLeft(self, address:str) -> bool:
        if not self.leftCongregationAddress:
            self.leftCongregationAddress = address
            self.save()
            return True
        return False

    def newConHere(self, address:str) -> str:
        """
        Return None when added the congregation (address) to this cluster.
        Return address of left or right congregation when search should continue.
        """
        if self.cluster.addLeft(address) or self.cluster.addRight(address):
            return None
        i = self.congregationAttempts.newHere()
        self.save()
        if i < 0:
            return self.left()
        return self.right()

    def getParam(self) -> dict:
        """
        Return param describing this cluster.
        """
        params = {"top": self.connect}
        if self.left():
            params["left"] = self.left()
        if self.right():
            params["right"] = self.right()
        return params


# from inspect import currentframe
# def Error(stack: list, error:str) -> str:
#    cf = currentframe()
#    return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error


class Congregation(RootHJ):
    """
 The Congregation is deployed on every host within the Hallelujah database,
 with the following purpose:
 1. route OAM messages between Congregations;
 2. monitor the host for its capacity to support Jah;
 3. maintain Worksheets holding details about the commands in this cluster,
    both past commands that are now deleted, and also commands that are
    presently running.
 3.1. worksheets has a journal of changes for the commands.

 Congregations provides a message deliver mechanism for less time sensative
 but reliable communications of Operations, Administration, and
 Maintenance (OAM). Delivery walks all Congregations in the network. Each
 Congregation delivers the Message to one of the local Hallelu or Jah, or
 otherwise forwards the Message to the next Congregation in the network.
 Hallelujah communicates with its local Congregation, or nearest Congregation.

 Three Congregations are grouped together to make a reliable cluster.
 Commands are located on one of the hosts, but the Worksheets across
 the cluster contains all commands on all of the hosts in the cluster.

 The failure of a host is detected by the remaining Congregations in the
 cluster. The cluster protects knowledge of the commands. Commands that
 were running on the failed host, remain dormant until a Hallelujah restarts
 them.
    """

    def __init__(self, port: int, processdir: str, connectaddr: (str, int)):
        super().__init__(cwd=os.getcwd(),
                         title="congregation",
                         congregationPort=port, port=port)
        self.hosts = set()
        self.jah_count = 0
        self.usage = MUsage()
        self.processCmd.update({
            "": self.start,
            "_ConReq_": self.ConReq,
            "_ConCfm_": self.ConCfm,
            "_usageReq_": self.usageReq,
            "_cmdInd_": self.cmdInd,
            "_sheetInd_": self.sheetInd,
            "_sheetReq_": self.sheetReq,
            "_cmdReq_": self.cmdReq,
            "_JahReq_": self.JahReq,
            "_STOP_": self.Stop
        })
        self.conreqTimer = mTimer(1)
        self.processTimers = mTimer(5)
        self.pingTimers = mTimer(10)
        self.processdir = processdir
        self.cluster = Cluster(self.processdir, connectaddr)
        p = os.path.join(processdir, ".worksheets")
        if not os.path.exists(p):
            os.mkdir(p)
        self.ws = MWorksheets(p)

    def ConReq(self, key: MUDPKey, cmd: dict):
        """
        Request is redirected to where the new congregation can join
        a database cluster.
        """
        if cmd["params"]["routing"]: # Routing to the summit.
            if self.cluster.parent():
                self.sendCfm(req=cmd, title="_ConCfm_", params={
                    "routing": True,
                    "Congregation": self.cluster.parent()
                })
                return
        addr = self.cluster.newConHere()
        if addr:
            self.sendCfm(req=cmd, title="_ConCfm_", params={
                "routing": False,
                "Congregation": addr
            })
            return
        params={
            "routing": None,
            "Congregation": None
        }
        params["cluster"] = self.cluster.getParam()
        params["cluster"]["worksheet"] = self.ws
        self.sendCfm(req=cmd, title="_ConCfm_", params=params)

    def ConCfm(self, key: MUDPKey, cmd: dict):
        """
        A new Congregation receiving the concfm.
        """
        self.conreqTimer.stop(k=1)
        p = cmd["params"]
        # Redirect request towards where the connection will be made.
        if p["routing"] is True:
            self.conreqTimer.start(k=1, v={})
            self.sendReq(
                title="_ConReq_",
                params={"routing": True},
                remoteAddr=p["Congregation"]
            )
            return
        # Connection has been made.
        self.cluster.parents = p["cluster"]
        self.save()

    def _redirectingWalk(self, key: MUDPKey, cmd: dict) -> (bool, dict):
        """
        Bool is True when congregation is first seen.
        Bool is False when congregation was seen before.
        Dict return params when redirecting.
        """
        p = cmd["params"]
        firstSeen = None
        params = {}
        if p["routing"]: # Routing to the summit.
            if self.cluster.parent():
                firstSeen = False
                params["routing"] = True
                params["Congregation"] = self.cluster.parent()
            else:
                firstSeen = True # Start walking from the summit congregation.
                params["routing"] = False
                if self.cluster.left():
                    params["Congregation"] = self.cluster.left()
                elif self.cluster.right():
                    params["Congregation"] = self.cluster.right()
                else:
                    params = None
        else: # walking the tree.
            params["routing"] = False
            if key.getAddr() == self.cluster.left():
                firstSeen = False # Back to congregation from the left-side.
                if self.cluster.right():
                    params["Congregation"] = self.cluster.right()
                elif self.cluster.parent():
                    params["Congregation"] = self.cluster.parent()
                else:
                    params = None
            elif key.getAddr() == self.cluster.right():
                firstSeen = False # Back to congregation from the right-side.
                if self.cluster.parent():
                    params["Congregation"] = self.cluster.parent()
                else:
                    params = None
            elif key.getAddr() == self.cluster.parent():
                firstSeen = True # Congregation on right/left of parent.
                if self.cluster.left():
                    params["Congregation"] = self.cluster.left()
                elif self.cluster.right():
                    params["Congregation"] = self.cluster.right()
                else:
                    params["Congregation"] = self.cluster.parent()
            else:
                raise Exception(f"""Walking tree but key {key} not parent
 {self.cluster.parent()} not left {self.cluster.left} and not right
 {self.cluster.right}""")
        return (firstSeen, params)

    def cmdInd(self, key: MUDPKey, cmd: dict):
        """ Find ALL commands. """
        (check, redirectingParams) = self._redirectingWalk(key, cmd)
        if check: # Check this congregation for the cmd.
            p = cmd["params"]
            filters = p["filters"]
            cmduuid = self.ws.nextCmdUuid(filters.get("cmduuid",None))
            while cmduuid: # Check that the cmd is a match for the filtering.
                cmd = self.ws.findCmd(
                    filters.get("sheetuuid",None), cmduuid,
                    filters.get("feed",None)
                )
                if cmd: # Got a cmd and route the next CmdInd back here.
                    self.sendCfm(
                        req=cmd, title="_cmdRsp_",
                        params = {
                            "filters": filters,
                            "routing": False,
                            "Congregation": self.cluster.connect,
                            "cmd": self.ws.getCmdUuid(cmduuid)
                        }
                    )
                    return
                cmduuid = self.ws.nextCmdUuid(cmduuid)
        self.sendCfm(req=cmd, title="_cmdRsp_", params=redirectingParams)

    def sheetInd(self, key: MUDPKey, cmd: dict):
        """ Find ALL sheets. """
        (check, redirectingParams) = self._redirectingWalk(key, cmd)
        if check: # Check this congregation for the sheet.
            p = cmd["params"]
            filters = p["filters"]
            sheet = None
            if "sheetUuid" in filters:
                sheet = self.ws.get(filters["sheetUuid"],None)
            elif p["sheetUuid"]:
                search = True
                for sheet in self.ws:
                    if search:
                        search = sheet["uuid"] != p["sheetUuid"]
                    else:
                        break
            else:
                for sheet in self.ws:
                    break
            if sheet: # Got a sheet and route the next SheetInd back here.
                self.sendCfm(
                    req=cmd, title="_sheetRsp_",
                    params = {
                        "filters": filters,
                        "routing": False,
                        "Congregation": self.cluster.connect,
                        "sheet": sheet
                    }
                )
                return
        self.sendCfm(req=cmd, title="_sheetRsp_", params=redirectingParams)

    def schReq(self, key: MUDPKey, cmd: dict):
        """ Update schema in each Congregation. """
        (updateHere, params) = self._redirectingWalk(key, cmd)
        if updateHere:
            p = cmd["params"]
            self.ws.changeSchema(p["schema"])
        self.sendCfm(req=cmd, title="_schCfm_", params=params)

    def _redirectingReq(self, key: MUDPKey, cmd: dict, check) -> (bool, dict):
        """
        Bool is True when congregation should take the new request.
        Bool is False when continue walking to another congregation.
        Dict return params when continue walking.
        """
        p = cmd["params"]
        if p["routing"]: # Routing to the summit.
            if self.cluster.parent():
                return (
                    False,
                    {"routing": True, "Congregation": self.cluster.parent()}
                )
        rv = check()
        if rv < 1 and self.cluster.left():
            return (
                False,
                {"routing": True, "Congregation": self.cluster.left()}
            )
        elif rv > 1 and self.cluster.right():
            return (
                False,
                {"routing": True, "Congregation": self.cluster.right()}
            )
        # rv == 0, or no left, or no right.
        return (True, None)

    def sheetReq(self, key: MUDPKey, cmd: dict):
        """ Update sheet """
        (addHere, params) = self._redirectingReq(
            key,cmd,self.cluster.sheetAttempts.newHere)
        if addHere:
            p = cmd["params"]
            params={}
            params["status"] = self.ws.updateSheet(
                uuid=p["sheetUuid"], oldtitle=p["oldname"],
                title=p["newname"], changelog=True)
        self.sendCfm(req=cmd, title="_sheetCfm_", params=params)

    def cmdReq(self, key: MUDPKey, cmd: dict):
        """ update/create cmd. """
        (addhere,params) = self._redirectingReq(
            key,cmd,self.cluster.commandAttempts.newHere)
        if not addhere:
            self.sendCfm(req=cmd, title="_cmdCfm_", params=params)
            return
        p = cmd["params"]
        uuid = p["cmdUuid"]
        (useroldparams, useroldselected, userolddesc) = self.ws.paramsCmd(
            cmd=p["oldcmd"], at=cmd["cmd"]
        )
        (usernewparams, usernewselected, usernewdesc) = self.ws.paramsCmd(
            cmd=p["newcmd"], at=cmd["cmd"]
        )
        error = self.ws.updateCmd(
            wsn=self.ws.getCmdUuidWS(uuid), cmdUuid=uuid,
            cmdname="", oldselected=useroldselected, selected=usernewselected,
            changelog=True
        )
        if error: # Abort cmdReq.
            self.sendCfm(
                req=cmd, title="_cmdCfm_",
                params = {
                    "status": error,
                    "routing": False
                }
            )
            return
        self.ProcessStop(title="h_", cmd=cmd)
        self.ProcessReq(
            "_cmdCfm_", params=p,
            title="h_", cmd=cmd,
            processType=Hallelu,
            processArgs=Hallelu.args(
                os.getcwd(), p["cmdUuid"],
                self.port, self.halleludir
            )
        )
        # Cfm is sent by self.tick().
        # self.sendCfm(req=cmd, title="_cmdCfm_", params=None)

    def start(self, cmd: dict):
        """ Get list of running processes. """
        if MLogger.isDebug():
            mlogger.debug(self.title+" start")
        # No parent but with a connection address, so try connecting.
        if not self.cluster.parent() and self.cluster.connect:
            self.conreqTimer.start(k=1, v={})
            self.sendReq(
                title="_ConReq_",
                params={"routing": True},
                remoteAddr=self.cluster.connect
            )
            return
        for fn in os.listdir(path=self.processdir):
            if (
                fn.endswith(".json") and
                (
                    fn.startswith("h_") or
                    fn.startswith("j_")
                )
            ):
                ffn = os.path.join(self.processdir, fn)
                if self._isProcessRunning(ffn):
                    self.pingTimers.start(ffn)
                    if MLogger.isDebug():
                        mlogger.debug(self.title+" "+fn +
                                      " Hallelu or Jah still running")
                else:
                    if MLogger.isDebug():
                        mlogger.debug(self.title+" "+fn +
                                      " Hallelu or Jah not running")

    def usageReq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd, title="_usageCfm_", params={
            "host": self.usage.host,
            "cpuUsage": self.usage.cpuUsage(),
            "diskUsage": self.usage.diskUsage(self.halleludir),
            "memoryUsage": self.usage.memoryUsage(),
            "timestamp": MZdatetime().strftime()
        })

    def Stop(self, cmd: dict) -> None:
        raise Exception("Stopping")

    def JahReq(self, key: MUDPKey, cmd: dict) -> None:
        p = cmd["params"]
        self.ProcessReq("_JahCfm_", "j_", cmd, Jah,
                        Jah.args(os.getcwd(), p["cmdUuid"], self.port,
                                 self.halleludir))

    def getTitle(self, fn: str) -> str:
        return fn[0:fn.index("_")]

    def ProcessStop(self, title: str, cmd: dict) -> bool:
        p = cmd["params"]
        fn = os.path.join(self.halleludir,
                          title + "_" + p["cmdUuid"] + ".json")
        return self.rmProcessFile(fn)

    def ProcessReq(self, cfm: str, params: dict, title: str, cmd: dict,
                   processType: any, processArgs: list) -> None:
        """
        Create process file and start process, schedule a timer to check that
        the process has started.
        """
        p = cmd["params"]
        uuid = p["cmdUuid"]
        fn = os.path.join(self.halleludir, title + "_" + uuid + ".json")
        if self.createProcessfile(fn, cmd):
            processArgs.append(MLogger.isDebug())
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+fn+" starting process")
            p = Process(target=processType.child_main, args=processArgs)
            p.start()
        self.processTimers.start(fn, {"msg": cfm, "params": params})

    def tick(self) -> bool:
        """Check if newly started processes have started by their port number
           being in the process-file. Send Cfm with the port number when the
           process started, and without a port number when process failed to
           start. Also, check the running processes that they are still running
           by the last modified timestamp being updated on their process-file.
           Delete stale process-file, and send _STOP_ request to that process.
           Processes are created again by whatever created them in the first
           place, catering for scenarios like the node dying or overload.
           """
        didSomething = super().tick()
        for k, v in self.conreqTimer.expired():
            if MLogger.isDebug():
                mlogger.debug(self.title+" tick : conreq expired")
            self.sendReq(
                title="_ConReq_",
                params={"first": True},
                remoteAddr=self.cluster.connect
            )
        for fn, expired, cfm in self.processTimers.walk():
            if MLogger.isDebug():
                mlogger.debug(self.title+" tick : "+fn+" "+str(expired) +
                              " "+str(cfm))
            didSomething = True
            (cmd, port) = self.readProcessFile(fn)
            if port != 0:
                if MLogger.isDebug():
                    mlogger.debug(self.title+" "+fn +
                                  " successfully started on port "+str(port))
                self.processTimers.stop(fn)
                self.pingTimers.start(fn)
                if cfm:
                    self.sendCfm(req=cmd, title=cfm, params={
                        "ip": self.host,
                        "port": port
                    })
            elif expired:
                if MLogger.isDebug():
                    mlogger.debug(
                        self.title+" "+fn +
                        ":removed; Zero port, taking too long to start")
                self.rmProcessFile(fn)
                if cfm:
                    self.sendCfm(req=cmd, title=cfm, params={
                        "ip": self.host,
                        "port": 0
                    })
        for fn, v in self.pingTimers.expired():
            didSomething = True
            if self._isProcessRunning(fn):
                self.pingTimers.start(fn)
        return didSomething

    def _isProcessRunning(self, fn: str) -> int:
        """ Return port number when process is running, otherwise return 0. """
        if not os.path.exists(fn):
            return 0
        (cmd, port) = self.readProcessFile(fn)
        if not self.isExpiredProcessFile(fn):
            return port
        if port == 0:
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+fn +
                              " stale and without a port, removing")
        else:
            addr = (self.host, port)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.bind(addr)
                if MLogger.isDebug():
                    mlogger.debug(self.title+" "+fn +
                                  " stale, port in use, sending stop")
                self.sendReq("_STOP_", {}, addr)
            except Exception:
                pass
        if MLogger.isDebug():
            mlogger.debug(self.title+" "+fn+" stale removing")
        os.remove(fn)
        return 0

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="""Congregation monitors
 the host and start Halleleujah, Halleu and Jah""")
        parser.add_argument('processdir', help="""Path to the directory where
 processing is tracked in files""")
        parser.add_argument('--port', help="Port number, default is 59990")
        parser.add_argument('-c', '--connect', help="""IP:port used when first
 connecting to the database""")
        parser.add_argument('-d', '--debug', help="debug", action="store_true")
        args = parser.parse_args()
        if not args.port:
            args.port = 59990
        else:
            args.port = int(args.port)
        if args.debug:
            MLogger.init("DEBUG")
        h = Congregation(port=args.port, processdir=args.processdir,
                         connectaddr=args.connect)
        h.poll()


if __name__ == "__main__":
    Congregation.main()
