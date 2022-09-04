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
from magpie.src.mworksheets import MWorksheets
from root import RootHJC
import os
import json
from magpie.src.mlogger import MLogger
from magpie.src.mTimer import mTimer


class Hallelujah(RootHJC):
    """
 Hallelujah is started by Congregation, there is one Hallelujah. It
 handles user interations with the database and manages the worksheets.
    """
    @staticmethod
    def args(congregationPort: int, halleludir: str, worksheetdir: str):
        return [congregationPort, halleludir, worksheetdir]

    def __init__(self, congregationPort: int, halleludir: str, worksheetdir: str):
        super().__init__(cwd=os.getcwd(), uuid="", halleludir=halleludir, title="hj_", congregationPort=congregationPort)
        if MLogger.isDebug():
           self.log.debug(self.title+" halleludir="+halleludir+" worksheetdir="+worksheetdir)
        self.ws = MWorksheets(worksheetdir)
        self.ws.expandcmds()
        self.processCmd.update({
            "": self.playworksheets,
            "_sheetsReq_": self.sheetsreq,
            "_sheetReq_": self.sheetreq,
            "_cmdReq_": self.cmdreq,
            "_ParentCongregationCfm_": self._ParentCongregationCfm_,
            "_ChildCongregationCfm_": self._ChildCongregationCfm_,
            "_HalleluCfm_": self._HalleluCfm_,
            "_streamReq_": self.streamreq
        })
        self.halleluAddr_cmdUUID = {}
        with open(self.halleluAddr_cmdUUID_fn,"r") as f:
            line = next(f)
            while len(line):
                l = json.loads(line)
                if l[0] == "add":
                    self.halleluAddr_cmdUUID[l[1]] = l[2]
                else:
                    del self.halleluAddr_cmdUUID[l[1]]
                line = next(f)
        self.halleluAddr_feed = {}
        with open(self.halleluAddr_feed_fn,"r") as f:
            line = next(f)
            while len(line):
                l = json.loads(line)
                if l[0] == "add":
                    self.halleluAddr_feed[l[1]] = l[2]
                else:
                    try:
                        del self.halleluAddr_feed[l[1]]
                    except:
                        pass
                line = next(f)
        # Timers to manage CMD changes, keyed by cmdUuid.
        self.cmdreqTimers = mTimer(10)
        self.ParentCongregationReqTimers = mTimer(10)
        self.ChildCongregationReqTimers = mTimer(10)
        self.HalleluReqTimers = mTimer(10)

    def playworksheets(self, cmd: dict) -> None:
        for wsn in self.ws.titles():
            for cmd in self.ws.sheet(wsn)["cmds"]:
                self.cmdreq(cmd)

    def sheetsreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_sheetsCfm_", params=[{"uuid": w["uuid"], "name": w["name"], "filename": w["filename"]} for w in self.ws])

    def sheetreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_sheetCfm_", params=[{"cmd": sheetcmd, "hallelu": self.halleluAddr.get(sheetcmd["uuid"],("",0))} for sheetcmd in self.ws.getWorkSheetCmds(cmd["uuid"])])

    def cmdreq(self, cmd: dict) -> None:
        """ Forward cmdreq to hallelu, or search for Congregation to create a new Hallelu. """
        cmdUuid = cmd["cmdUuid"]
        halleluAddr = self.halleluAddr_cmdUUID.get(cmdUuid,None)
        if halleluAddr:
            self.sendReq(title="_cmdReq_", params=cmd, remoteAddr=halleluAddr)
            self.cmdreqTimers.start(cmdUuid,cmd)
        else:
            self.sendReq(title="_ParentCongregationReq_", params={"cmdUuid": cmdUuid}, remoteAddr=self.congregation_addr)
            self.ParentCongregationReqTimers.start(cmdUuid,(self.congregation_addr,cmd))

    def _ParentCongregationCfm_(self, cmd: dict) -> None:
        """ Search for summit Congregation. """
        cmdUuid = cmd["cmdUuid"]
        addr = cmd["__remote_address__"]
        timer = self.ParentCongregationReqTimers.getStop(cmdUuid)
        if timer == None:
            return
        (priorParentAddr, cmdreq) = timer
        if priorParentAddr == addr:
            self.sendReq(title="_ChildCongregationReq_", params={"cmdUuid": cmdUuid}, remoteAddr=addr)
            self.ChildCongregationReqTimers.start(cmdUuid,(addr,cmdreq))
        else:
            self.sendReq(title="_ParentCongregationReq_", params={"cmdUuid": cmdUuid}, remoteAddr=addr)
            self.ParentCongregationReqTimers.start(cmdUuid,(addr,cmdreq))

    def _ChildCongregationCfm_(self, cmd: dict) -> None:
        """ Search for child Congregation where a new Hallelu will be created. """
        cmdUuid = cmd["cmdUuid"]
        addr = cmd["__remote_address__"]
        timer = self.ChildCongregationReqTimers.getStop(cmd["cmdUuid"])
        if timer == None:
            return
        (priorChildAddr, cmdreq) = timer
        if priorChildAddr == addr:
            self.sendReq(title="_HalleluReq_", params=cmdreq, remoteAddr=addr)
            self.HalleluReqTimers.start(cmdUuid,cmdreq)
        else:
            self.sendReq(title="_ChildCongregationReq_", params={"cmdUuid": cmdUuid}, remoteAddr=addr)
            self.ChildCongregationReqTimers.start(cmdUuid,(addr,cmdreq))

    def _HalleluCfm_(self, cmd: dict) -> None:
        """ Congregation has created a Hallelu, send cmdCfm to the originator of the cmdreq. """
        cmdUuid = cmd["cmdUuid"]
        cmdreq = self.HalleluReqTimers.getStop(cmdUuid)
        if cmdreq == None:
            return
        addr = cmd["__remote_address__"]
        # Remove any uuid and feeds associated with this cmd.
        if cmdUuid in self.halleluAddr_cmdUUID:
            addr = self.halleluAddr_cmdUUID[cmdUuid]
            toDelete = []
            for feed in self.halleluAddr_feed:
                if self.halleluAddr_feed[feed] == addr:
                    toDelete.append(feed)
            for feed in toDelete:
                del self.halleluAddr_feed[feed]
            del self.halleluAddr_cmdUUID[cmdUuid]
        # Add uuid and feeds associated with this cmd.
        if cmd["status"] in ["created", "updated"]:
            self.halleluAddr_cmdUUID[cmdUuid] = addr
            with open(self.halleluAddr_cmdUUID_fn,"a+") as f:
                line = json.dumps(["add",cmdUuid,addr])+"\n"
                f.write(line)
            for feed in cmd["feeds"]:
                self.halleluAddr_feed[feed] = addr
                with open(self.halleluAddr_feed_fn,"a+") as f:
                    line = json.dumps(["add",feed,addr])+"\n"
                    f.write(line)
        elif cmd["status"] == "delete":
            del self.halleluAddr_cmdUUID[cmdUuid]
            with open(self.halleluAddr_cmdUUID_fn,"a+") as f:
                line = json.dumps(["del",cmdUuid,addr])+"\n"
                f.write(line)
            for feed in cmd["feeds"]:
                self.halleluAddr_feed[feed] = addr
                with open(self.halleluAddr_feed_fn,"a+") as f:
                    line = json.dumps(["del",feed,addr])+"\n"
                    f.write(line)
        # Let user know the request is complete.
        self.sendCfm(req=cmdreq,title="_cmdCfm_", params=cmd)

    def streamreq(self, cmd: dict) -> None:
        """ forward req to Hallelu. """
        if cmd["feed"] not in self.halleluAddr_feed:
            self.sendCfm(req=cmd,title="_streamCfm_", params={"state": "fail"})
        self.sendReq(title="_streamReq_", params=cmd, remoteAddr=self.halleluAddr_feed[cmd["feed"]])

    def tick(self) -> bool:
        """ Timeout during cmdreq terminates any further processing associated with the cmdreq. """
        didSomething = super().tick()
        for cmdUuid, cmdreq in self.cmdreqTimers.expired():
            didSomething = True
            self.sendCfm(req=cmdreq,title="_cmdCfm_", params={"status": "timeout"})
            self.ParentCongregationReqTimers.stop(cmdUuid)
            self.ChildCongregationReqTimers.stop(cmdUuid)
            self.HalleluReqTimers.stop(cmdUuid)
        for cmdUuid, priorParentAddr, cmdreq in self.ParentCongregationReqTimers.expired():
            didSomething = True
            self.sendCfm(req=cmdreq,title="_cmdCfm_", params={"status": "timeout"})
            self.ChildCongregationReqTimers.stop(cmdUuid)
            self.HalleluReqTimers.stop(cmdUuid)
        for cmdUuid, priorChildAddr, cmdreq in self.ChildCongregationReqTimers.expired():
            didSomething = True
            self.sendCfm(req=cmdreq,title="_cmdCfm_", params={"status": "timeout"})
            self.HalleluReqTimers.stop(cmdUuid)
        for cmdUuid, cmdreq in self.HalleluReqTimers.expired():
            didSomething = True
            self.sendCfm(req=cmdreq,title="_cmdCfm_", params={"status": "timeout"})
            self.HalleluReqTimers.stop(cmdUuid)
        return didSomething

    @staticmethod
    def child_main(congregationPort: int, halleludir: str, worksheetdir: str, debug : bool=False):
        if debug:
            MLogger.init("DEBUG")
        h = Hallelujah(congregationPort, halleludir, worksheetdir)
        h.poll()


if __name__ == "__main__":
    raise Exception("Hallelujah is started by congregation, using -m for master node where Hallelujah runs")