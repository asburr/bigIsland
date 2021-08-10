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


class Hallelu:
    @staticmethod
    def getIPAddressForTheInternet() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ret = s.getsockname()[0]
        s.close()
        return ret
        
    def __init__(self, port: int, ip: str, worksheetHelp: dict):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.setblocking(0)
        self.stop = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if not ip:
            hostip = self.getIPAddressForTheInternet()
        self.socket.bind((hostip, port))
        self.cmds = {}
        for cmd in worksheetHelp:
            self.cmds[cmd["short"]] = cmd

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
            self.input(data)
            # self.s.sendto(bytesToSend, ip)

    def input(self, data: bytes):
        

    @staticmethod
    def main():
        h = Hallelu(port=1234,ip="")
        with open("worksheets/worksheetHelp.json","r") as f:
            j = json.load(f)
            f.

if __name__ == "__main__":
    Hallelu.main()