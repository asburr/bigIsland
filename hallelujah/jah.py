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

from magpie.src.mudp import MUDP, MUDPKey
import os.path
import traceback
# import ZipFile
# import gzip
from magpie.src.mworksheets import MWorksheets
from magpie.src.mudp import MUDPBuildMsg
import json
import socket
from hallelujah.cmds.files import Files
# from cmds.loadf import Loadf
from time import sleep
import threading
from multiprocessing import Process
import uuid
import argparse


# TestReceiver is the both Hallelu and Receiver. establish the stream, and
# also receives the stream too.
class TestReceiver(threading.Thread):
    def __init__(self, jahAddr: (str, int)):
        threading.Thread.__init__(self)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(1.0)
        self.s.bind((MUDP.getIPAddressForTheInternet(), 0))
        self.mudp = MUDP(socket=self.s, skipBad=False)
        print(" Tester says hello : " + str(self.s.getsockname()))
        self.msg = MUDPBuildMsg(MUDPKey(addr=jahAddr))

    def run(self) -> None:
        streamUuid = str(uuid.uuid4())
        j = json.dumps({"_streamReq_": {
            "streamUuid": streamUuid,
            "feed": "test.pcap",
            "burst": 1,
            "streamType": "serial"
        }})
        print("Tester (being Hallelu) sending streamReq to JAH: "+str(j),flush=True)
        remotekey=self.mudp.send(content=j, eom=True, msg=self.msg)
        if remotekey is None:
            raise Exception("Failed to send _streamReq_")
        print("Tester (being Hallelu) waiting for response : "+str(remotekey),flush=True)
        (content, eom) = next(self.mudp.recvResponse(remotekey,wait=2.0))
        j = json.loads(content)
        if "_streamCfm_" not in j:
            raise Exception("Bad msg "+str(j))
        j = j["_streamCfm_"]
        if j["state"] != "success":
            raise Exception("Bad _streamCfm_ "+str(j))
        print("Tester recv streamCfm: "+str(j),flush=True)
        addr = (j["jahs"][0]["ip"], j["jahs"][0]["port"])
        if addr != remotekey.getAddr():
            raise Exception("Jah test bad key got="+str(addr)+" exp="+str(remotekey))
        drs = json.dumps({"_dataReq_": {"streamUuid": streamUuid}})
        for i in range(10):
            print("Tester requesting data from " + str(self.msg.getRemoteKey()),flush=True)
            remotekey=self.mudp.send(content=drs, eom=True, msg=self.msg)
            if remotekey is None:
                raise Exception("Failed ot send _dataReq_")
            print("Tester waiting for data from " + str(remotekey),flush=True)
            (content, eom) = next(self.mudp.recvResponse(remotekey,wait=2.0))
            j = json.loads(content)
            if "_dataCfm_" not in j:
                raise Exception("Bad _data_Cfm_ "+str(j))
            j = j["_dataCfm_"]
            print("Tester received data "+str(j),flush=True)
            # Reconfig msg if next JAH has changed.
            ip = j["nxtJah"][0]["ip"]
            port = j["nxtJah"][0]["port"]
            if (ip != self.msg.getRemoteKey().getIP() or
                port != self.msg.getRemoteKey().getPort()):
                self.msg = MUDPBuildMsg(MUDPKey(addr=(ip,port)))
        print("Tester finished",flush=True)


