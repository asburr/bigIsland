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
from magpie.src.mTimer import mTimer
from magpie.src.musage import MUsage
from magpie.src.mzdatetime import MZdatetime
from hallelujah.root import RootHJ
from hallelujah.jah import Jah
from hallelujah.hallelu import Hallelu
from hallelujah.hallelujah import Hallelujah
from multiprocessing import Process
import argparse
from magpie.src.mlogger import MLogger


#from inspect import currentframe
#def Error(stack: list, error:str) -> str:
#    cf = currentframe()
#    return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error


class Congregation(RootHJ):
    """
 The Congregation is deployed on every host within the Hallelujah cluster to
 monitor the host for its capacity to support more or less hallelu and Jah.
 The Congregation starts Hallelujah on the master host.

 Hallelujah communicates with the Congregation to launch Hallelu which
 are scattered across the cluster. Hallelu are less resource needy, and
 it's assumed they will run on the spare CPU cycles on a host with a full
 deployment of Jahs. Jah are single threaded, and cannot use more than one
 CPU, and the Congregation starts no more than one Jah per CPU.

 The congregation is unaware of Hallelujah's organization policy for Jahs.
 Still, it is worth noting here, that Hallelujah manages work in streams.
 External input is processed by Jahs too, these Jahs report backlogs to their
 Hallelu which in turn creates more Jahs. Some Jahs hold transient data which
 is distributed to other Jahs and not held within the Jah. These Jahs
 can be stopped, and stopping a Jah is the responsibility of the Hallelu,
 and again is triggered by the backlog reporting. The Congregation has the
 ability to shutdown transient Jahs too, to free up resources for additional
 streams. The end user can decrease the capcity of other streams when
 Hallelu cannot create a new stream.

 Hallelu will shutdown their Jah that are not streaming data. And will
 request the Jah restart when there is another request to stream.
 
 Other Jahs are holding data that is persistant. There is a copy
 of the data on disk, and a Jah is restarted with the data from disk.
 Restart occurs when an outgoing stream is requested. Also, a restart occurs
 when an incoming stream is requested, and the Jah will update the data on
 disk from the incoming stream of data.

 Hallelujah sends _HalleluReq_ or _JahReq_. Congregation creates the process,
 and forwards Req to the new process which responds to Hallelujah.
    """
    def __init__(self, port: int, halleludir: str, worksheet: str):
        super().__init__(cwd=os.getcwd(), halleludir=halleludir, title="congregation", port=port)
        self.hosts = set()
        self.jah_count = 0
        self.usage = MUsage()
        self.processCmd.update({
            "": self.start,
            "_usageReq_": self.usageCmd,
            "_HalleluReq_": self.HalleluReq,
            "_JahReq_": self.JahReq,
            "_STOP_": self.Stop
        })
        self.processTimers = mTimer(5)
        self.pingTimers = mTimer(10)
        if worksheet:
            self.createProcessfile("hj.json", {"cmdUuid":"", "params": {"worksheetdir": worksheet}})

    def start(self, cmd: dict):
        """ Read process-files in halls-dir. Create process that does not already exist.
        """
        for fn in os.listdir(path=self.halleludir):
            if not fn.endswith(".json"):
                continue
            ffn = os.path.join(self.halleludir,fn)
            if fn == "hosts.json":
                # Local host file has all hosts that this congregation is aware of.
                with open(ffn,"r") as f:
                    for line in f:
                        j = json.loads(line)
                    if j["host"] not in self.hosts:
                        self.hosts[j["host"]] = j["hallelujah"]
                if self.host not in self.hosts:
                    self.hosts.add(self.host)
                    with open(ffn,"a") as f:
                        s=json.dumps({"host": self.host})+"\n"
                        f.write(s)
            elif fn.startswith("h_") or fn.startswith("j_"):
                if self._isProcessRunning(ffn):
                  self.pingTimers.start(ffn)
            elif fn.startswith("hj_"):
                if self._isProcessRunning(ffn):
                    self.pingTimers.start(ffn)
                else:
                    (cmd,port) = self.readProcessFile(ffn)
                    self.ProcessReq(None, "hj", cmd, Hallelujah)

    def usageCmd(self, cmd: dict) -> None:
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
        self.ProcessReq("_HalleluCfm_", "h_", cmd, Hallelu)

    def JahReq(self, cmd: dict) -> None:
        self.ProcessReq("_JahCfm_", "j_", cmd, Jah)

    def getTitle(self, fn:str) -> str:
        return fn[0:fn.index("_")]

    def ProcessReq(self, cfm: str, title: str, cmd: dict, processType: any) -> None:
        uuid = cmd["cmdUuid"]
        fn = os.path.join(self.halleludir,title + "_" + uuid + ".json")
        if self.createProcessfile(fn,cmd):
            p = Process(target=processType.child_main,
                        args=[os.getcwd(), uuid, self.port, self.halleludir])
            p.start()
        self.processTimers.start(fn,cfm)

    def tick(self) -> bool:
        """Check if newly started processes have started by their port number
           being in the process-file. Send Cfm with the port number when the
           process started, and without a port number when process failed to 
           start. Also, check the running processes that they are still running
           by the last modified timestamp being updated on their process-file.
           Delete stale process-file, and send _STOP_ request to that process.
           """
        didSomething = super().tick()
        for fn, expired, cfm in self.processTimers.walk():
            didSomething = True
            (cmd,port) = self.readProcessFile(fn)
            if port != 0:
                if MLogger.isDebug():
                    MLogger.log(self.title+" "+fn+" successfully started on port "+str(port))
                self.processTimers.stop(fn)
                if cfm:
                    self.sendCfm(req=cmd,title=cfm, params={
                        "ip": self.host,
                        "port": port
                    })
            elif expired:
                if MLogger.isDebug():
                    MLogger.log(self.title+" "+fn+":removed; Zero port, taking too long to start")
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

    def _isProcessRunning(self, fn:str) -> bool:
        if not self.isExpiredProcessFile(fn):
            return True
        (cmd,port) = self.readProcessFile(fn)
        if port == 0:
            if MLogger.isDebug():
                MLogger.log(self.title+" "+fn+" stale and without a port, removing")
        else:
            if MLogger.isDebug():
                MLogger.log(self.title+" "+fn+" stale and stopping process, removing")
            addr = (self.host,port)
            self.sendReq("_STOP_", {},addr)
        os.remove(fn)
        return False

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Congregation monitors the host and start Halleleujah, Halleu and Jah")
        parser.add_argument('halleludir', help="Path to hallelu directory where processing is tracked in files")
        parser.add_argument('--port', help="Port number, default is 59990")
        parser.add_argument('-d', '--debug', help="debug", action="store_true")
        parser.add_argument('-w', '--worksheet', help="Identifies that this host is where Hallelujah runs")
        args = parser.parse_args()
        if not args.port:
            args.port = 59990
        else:
            args.port = int(args.port)
        if args.debug:
            MLogger.init("DEBUG")
        h = Congregation(port=args.port, halleludir=args.halleludir, worksheet=args.worksheet)
        h.poll()


if __name__ == "__main__":
    Congregation.main()