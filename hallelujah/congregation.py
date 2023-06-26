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
            # TODO; fix up congregations and worksheets from ConReq.
            self.leftCongregationAddress = None
            self.leftWorksheets = None
            self.leftConnectAttempts = 0
            self.rightCongregationAddress = None
            self.rightWorksheets = None
            self.rightConnectAttempts = 0
            self.commandAttempts = 0
            self.leftCommandAttempts = 0
            self.rightCommandAttempts = 0
            self.parents = []
            self.connect = connectaddr
            self.save()

    def parent(self) -> str:
        if not self.parents:
            return None
        return self.parents[0]

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.__dict__,f)

    def newCmdHere(self) -> bool:
        """
        Return True when new command should be added at this Congregation
        """
        if self.commandAttempts < self.leftCommandAttempts:
            if self.commandAttempts < self.rightCommandAttempts:
                self.commandAttempts += 1
                return True
        if self.leftCommandAttempts < self.rightCommandAttempts:
            self.leftCommandAttempts += 1
        else:
            self.rightCommandAttempts += 1
        return False

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
        p = os.path.join(processdir,".worksheets")
        self.ws = MWorksheets(p)

    def _redirecting(self, key: MUDPKey, cmd: dict) -> (bool, dict):
        """ Returns bool, True when this node is first, or False when this node has already been walked. Also returns the param to route a msg to the next node in the walk, or params is None when the walk ends. Redirecting is one of two states: accending to the summit congregation when routing is True; or, walking from the summit and through all congregations in the tree when routing is False. Walking starts at the summit and either goes left if there is a left, or goes right if there is a right, or the walk ends. Walking from the parent continues by going left if there is a left, or going right if there is a right, or going back up to the parent. Walking from the left continues by going right if there is a right, or going back up to the parent. Walking ends at the summit. A node may be walked three times: when walking down the tree on the left hand-side or on the right hand-side; and again when walking up from the left hand-side; and again when walking up from the right hand-side. For this reason, the processing of a node should be the first time which is frmo the parent, or the summit node is processed when the walk starts. """
        p = cmd["params"]
        first  = None # (True) first time this walk has seen this congregation, (false) otherwise.
        params = {} # params to message the next congregation in the walk of the tree of congregations.
        # params["routing"] (True) when routing to the summit, (False) when walking the congregations.
        if p["routing"]:
            # heading upwards, towards the summit Congregation.
            if self.cluster.parent():
                # Continue towards the summit Congregation.
                first  = False
                params["routing"] = True
                params["Congregation"] = self.cluster.parent()
            else:
                # This is the summit, start walking.
                first  = True
                params["routing"] = False
                if self.cluster.left:
                    params["Congregation"] = self.cluster.left
                elif self.cluster.right:
                    params["Congregation"] = self.cluster.right
                else:
                    params = None
        else:
            # walking the tree.
            params["routing"] = False
            if key.getAddr() == self.cluster.left:
                # Just walked up from the left node.
                first  = False
                if self.cluster.right:
                    params["Congregation"] = self.cluster.right
                elif self.cluster.parent:
                    params["Congregation"] = self.cluster.parent()
                else:
                    params = None
            elif key.getAddr() == self.cluster.right:
                # Just walked up from the right node.
                first  = False
                if self.cluster.parent():
                    params["Congregation"] = self.cluster.parent()
                else:
                    params = None
            elif key.getAddr() == self.cluster.parent():
                # Just walked down from parent node.
                first  = True
                if self.cluster.left:
                    params["Congregation"] = self.cluster.left
                elif self.cluster.right:
                    params["Congregation"] = self.cluster.right
                else:
                    params["Congregation"] = self.cluster.parent()
            else:
                raise Exception("Walking tree but key "+str(key)+" not parent "+str(self.cluster.parent())+" not left "+str(self.cluster.left)+" and not right "+str(self.cluster.right))
        return (first,params)

    def ConReq(self, key: MUDPKey, cmd: dict):
        """
        Request is redirected to where the new congregation can join the database in a cluster of up to three
        congregations.
        """
        (first, params) = self._redirecting(key, cmd)
        if not first:
            self.sendCfm(req=cmd,title="_ConCfm_", params=params)
            return
        if not self.cluster.left:
            self.cluster.left = cmd["__remote_address__"]
            self.cluster.save()
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "cluster": [{"Congregation": self.localAddress, "worksheet": self.ws}]
            })
            return
        if not self.cluster.right:
            self.cluster.right = cmd["__remote_address__"]
            self.cluster.save()
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "cluster": [self.localAddress, self.childLeft]
            })
            return
        # Route new Congregation to smallest branch on the left.
        if self.cluster.leftConnectAttempts < self.cluster.rightConnectAttempts:
            self.leftConnectAttempts += 1
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "resend": self.cluster.left
            })
        # Route new Congregation to smallest branch on the right.
        else:
            self.cluster.rightConnectAttempts += 1
            self.sendCfm(req=cmd,title="_ConCfm_", params={
                "resend": self.cluster.right
            })

    def ConCfm(self, key: MUDPKey, cmd: dict):
        """ We are a new Congregation receiving the concfm. """
        self.conreqTimer.stop(k=1)
        p = cmd["params"]
        # Redirect request towards where the connection will be made.
        if p["routing"] == True:
            params={"routing": p["routing"]}
            self.conreqTimer.start(k=1,v={})
            self.sendReq(
                title="_ConReq_",
                params=params,
                remoteAddr=p["resend"]
            )
            return
        # Connection has been made.
        self.cluster.parents = p["cluster"]
        self.save()

    def _walkDatabase(self, cmd: dict, params: dict, cfmTitle: str, getParams):
        """
        Walk database using the routing strategy: Starting at summit; Walk
        self then walk left hand side, and repeat; Walk right hand side then
        walk up to parent, and repeat.
        """
        # heading upwards, towards the summit Congregation.
        p = cmd["params"]
        if p["routing"] == True:
            if self.cluster.parent():
                params["routing"] = True
                params["Congregation"] = self.cluster.parent()
                self.sendCfm(req=cmd,title=cfmTitle, params=params)
                return
            p["routing"] = False
        # heading downwards, towards the next Congregation on the left
        if p["routing"] == False:
            for k,v in getParams(self,cmd):
                params[k] = v
            cmduuid = self.ws.nextCmdUuid(p["cmdUuid"])
            if cmduuid:
                params["routing"] = False
                params["Congregation"] = self.localAddress
                self.sendCfm(req=cmd,title="_cmdRsp_", params=params)
                return
            if self.cluster.left:
                params["routing"] = False
                params["Congregation"] = self.cluster.left
                self.sendCfm(req=cmd,title=cfmTitle, params=params)
                return
            p["routing"] = None
        # heading upwards, towards the next Congregation on the right
        if p["routing"] == None:
            if self.cluster.right:
                params["routing"] = False
                params["Congregation"] = self.cluster.right
                self.sendCfm(req=cmd,title=cfmTitle, params=params)
                return
            else:
                params["routing"] = None
                if self.cluster.parent():
                    params["Congregation"] = self.cluster.parent()
                    self.sendCfm(req=cmd,title=cfmTitle, params=params)
                else:
                    self.sendCfm(req=cmd,title=cfmTitle, params=params)
                return

    @staticmethod
    def cmdIndParams(self, cmd: dict):
        p = cmd["params"]
        yield ("cmd", self.ws.nextCmdUuid(p["cmdUuid"]))

    def cmdInd(self, key: MUDPKey, cmd: dict):
        """
        Find commands. Walk database using the routing strategy
        which left hand side, then right hand side. then up to parent.
        """
        p = cmd["params"]
        params={"filters": p["filters"]}
        self._walkDatabase(cmd,params,"_cmdRsp_",self.cmdIndParams)

    @staticmethod
    def schIndParams(self, cmd: dict):
        p = cmd["params"]
        self.ws.changeSchema(p["schema"])

    def schReq(self, key: MUDPKey, cmd: dict):
        """ Update schema in each Congregation.
        """
        params={}
        self._walkDatabase(cmd,params,"_schCfm_",self.schIndParams)

    def redirecting(self, key: MUDPKey, cmd: dict) -> bool:
        """ """
        p = cmd["params"]
        params={}
        # heading upwards, towards the summit Congregation.
        if p["routing"] == True:
            if self.cluster.parent():
                params["routing"] = True
                params["Congregation"] = self.cluster.parent()
                self.sendCfm(req=cmd,title="_cmdCfm_", params=params)
                return True
            else:
                p["routing"] == False
        # Walking the tree.
        elif p["routing"] == False:
            if self.cluster.right:
                params["routing"] = None
                params["Congregation"] = self.cluster.right
                self.sendCfm(req=cmd,title="_cmdCfm_", params=params)
            else:
                params["routing"] = None
                params["Congregation"] = self.cluster.parent()
                self.sendCfm(req=cmd,title="_cmdCfm_", params=params)
        return False

    def sheetReq(self, cmd: dict):
        """ Update sheet """
        if self.redirecting(cmd):
            return
        
        
    def cmdReq(self, key: MUDPKey, cmd: dict):
        """ update/create cmd """
        # heading upwards, towards the summit Congregation.
        p = cmd["params"]
        if self.redirecting(cmd):
            return
        # heading downwards, towards the command.
        if p["routing"] == False:
            uuid = p["cmdUuid"]
            version = int(p["version"])
            # New version.
            if version == 0:
                if self.cluster.newCmdHere():
                    self.ProcessReq(
                        "_cmdCfm_", params=params,
                        title="h_", cmd=cmd,
                        processType=Hallelu,
                        processArgs=Hallelu.args(
                            os.getcwd(), p["cmdUuid"],
                            self.port, self.halleludir
                        )
                    )
            # An existing command.
            else:
                # Is the command in this local worksheet?
                cmd = self.ws.getCmdUuid(uuid)
                if cmd:
                    # Update local worksheet.
                    (params, selected, desc) = self.ws.paramsCmd(cmd=cmd, at=p["cmd"])
                    error = self.ws.updateCmd(self.ws.getCmdUuidWS(uuid), uuid, selected, changelog=True)
                    if error:
                        # Stop the cmdReq with the error message.
                        params["error"] = error
                        self.sendCfm(req=cmd,title="_cmdCfm_", params=params)
                        return
                    # If local command is running here
                    if self.ProcessStop(title="h_", cmd=cmd):
                        # If there's a new version to start.
                        if version > 0:
                            self.ProcessReq(
                                "_cmdCfm_", title="h_", cmd=cmd,
                                processType=Hallelu,
                                processArgs=Hallelu.args(
                                    os.getcwd(), p["cmdUuid"],
                                    self.port, self.halleludir
                                )
                            )
            if self.cluster.left:
                params["routing"] = False
                params["Congregation"] = self.cluster.left
                self.sendCfm(req=cmd,title="_cmdCfm_", params=params)
                return
            else:
                p["routing"] = None
        
    def start(self, cmd: dict):
        """ Get list of running processes. """
        if MLogger.isDebug():
           mlogger.debug(self.title+" start")
        # No parent but with a connection address, so try connecting.
        if not self.cluster.parent() and self.cluster.connect:
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

    def JahReq(self, key: MUDPKey, cmd: dict) -> None:
        p = cmd["params"]
        self.ProcessReq("_JahCfm_", "j_", cmd, Jah, Jah.args(os.getcwd(), p["cmdUuid"], self.port, self.halleludir))

    def getTitle(self, fn:str) -> str:
        return fn[0:fn.index("_")]

    def ProcessStop(self, title: str, cmd: dict) -> bool:
        p = cmd["params"]
        fn = os.path.join(self.halleludir,title + "_" + p["cmdUuid"] + ".json")
        return self.rmProcessFile(fn)
        
    def ProcessReq(self, cfm: str, params: dict, title: str, cmd: dict, processType: any, processArgs:list) -> None:
        """
        Create process file and start process, schedule a timer to check that the process has started.
        """
        p = cmd["params"]
        uuid = p["cmdUuid"]
        fn = os.path.join(self.halleludir,title + "_" + uuid + ".json")
        if self.createProcessfile(fn,cmd):
            processArgs.append(MLogger.isDebug())
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+fn+" starting process")
            p = Process(target=processType.child_main,args=processArgs)
            p.start()
        self.processTimers.start(fn,{"msg": cfm, "params": params})

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