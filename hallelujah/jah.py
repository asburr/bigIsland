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
from hallelujah.root import RootHJC
from hallelujah.cmds.files import Files, Test

class Jah(RootHJC):
    """
 Jah is started by Congregation, there are one or more Jah for a command. It
 coordinates a partition of processing and data storage.
    """
    cmds = {
        "test": Test,
        "files": Files
    }
    def __init__(self, cwd: str, uuid:str, congregationPort: int, halleludir: str):
        super().__init__(cwd=cwd, uuid=uuid, halleludir=halleludir, title="j", congregationPort=congregationPort, debug=True)
        self.processCmd.update({
            "_streamReq_": self.streamreq,
            "_streamCanReq_": self.streamcanreq,
            "_streamTimeoutReq_": self.streamtimeoutreq,
            "_dataReq_": self.datareq
        })
        if self.cmdname not in self.cmdTypes:
            raise Exception("not a recognized cmd type "+self.cmdname)
        self.op = self.cmdTypes[self.cmdname](self.cmd)

    def streamreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_streamCfm_", params={
            "ip": self.host,
            "port": 0
        })

    def streamcanreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_streamCanCfm_", params={
            "ip": self.host,
            "port": 0
        })

    def streamtimeoutreq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_streamTimeoutCfm_", params={
            "ip": self.host,
            "port": 0
        })

    def datareq(self, cmd: dict) -> None:
        self.sendCfm(req=cmd,title="_dataCfm_", params={
            "ip": self.host,
            "port": 0
        })

    @staticmethod
    def child_main(cwd: str, uuid: str, congregationPort: int, halleludir: str):
        j = Jah(cwd, uuid, congregationPort, halleludir)
        j.poll()
