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


class Cluster():
    def __init__(self, path:str, connectaddr: (str,int)):
        if not os.path.exists(path):
            os.mkdir(path)
        self.path = os.path.join(path,'cluster.json')
        if os.path.exists(self.path):
            with open(self.path, "r") as f:
                  self.__dict__.update(**json.load(f))
            if self.connect != connectaddr:
                self.connect = connectaddr
                self.save()
        else:
            self.left = None
            self.right = None
            self.parents = []
            self.connect = connectaddr
            self.save()

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.__dict__,f)


#from inspect import currentframe
#def Error(stack: list, error:str) -> str:
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
    def __init__(self, port: int, processdir: str, connectaddr: (str,int)):
        super().__init__(cwd=os.getcwd(), title="congregation", congregationPort=port, port=port)
        self.hosts = set()
        self.jah_count = 0
        self.usage = MUsage()
        self.processCmd.update({
            "": self.start,
            "_ConReq_": self.ConReq,
            "_ConCfm_": self.ConCfm,
            "_usageReq_": self.usageReq,
            "_HalleluReq_": self.HalleluReq,
            "_cmdInd_": self.cmdInd,
            "_sheetReq_": self.sheetReq,
            "_cmdReq_": self.cmdReq,
            "_JahReq_": self.JahReq,
            "_STOP_": self.Stop
        })
        self.conreqTimers = mTimer(1)
        self.processTimers = mTimer(5)
        self.pingTimers = mTimer(10)
        self.processdir = processdir
        self.cluster = Cluster(self.processdir,connectaddr)
        self.ws = MWorksheets(os.path.join(processdir,".worksheets"))

    def ConReq(self, cmd: dict):
        """
        We are a connected Congregation receiving conReq from a new
        Congregation that wants to join the database.
        """
        # Initially, the request is redirected to the parent.
        if cmd["routing"] == True and self.parent:
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "routing": True,
                "resend": self.parent
            })
            return
        # Otherwise, the request is redirected down to where the new
        # congregation can join the database.
        # Connect new Congregation here, on the empty left.
        if not self.cluster.left:
            self.cluster.left = cmd["__remote_address__"]
            self.cluster.save()
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                    "cluster": [self.localAddress]
            })
            return
        # Connect new Congregation here, on the empty right.
        if not self.childRight:
            self.childRight = cmd["__remote_address__"]
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "cluster": [self.localAddress, self.childLeft]
            })
            return
        # Route new Congregation to smallest branch on the left.
        if self.childLeftSize < self.childRightSize:
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "resend": self.childLeft
            })
        # Route new Congregation to smallest branch on the right.
        else:
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "resend": self.childRight
            })

    def ConCfm(self, cmd: dict):
        """ Resend the ConReq, or retain address of other Congregation that are within the cluster. """
        self.conreqTimer.stop(k=1)
        params={"routing": cmd["routing"]}
        # Redirect request towards where the connection will be made.
        if "resend" in cmd:
            self.conreqTimer.start(k=1,v={})
            self.sendReq(
                title="_ConReq_",
                params=params,
                remoteAddr=cmd["resend"]
            )
            return
        # Connection has been made.
        self.cluster.parents = cmd["cluster"]
        self.save()

    def cmdInd(self, cmd: dict):
        """ Find commands. Walk database using the routing strategy
            which left hand side, then right hand side. then up to parent.
        """
        params={"filters": cmd["filter"]}
        # heading upwards, towards the summit Congregation.
        if cmd["routing"] == True:
            if self.parent:
                params["routing"] = cmd["routing"]
                params["Congregation"] = self.parent
                self.sendCfm(req=cmd,title="_cmdRsp_", params=params)
                return
            else:
                cmd["routing"] == False
        # heading downwards, towards the next Congregation on the left
        if cmd["routing"] == False:
            # Get next command on this host.
            cmduuid = self.ws.nextCmdUuid(cmd["cmdUuid"])
            if cmduuid:
                params["cmd"] = self.ws.getCmdUuid(cmduuid)
                params["routing"] = False
                params["Congregation"] = self.localAddress
                self.sendCfm(req=cmd,title="_cmdRsp_", params=params)
                return
            if self.cluster.left:
                params["routing"] = False
                params["Congregation"] = self.cluster.left
                self.sendCfm(req=cmd,title="_cmdRsp_", params=params)
                return
            else:
                cmd["routing"] == None
        # heading upwards, towards the next Congregation on the right
        if cmd["routing"] == None:
            if self.cluster.right:
                params["routing"] = False
                params["Congregation"] = self.cluster.right
                self.sendCfm(req=cmd,title="_cmdRsp_", params=params)
                return
            else:
                params["routing"] = None
                params["Congregation"] = self.parent
                self.sendCfm(req=cmd,title="_cmdRsp_", params=params)
                return

    def sheetReq(self, cmd: dict):
        """ Update sheet """
        
    def cmdReq(self, cmd: dict):
        """ update/create cmd """
        # TODO; version(0) means new command, verion(>0) means existing command
        # TODO; cmd included in process file.
        
    def start(self, cmd: dict):
        """ Get list of running processes. """
        if MLogger.isDebug():
           mlogger.debug(self.title+" start")
        # No parent but with a connection address, so try connecting.
        if not self.cluster.parents and self.cluster.connect:
            self.conreqTimer.start(k=1,v={})
            self.sendReq(
                title="_ConReq_",
                params={"first": True},
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
                ffn = os.path.join(self.processdir,fn)
                if self._isProcessRunning(ffn):
                    self.pingTimers.start(ffn)
                    if MLogger.isDebug():
                        mlogger.debug(self.title+" "+fn+" Hallelu or Jah still running")
                else:
                    if MLogger.isDebug():
                        mlogger.debug(self.title+" "+fn+" Hallelu or Jah not running")

    def usageReq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_usageCfm_", params={
            "host": self.usage.host,
            "cpuUsage": self.usage.cpuUsage(),
            "diskUsage": self.usage.diskUsage(self.halleludir),
            "memoryUsage": self.usage.memoryUsage(),
            "timestamp": MZdatetime().strftime()
        })

    def Stop(self, cmd: dict) -> None:
        raise Exception("Stopping")

    def HalleluReq(self, cmd: dict) -> None:
        self.ProcessReq("_HalleluCfm_", "h_", cmd, Hallelu, Hallelu.args(os.getcwd(), cmd["cmdUuid"], self.port, self.halleludir))

    def JahReq(self, cmd: dict) -> None:
        self.ProcessReq("_JahCfm_", "j_", cmd, Jah, Jah.args(os.getcwd(), cmd["cmdUuid"], self.port, self.halleludir))

    def getTitle(self, fn:str) -> str:
        return fn[0:fn.index("_")]

    def ProcessReq(self, cfm: str, title: str, cmd: dict, processType: any, processArgs:list) -> None:
        """ Create process file and start process, schedule a timer to check that the process has started. """
        uuid = cmd["cmdUuid"]
        fn = os.path.join(self.halleludir,title + "_" + uuid + ".json")
        if self.createProcessfile(fn,cmd):
            processArgs.append(MLogger.isDebug())
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+fn+" starting process")
            p = Process(target=processType.child_main,args=processArgs)
            p.start()
        self.processTimers.start(fn,cfm)

    def tick(self) -> bool:
        """Check if newly started processes have started by their port number
           being in the process-file. Send Cfm with the port number when the
           process started, and without a port number when process failed to 
           start. Also, check the running processes that they are still running
           by the last modified timestamp being updated on their process-file.
           Delete stale process-file, and send _STOP_ request to that process.
           Processes are created again by whatever created them in the first place,
           catering for scenarios like the node dying or overload.
           """
        didSomething = super().tick()
        for k,v in self.conreqTimers.expired():
            if MLogger.isDebug():
                mlogger.debug(self.title+" tick : conreq expired")
            self.sendReq(
                title="_ConReq_",
                params={"first": True},
                remoteAddr=self.cluster.connect
            )
        for fn, expired, cfm in self.processTimers.walk():
            if MLogger.isDebug():
                mlogger.debug(self.title+" tick : "+fn+" "+str(expired)+" "+str(cfm))
            didSomething = True
            (cmd,port) = self.readProcessFile(fn)
            if port != 0:
                if MLogger.isDebug():
                    mlogger.debug(self.title+" "+fn+" successfully started on port "+str(port))
                self.processTimers.stop(fn)
                self.pingTimers.start(fn)
                if cfm:
                    self.sendCfm(req=cmd,title=cfm, params={
                        "ip": self.host,
                        "port": port
                    })
            elif expired:
                if MLogger.isDebug():
                    mlogger.debug(self.title+" "+fn+":removed; Zero port, taking too long to start")
                self.rmProcessFile(fn)
                if cfm:
                    self.sendCfm(req=cmd,title=cfm, params={
                        "ip": self.host,
                        "port": 0
                    })
        for fn, v in self.pingTimers.expired():
            didSomething = True
            if self._isProcessRunning(fn):
              self.pingTimers.start(fn)
        return didSomething

    def _isProcessRunning(self, fn:str) -> int:
        """ Return port number when process is running, otherwise return 0. """
        if not os.path.exists(fn):
            return 0
        (cmd,port) = self.readProcessFile(fn)
        if not self.isExpiredProcessFile(fn):
            return port
        if port == 0:
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+fn+" stale and without a port, removing")
        else:
            addr = (self.host,port)
            try:
                s = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
                s.bind(addr)
                if MLogger.isDebug():
                    mlogger.debug(self.title+" "+fn+" stale, port in use, sending stop")
                self.sendReq("_STOP_", {},addr)
            except:
                pass
        if MLogger.isDebug():
            mlogger.debug(self.title+" "+fn+" stale removing")
        os.remove(fn)
        return 0

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Congregation monitors the host and start Halleleujah, Halleu and Jah")
        parser.add_argument('processdir', help="Path to the directory where processing is tracked in files")
        parser.add_argument('--port', help="Port number, default is 59990")
        parser.add_argument('-c', '--connect', help="IP:port used when first connecting to the database")
        parser.add_argument('-d', '--debug', help="debug", action="store_true")
        args = parser.parse_args()
        if not args.port:
            args.port = 59990
        else:
            args.port = int(args.port)
        if args.debug:
            MLogger.init("DEBUG")
        h = Congregation(port=args.port, processdir=args.processdir, connectaddr=args.connect)
        h.poll()


if __name__ == "__main__":
    Congregation.main()