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
from magpie.src.mworksheets import MWorksheets, MJournalChange
from magpie.src.mudp import MUDPKey
from hallelujah.root import RootH
import os
from magpie.src.mlogger import MLogger, mlogger
from magpie.src.mTimer import mTimer
# from magpie.src.mzdatetime import MZdatetime
import argparse
import shutil
import threading
import time


class Hallelujah(RootH,threading.Thread):
    """
 Hallelujah is a thread that manages user interactions with the database.
 A local copy of the worksheet is maintained. The user can pull
 the latest changes from the database, or push the local changes into the
 database.
    """
    def __init__(self, congregationPort: int, worksheetdir: str, congregationHost: str=""):
        try:
            threading.Thread.__init__(self)
            RootH.__init__(self,title="hj", congregationPort=congregationPort, congregationHost=congregationHost)
            if MLogger.isDebug():
               mlogger.debug(
                   f"{self.title} worksheetdir={worksheetdir}"
               )
            self.worksheets = MWorksheets(worksheetdir)
            self.processCmd.update({
                "_cmdRsp_": self.__cmdRsp,
                "_cmdCfm_": self.__cmdCfm
            })
            self.cmdTimer = mTimer(3)
            self.filters={}
            p=os.path.join(worksheetdir,".dbversion")
            shutil.rmtree(p,ignore_errors=True)
            os.mkdir(p)
            self.worksheets.copySchema(p)
            self.dbworksheets = MWorksheets(p)
            self.dbworksheets_state = None
            self.start()  # Start the thread, see self.run()
            self.pull()
            self.error = None
        except:
            self.stop = True
            raise

    def pull(self, __cmd: dict = None) -> str:
        """
        Queries the database for the commands and pull them into the local
        worksheet.
        """
        if self.dbworksheets_state:
            return self.dbworksheets_state
        self.dbworksheets_state = "pulling"
        v={
            "msgtype": "_cmdInd_",
            "params": {
                "filters": self.filters,
                "cmdUuid": None,
                "routing": True
            },
            "addr":self.congregation_addr
        }
        self.cmdTimer.start(k=1,v=v)
        self.dbworksheets.empty()
        self.sendReq(
            title=v["msgtype"],
            params=v["params"],
            remoteAddr=v["addr"]
        )
        while self.dbworksheets_state == "pulling":
            time.sleep(1)
        error = self.worksheets.pull(self.dbworksheets.dir)
        self.dbworksheets_state = None
        return error

    def __cmdRsp(self, key: MUDPKey, cmd: dict) -> None:
        """ Build worksheet from cmds in cmdRsp. Resend the first cmdind
            towards the summit congregation. Or, resend to the next congregation.
            Otherwise, no more cmds and then the worksheet is complete.
        """
        p = cmd["params"]
        c = p["cmd"]
        if c:
            (params, selected, description) = self.dbworksheets.paramsCmd(cmd=c,at=None)
            self.dbworksheets.updateCmd(c["uuid"], None, selected, changelog=False)
        # Get params from timer before stopping it.
        v = self.cmdTimer.get(1)
        self.cmdTimer.stop(1)
        # No more redirections means this is the last response.
        if "Congregation" not in cmd:
            self.dbworksheets.save(self.dbworksheets.dir)
            self.dbworksheets_state = "built"
            return
        # More redirections, copy the routing indicator and address from the response.
        v["params"]["routing"] = p["routing"]
        v["addr"] = p["Congregation"]
        self.cmdTimer.start(k=1,v=v)
        self.sendReq(
            title=v["msgtype"],
            params=v["params"],
            remoteAddr=v["addr"]
        )

    def push(self, change:MJournalChange) -> str:
        """
        Returns None when successfully pushed the change into the database. Return a string describing the error when failed to push the change into the database.
        """
        if self.dbworksheets_state:
            raise Exception("Two calls to push() at the same time is not supported")
        while True:
            v = {
                "msgtype": change.msgType(),
                "params": change.msgParams(),
                "addr":self.congregation_addr
            }
            self.dbworksheets_state = "pushing"
            self.cmdTimer.start(k=1,v=v)
            self.sendReq(
                title=v["msgtype"],
                params=v["params"],
                remoteAddr=v["addr"]
            )
            while self.dbworksheets_state == "pushing":
                time.sleep(1)
            if self.dbworksheets_state == "failed":
                self.dbworksheets_state = None
                return self.error
            self.dbworksheets_state = None
            return None

    def __cmdCfm(self, key: MUDPKey, cmd: dict) -> None:
        """
        Redirect cmdreq when cmdreq was successfull, or get the failure code.
        """
        v = self.cmdTimer.get(1)
        self.cmdTimer.stop(1)
        p = cmd["params"]
        if "Congregation" in p: # Redirect request.
            v["params"]["routing"] = p["routing"]
            print(v)
            self.cmdTimer.start(k=1,v=v)
            self.sendReq(
                title=v["msgtype"],
                params=v["params"],
                remoteAddr=p["Congregation"]
            )
        else:
            if p["status"] == "updated":
                self.dbworksheets_state = "pushed"
            else:
                self.dbworksheets_state = "failed"
                self.error = p["status"]
                
    def tick(self) -> bool:
        """ Handle timeout with retransmit to the local congregation. """
        didSomething = super().tick()
        for k, v in self.cmdTimer.expired():
            didSomething = True
            v["first"] = True
            v["addr"] = self.congregation_addr
            self.cmdTimer.start(k=k,v=v)
            print(v)
            self.sendReq(
                title=v["msgtype"],
                params=v["params"],
                remoteAddr=v["addr"]
            )
        return didSomething

    def run(self) -> None:
        self.poll()

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Hallelujah tester")
        parser.add_argument('port', help="Congregation port")
        parser.add_argument('dir', help="worksheet dir")
        parser.add_argument("-d",'--debug', help="Debug logging")
        args = parser.parse_args()
        if args.debug:
            MLogger.init("DEBUG")
        h = Hallelujah(
                congregationPort=int(args.port),
                worksheetdir=args.dir
            )
        h.stop()


if __name__ == "__main__":
    Hallelujah.main()