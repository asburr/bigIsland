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
# There is a heirarchy of Hallelu. The first database operation is sent to
# the top Hallelu. The top Hallelu searches its children for a Hallelu that is
# running the same database operation. In this case, the child Hallelu is
# returned to the user. Otherwise, a new child Hallelu is created for the
# database operation and this Hallelu is returned to the user.
#
# The user's next database operation is sent to the child Hallelu, not the
# top Hallelu.
#
# A worksheet is one or more database operations. Worksheets are tracked
# in the database by a user provided name. Subsequent operations are part
# of the same worksheet when they are sent with the same name. Operations
# are available on the worksheet, at any level within the heirarcy.
#
# Communication with Hallelu is using JSON sent over a UDP socket. Each
# Hallelu has just one UDP socket, communication with the same Hallelu
# will use the same socket for all Users.
# 
# 
import socket
import select
import json
import os
import traceback
import re
from inspect import currentframe


def Error(stack: list, error:str) -> str:
    cf = currentframe()
    return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error


class Hallelu:
    @staticmethod
    def getIPAddressForTheInternet() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ret = s.getsockname()[0]
        s.close()
        return ret
        
    def __init__(self, port: int, ip: str, worksheetdir: str):
        self.verify_handlers = {
            "composite": self._verifyComposite,
            "listComposites": self._verifyListComposite,
            "feed": self._verifyFeed,
            "path": self._verifyPath,
            "field": self._verifyField,
            "str": self._verifyStr,
            "int": self._verifyInt,
            "email": self._verifyEmail,
            "fmt": self._verifyFmt,
            "any": self._verifyAny,
            "regex": self._verifyRegex,
            "bool": self._verifyBool
        }
        self.dir = worksheetdir
        cmds_schema_fn = os.path.join(self.dir, "worksheetHelp.json")
        try:
            with open(cmds_schema_fn,"r") as f:
                try:
                    self.cmds_schema = json.load(f)
                except json.JSONDecodeError as err:
                    print(err)
                    raise Exception("Failed to parse " + cmds_schema_fn)
                except Exception as e:
                    print(self.cmds_schema)
                    raise Exception("Failed to parse " + cmds_schema_fn + " " + str(e))
        except Exception as e:
            raise Exception("Failed to read " + cmds_schema_fn + str(e))
        if not os.path.isdir(worksheetdir):
            raise Exception("Failed to find worksheet dir " + worksheetdir)
        for fn in os.listdir(path=worksheetdir):
            if fn == "worksheetHelp.json":
                continue
            dfn = os.path.join(worksheetdir,fn)
            try:
                with open(dfn, "r") as f:
                    j = json.load(f)
                error = self.verifycmds(j)
                if error:
                    raise Exception(error)
                ip, port = self.owncmd(j[0])
                for cmd in j[1:]:
                    ip, port = self.nextcmd(ip, port, cmd)
            except json.JSONDecodeError as err:
                raise Exception("Failed to parse " + dfn + " " + str(err))
            except Exception as e:
                traceback.print_exc()
                raise Exception("Failed to parse " + dfn + " " + str(e))
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.setblocking(0)
        self.stop = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if not ip:
            hostip = self.getIPAddressForTheInternet()
        self.socket.bind((hostip, port))

    def poll(self):
        while not self.stop:
            ready = select.select([self.s], [], [], 1)
            if not ready[0]:
                continue
            (data, ip) = self.s.recvfrom(4096)
            if ip in self.partialMsg:
                data = self.partialMsg[ip] + data
                del self.partialMsg[ip]
            l = int(data[0:4])
            dl = len(data)
            if dl < l:
                self.partialMsg[ip] = data
                continue
            if dl > l:
                self.partialMsg[ip] = data[l:]
                continue
            try:
                j = json.load(data)
            except json.JSONDecodeError as err:
                print("Failed to parse cmds ")
                print(err)
            except Exception as e:
                print("Failed to parse cmds " + str(e))
            self.cmd(j)
            # self.s.sendto(bytesToSend, ip)

    def _verifyComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, dict):
            return Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        for k in cmd.keys():
            stack.append(k)
            if k not in schema:
                return Error(stack, "\nExpecting: " + str(list(schema.keys())) + "\ngot: " + k)
            error = self._verifycmd(stack, cmd[k], schema[k])
            if error:
                return error
            stack.pop()
        for k in schema.keys():
            if k in ["type", "desc", "choice", "eg", "default"]:
                continue
            if "default" not in schema[k]:
                # Mandatory
                if k not in cmd:
                    stack.append(k)
                    return Error(stack, "missing attribute " + k)
            elif schema[k]["default"] is None:
                # Optional
                pass
            else:
                # default value
                pass

    def _verifyListComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, list):
            return Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        for i, j in enumerate(cmd):
            stack.append("e"+str(i))
            error = self._verifyComposite(stack, j, schema)
            if error:
                return error
            stack.pop()

    def _verifyFeed(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))

    def _verifyPath(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))

    def _verifyField(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))

    def _verifyStr(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))

    def _verifyInt(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, int):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))

    def _verifyEmail(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))

    def _verifyFmt(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))

    def _verifyBool(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, bool):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))

    def _verifyAny(self, stack: list, cmd: any, schema: any) -> str:
        pass

    def _verifyRegex(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        try:
            re.compile(cmd)
        except Exception as e:
            return Error(stack, "Error in regex " + cmd + " " + str(e))

    def _verifycmd(self, stack: list, cmd: any, schema: any) -> str:
        t = schema["type"]
        if t not in self.verify_handlers:
            if t.endswith(".macro"):
                if t not in self.cmds_schema:
                    return Error(stack, "Unknonw macro named " + t)
                return self._verifycmd(stack, cmd, self.cmds_schema[t])
            else:
                return Error(stack, "Unknown type " + t)
        return self.verify_handlers[t](stack, cmd, schema)

    def verifycmds(self, j: any) -> str:
        for cmd in j:
            name = list(cmd.keys())[0]
            if name not in self.cmds_schema:
                return Error([], "Unexpected cmd name " + name)
            error = self._verifycmd([name], cmd[name], self.cmds_schema[name])
            if error:
                return "Error in cmd " + name + " " + error

    def owncmd(self, j: any) -> (str, int):
        return ("", 0)

    def nextcmd(self, ip:str, port: int, j: any) -> (str, int):
        return ("", 0)

    @staticmethod
    def main():
        Hallelu(port=1234, ip="", worksheetdir="./worksheets")


if __name__ == "__main__":
    Hallelu.main()