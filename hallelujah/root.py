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
from magpie.src.mudp import MUDP, MUDPBuildMsg, MUDPKey
from time import time, sleep
import socket
from pathlib import Path
import sys
from magpie.src.mlogger import MLogger, mlogger


class RootH():
    """
 RootH: Root for a process that is communicating in the database.
 Default behaviour is to allocate a port.
    """
    def __init__(self, title: str, congregationPort: int, port: int = 0):
        self.host = socket.gethostname()
        self.congregation_addr = (self.host, congregationPort)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket_timeout = 5.0
        self.s.settimeout(self.socket_timeout)
        try:
            self.s.bind((self.host, port))
        except:
            if MLogger.isError():
                mlogger.error(self.title+" address in use " + str(self.host)+":"+str(self.port))
            raise
        self.port = self.s.getsockname()[1]
        self.localAddress = (self.host, self.port)
        self.title = title
        self._stop = False
        self.mudp = MUDP(socket=self.s, skipBad=False)
        self.processCmd = {}
        self.processCmd[""] = self.commandDoNothing

    def stop(self) -> None:
        print("stop")
        self._stop = True

    def commandDoNothing(self, cmd: dict) -> None:
        pass

    def poll(self) -> None:
        if MLogger.isDebug():
            mlogger.debug(self.title+" start " + str(self.host)+":"+str(self.port))
        self.processCmd[""]({})  # Run the start cmd.
        didSomething = False
        while not self._stop:
            if didSomething:
                didSomething = False
                if MLogger.isDebug():
                    mlogger.debug(self.title+" waiting")
            for (key, content, eom) in self.mudp.recv():
                didSomething = True
                cmd = json.loads(content)
                if MLogger.isDebug():
                    mlogger.debug("Poll:"+str(cmd))
                if "__remote_address__" not in cmd:
                    # The remote_address is the originator and is stored in
                    # the command, so the response is sent to the originator.
                    cmd["__remote_address__"] = key.getAddr()
                if "__request_id__" not in cmd:
                    # The request id is stored in the command, so the response
                    # is to the original request id.
                    cmd["__request_id__"] = key.getRequestId()
                n = self.processCmd.get(cmd["cmd"],self.processCmd.get("_", None))
                if n == None:
                    raise Exception("Unexpected message " + str(cmd))
                if MLogger.isDebug():
                    mlogger.debug(self.title+" recv "+str(key)+" "+str(cmd))
                n(cmd)
            if not didSomething and not self.tick():
                sleep(0.1)
        if MLogger.isDebug():
            mlogger.debug(self.title+" stopped")
        self._stop = False

    def tick(self) -> bool:
        """Placeholder for any periodic work. Return True when work was done. """
        return False

    def sendReq(self, title: str, params: dict, remoteAddr: (str,int)) -> None:
        if MLogger.isDebug():
            mlogger.debug(self.title+" sendReq "+title+" to "+str(remoteAddr))
        self.mudp.send(
            content=json.dumps({"cmd": title, "params": params}),
            eom=True,
            msg=MUDPBuildMsg(MUDPKey(addr=remoteAddr))
        )

    def sendCfm(self, req:dict, title: str, params: dict) -> None:
        remoteAddr = req["__remote_address__"]
        requestId = req["__request_id__"]
        if MLogger.isDebug():
            mlogger.debug(f"{self.title} sendCfm {title} to {remoteAddr}:{requestId} params {params}")
        self.mudp.send(
            content=json.dumps({"cmd": title, "params": params}),
            eom=True,
            msg=MUDPBuildMsg(MUDPKey(addr=remoteAddr,
            requestId=requestId))
        )


