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
import os
from hallelujah.root import RootHJC


class Hallelu(RootHJC):
    """
 Hallelu is started by Congregation, there is one Hallelu per command. It
 coordinates all user interations with the command; including setting up
 data streams.
    """
    def __init__(self, cwd: str, uuid: str, halleludir: str, congregationPort: int = 0):
        super().__init__(cwd=os.getcwd(), uuid=uuid, halleludir=halleludir, title="Hallelu", port=0, congregationPort=congregationPort)
        self.processCmd.update({
            "_cmdReq_": self.cmdreq,
            "_streamReq_": self.streamreq,
            "_streamCanReq_": self.streamcanreq,
            "_streamTimeoutReq_": self.streamtimeoutreq,
            "_dataReq_": self.datareq
        })

    def cmdreq(self, cmd: dict) -> None:
        """
        cmdreq: Updated command, check differences, and make adjustments.
        Empty command means terminate the current command.
        """
        self.sendCfm(req=cmd,title="_cmdCfm_", params={
            "ip": self.host,
            "port": 0
        })

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
        h = Hallelu(cwd, uuid, halleludir, congregationPort)
        h.poll()

if __name__ == "__main__":
    raise Exception("Hallelu is started by congregation under instruction from Hallelujah")