class Jah():
    def __init__(self, identification: str, halleludir: str, worksheetdir: str):
        host = socket.gethostname()
        try:
            fn = os.path.join(halleludir,"hosts.json")
            with open(fn,"r") as f:
                j = json.load(f)
                self.summit_addr = (j[host]["ip"], j[host]["port"])
        except:
            raise Exception("Failed to find summit hallelu, "+host+", in "+fn)
        self.ip = MUDP.getIPAddressForTheInternet()
        self.port = 0
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.settimeout(5.0)
        # '' is ENYADDR, 0 causes bind to select a random port.
        # IPv6 requires socket.bind((host, port, flowinfo, scope_id))
        self.s.bind((self.ip, self.port))
        self.port = self.s.getsockname()[1]
        self.id = identification
        self.halleludir = halleludir
        fn = os.path.join(self.halleludir,"jah_" + self.id + ".json")
        with open(fn, "r") as f:
            j = json.load(f)
            self.cmd = j["cmd"]
        with open(fn, "w") as f:
            j["ip"] = self.ip
            j["port"] = self.port
            json.dump(j,f)
        self.ws = MWorksheets(worksheetdir)
        self.stop = False
        self.cmdname = MWorksheets.cmdName(self.cmd)
        if self.cmdname == "files":
            self.op = Files(self.cmd[self.cmdname])
        else:
            raise Exception("unknown command " + self.cmdname)
        self.mudp = MUDP(socket=self.s, skipBad=False)
        print(str(self.port)+":"+self.id+" jah says hello " + str(self.ip),flush=True)
        self.streams = {}

    def runCmd(self, remotecmd: any, requestId: int) -> None:
        cmdname = MWorksheets.cmdName(remotecmd)
        if cmdname == "_sample_":
            self.sample(remotecmd, requestId)
        elif cmdname == "_streamReq_":
            self.streamReq(remotecmd, requestId)
        elif cmdname == "_dataReq_":
            self.dataReq(remotecmd, requestId)
        else:
            raise Exception("Unknown command " + cmdname)

    def sample(self, cmd: any, requestId: int) -> None:
        key = MUDPKey(addr=cmd["__remote_address__"], requestId=requestId)
        msg=MUDPBuildMsg(remotekey=key)
        self.mudp.send(
            content=json.dumps({
                "_sample_response_": {
                    "schema": self.op.schema()
                }
            }),
            eom=False, msg=msg
        )
        cmd = cmd["_sample_"]
        for eom, sample in self.op.sample( cmd["feed"], cmd["N"]):
            self.mudp.send(
                content=json.dumps(sample),
                eom=eom, msg=msg
            )

    def streamReq(self, cmd: any, requestId: int) -> None:
        key = MUDPKey(addr=cmd["__remote_address__"], requestId=requestId)
        cmd = cmd["_streamReq_"]
        self.streams[cmd["streamUuid"]] = cmd
        del cmd["streamUuid"]
        msg=MUDPBuildMsg(remotekey=key)
        # print("JAH sending streamcfm to:"+str(key)+" from:"+str(self.s.getsockname()),flush=True)
        self.mudp.send(
            content=json.dumps({
                "_streamCfm_": {
                    "state": "success",
                    "jahs": [{"ip": self.ip, "port": self.port}]
                }
            }),
            eom=True, msg=msg
        )

    def dataReq(self, cmd: any, requestId: int) -> None:
        key = MUDPKey(addr=cmd["__remote_address__"], requestId=requestId)
        cmd = cmd["_dataReq_"]
        if cmd["streamUuid"] not in self.streams:
            return
        stream = self.streams[cmd["streamUuid"]]
        msg=MUDPBuildMsg(remotekey=key)
        j = {
                "_dataCfm_": {
                    "data": self.op.data(feedName=stream["feed"],n=stream["burst"]),
                    "nxtJah": [{"ip": self.ip, "port": self.port}]
                }
            }
        # print("JAH sending datacfm to:"+str(key)+" from:"+str(self.s.getsockname())+" "+str(j),flush=True)
        self.mudp.send(
            content=json.dumps(j),
            eom=True, msg=msg
        )

    def poll(self) -> None:
        while not self.stop:
            didSomething = False
            for (key, content, eom) in self.mudp.recv():
                # print("JAH recv" +content)
                didSomething = True
                cmd = json.loads(content)
                if "__remote_address__" not in cmd:
                    cmd["__remote_address__"] = key.getAddr()
                self.runCmd(cmd, key.getRequestId())
            if not didSomething:
                if not self.op.execute():
                    sleep(0.1)
        for p in self.processes:
            # Wait for child to terminate
            p.join()

    @staticmethod
    def child_main(identification: str, halleludir: str, worksheetdir: str) -> None:
        try:
            jah = Jah(identification, halleludir, worksheetdir)
            jah.poll()
        except:
            traceback.print_exc()
        print("Jah terminated " + str(jah.port))

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Jah testing")
        parser.add_argument('worksheetdir', help="Path to worksheet directory")
        parser.add_argument('halleludir', help="Path to hallelu directory")
        args = parser.parse_args()
        identification = "test"
        fn = os.path.join(args.halleludir,"jah_"+identification+".json" )
        j = {"port": 0, "ip": "127.0.0.1", "cmdtitle": "testing", "cmd": {"files": Files.testCmd()}}
        print("Writing to "+fn)
        with open(fn,"w") as f:
            json.dump(j,f)

        # Reset files testcase (-1).
        tc_i = 0
        while Files.runTestcase(-1,Files.testcases[tc_i]):
            tc_i += 1

        # Start Jah with the file test cmd.
        p = Process(target=Jah.child_main,
                    args=[identification, args.halleludir,args.worksheetdir])
        p.start()
        while not j["port"]:
            with open(fn,"r") as f:
                j = json.load(f)
            sleep(0.5)
        jahAddr = (j["ip"],j["port"])
        print("Jah started "+str(jahAddr))

        # run the testcases, to create new files.
        for i in range(3):
            while Files.runTestcase(i,Files.testcases[tc_i]):
                tc_i += 1

        # Create a Fake-Hallelu/Receiver, to establish and receive the stream.
        tester = TestReceiver(jahAddr)
        tester.start()
        
        # wait for Receiver to finish.
        tester.join()
        
        # Clean up the testcases
        for i in range(10):
            while Files.runTestcase(i,Files.testcases[tc_i]):
                tc_i += 1


if __name__ == "__main__":
    Jah.main()