class RootHJ(RootH):
    """
 RootHJ: Root for database components managed by Congregation.
 Touches the ProcessFile, the last modified time being an indication to
 Congregation that this process is alive.
    """
    def __init__(self, cwd: str, title: str, congregationPort: int, port: int = 0):
        super().__init__(title, port=port, congregationPort=congregationPort)
        os.chdir(cwd)

    def readProcessFile(self, fn: str) -> (dict, int):
        if not os.path.exists(fn):
            return (None, 0)
        with open(fn, "r") as f:
            line = f.readline()
            cmd=json.loads(line)
            if "__remote_address__" in cmd:
                # Remote address is tuple but saved as list in json format, convert back to tuple.
                ra = cmd["__remote_address__"]
                cmd["__remote_address__"] =(ra[0], ra[1])
            line = f.readline()
            if len(line) > 0:
                port = json.loads(line)["port"]
            else:
                port = 0
            return (cmd, port)

    def rmProcessFile(self, fn: str) -> bool:
        if not os.path.exists(fn):
            return False
        with open(fn, "r") as f:
            line = f.readline()
            line = f.readline()
            port = 0
            if line is not None:
                try:
                    port = json.loads(line)["port"]
                except:
                    pass
            if port > 0:
                addr = (self.host,port)
                self.sendReq("_STOP_", {},addr)
            if MLogger.isDebug():
                mlogger.debug(self.title+" Remove "+fn)
            os.remove(fn)
            return True

    def createProcessfile(self, fn: str, cmd: dict) -> bool:
        if os.path.exists(fn):
            if self.isExpiredProcessFile(fn):
                self.rmProcessFile(fn)
            else:
                if MLogger.isDebug():
                    mlogger.debug(self.title+" "+fn+" exists "+fn)
                (c,p) = self.readProcessFile(fn)
                if c == cmd:
                    return False  # Process already running.
                self.rmProcessFile(fn)
        with open(fn,"w") as f:
            line = json.dumps(cmd)+"\n"
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+fn+" writing "+line)
            f.write(line)
        return True # Created a new process file.

    def isExpiredProcessFile(self, fn: str) -> bool:
        d = time() - os.path.getmtime(fn)
        l = self.socket_timeout*3
        if d > l:
            if MLogger.isDebug():
                mlogger.debug(fn+" processfile expired "+str(d)+" "+str(l))
            return True
        else:
            return False


class RootHJC(RootHJ):
    """
  RootHJC: Root for Hallelu and Jah; those with a command. Reads command from
  file.
    """
    def __init__(self, cwd: str, uuid: str, halleludir: str, title: str, congregationPort: int, port: int = 0):
        super().__init__(cwd, title, port=port, congregationPort=congregationPort)
        self.halleludir = halleludir
        self.id = uuid
        self.fn = os.path.join(self.halleludir,title+self.id+".json")
        (self.cmd,port) = self.readProcessFile(self.fn)
        if self.cmd is None:
            raise Exception("process file does not exist "+self.fn)
        if port != 0:
            if self.isExpiredProcessFile(self.fn):
                self.rmProcessFile(self.fn)
                port = 0
            else:
                raise Exception("process file already has a port number"+self.fn)
        self.cmdname = self.cmd["cmd"]
        with open(self.fn, "a") as f:
            j = {"port": self.port}
            line = json.dumps(j)+"\n"
            if MLogger.isDebug():
                mlogger.debug(self.title+" "+self.fn+" add:"+line)
            f.write(line)
        (cmd,port) = self.readProcessFile(self.fn)
        if cmd != self.cmd:
            raise Exception("process file has different cmd "+self.fn)
        if self.port != port:
            raise Exception("process file has different port "+self.fn)
        self.keepaliveTimer = mTimer(5)
        self.keepaliveTimer.start(self.fn)

    def tick(self) -> bool:
        """Update the last modified time for the file associated with this process.
           Exit when file has been removed by Congregation and that occurs when
           file is stale and has not been updated here, and when processing should
           stop"""
        if not os.path.exists(self.fn):
            sys.exit()
        didSomething = super().tick()
        for fn,v in self.keepaliveTimer.expired():
            didSomething = True
            Path(fn).touch()
            self.keepaliveTimer.start(fn)
        return didSomething
