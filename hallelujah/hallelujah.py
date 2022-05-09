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
from hallelujah.root import RootHJC
import os
from magpie.src.mlogger import MLogger


class _Congregations:
    """
    _Congregations: maintain usage order for addr(IP,port).
    """
    def __init__(self):
        self.nextCongregation = 0
        self.usage = [[]]*11

    def leastCongested(self) -> (str,int):
        for usage in self.usage:
            if usage:
                addr = usage.pop(0)
                usage.append(addr)
                return addr
        return None

    def usage(self, addr: (str,int), usage: int) -> None:
        if usage > 10 or usage < 0:
            raise Exception("ERROR: usage must be 0 to 10 "+str(usage))
        if addr not in self.congregations:
            self.usage[usage].append(addr)
        else:
            for usage in self.usage:
                if addr in usage:
                    usage.remove(addr)
            self.usage[usage].append(addr)


class Hallelujah(RootHJC):
    """
 Hallelujah is started by Congregation, there is one Hallelujah. It
 handles all user interations with the database.
    """
    def __init__(self, congregationPort: int, halleludir: str, worksheetdir: str):
        super().__init__(cwd=os.getcwd(), halleludir=halleludir, title="hj")
        self.ws = MWorksheets(worksheetdir)
        self.ws.expandcmds()
        self.processCmd.update({
            "": self.playworksheets,
            "_sheetsReq_": self.sheetsreq,
            "_sheetReq_": self.sheetreq,
            "_cmdReq_": self.cmdreq,
            "_streamReq_": self.streamreq
        })
        self.halleluAddr_cmdUUID = {}
        self.halleluAddr_feed = {}
        self.congregations = _Congregations()

    def playworksheets(self, cmd: dict) -> None:
        for wsn in self.ws.titles():
            for cmd in self.ws.sheet(wsn):
                self.nextCmd(cmd)

    def sheetsreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_sheetsCfm_", params=[{"uuid": w["uuid"], "name": w["name"], "filename": w["filename"]} for w in self.ws])

    def sheetreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_sheetCfm_", params=[{"cmd": sheetcmd, "hallelu": self.halleluAddr.get(sheetcmd["uuid"],("",0))} for sheetcmd in self.ws.getWorkSheetCmds(cmd["uuid"])])

    def cmdreq(self, cmd: dict) -> None:
        """
        cmdreq: Forward cmdreq to hallelu, or create Hallelu via Congration.
        """
        if cmd["cmd"]["uuid"] not in self.halleluAddr_cmdUUID:
            self.sendReq(title="_cmdReq_", params=cmd, remoteAddr=self.congregation[self.nextCongregation])
        self.sendCfm(req=cmd,title="_cmdCfm_", params={"status": "?"})

    def streamreq(self, cmd: dict) -> None:
        """
        streamreq: forward req to Hallelu.
        """
        if cmd["feed"] not in self.halleluAddr_feed:
            self.sendCfm(req=cmd,title="_streamCfm_", params={"state": "fail"})
        self.sendReq(title="_streamReq_", params=cmd, remoteAddr=self.halleluAddr_feed[cmd["feed"]])

    @staticmethod
    def child_main(cwd: str, uuid: str, congregationPort: int, halleludir: str, debug : bool=False):
        if debug:
            MLogger.init("DEBUG")
        h = Hallelujah(cwd, uuid, congregationPort, halleludir)
        h.poll()


if __name__ == "__main__":
    raise Exception("Hallelujah is started by congregation, using -m for master node where Hallelujah runs")