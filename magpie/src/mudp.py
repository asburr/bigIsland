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

# This is a little wrapper on top of UDP. A message is started between
# two UDP ports, and one or more text content can be sent. Small contents
# are packed into the same UDP payload, the payload is sent when full or at
# the end of the mesage. Large contents is packed across many UDP payloads,
# and in this case the content is yielded at the remote end before all of
# the message is sent.
# UDP loss is detected. Content is lost when one of its chunks is lost.
# Remote users are notified of the loss of content, and can decide to continue
# to receive the remaining content, or stop receiving the remaining content.
# 
# UDP payloads start with a (Msg Id), two hex digits, it is a one up number
# that increments for each new message.
# After (Msg Id), is the content indicator and content id. Content Id is two
# hex digits, it is a one up number that increments for each new content in
# the message.
#  O<single content>
#  B(Content Id)<first content>
#  C(Content Id)<next content>
#  F(Content Id)<last content>
# Content is divided into chunks when it is too large to fit into the
# remaining space in the UDP payload.
#  o<no chunks, single chunk>
#  b(Chunk Id)<first chunk>
#  c(Chunk Id)<next chunk>
#  f(Chunk Id)<last chunk>
# The application program interface is as follows,
#  m.send("hello", eom=True)
#  m.send("hello", eom=False)
#  m.send("world", eom=True)

import socket
import select
import json
import traceback


class MUDP:
    @staticmethod
    def nextId(i: int) -> int:
        return (i + 1) & 0xff

    def __init__(self, addr: any, socket: any,
                 maxPayload: int=65527):
        self.maxPayload = maxPayload
        self.addr = addr
        self.s = socket
        self.contentId = 0
        self.firstContent = True
        self.chunkId = 0
        self.sndMsgId = 0
        self.rcvMsgId = 0
        self.buffer = None
        self.i = 0
        self._initBuffer()
        self.recvMsgs = {}
        self.contentHdrLen = len("B11")       # B<contentId>
        self.chunkOHdrLen = len("o1111")      # o<chunkLen>
        self.chunkHdrLen = len("b001111")     # b<chunkId><chunkLen>
        self.sensibleSpaceForContent = self.contentHdrLen + (self.chunkHdrLen * 2)

    def _initBuffer(self):
        self.buffer = "%02x" % self.sndMsgId
        self.i = 2
        self.sndMsgId = self.nextId( self.sndMsgId )
        self.firstContent = True

    def _append(self, s: str):
        self.buffer += s
        self.i += len(s)
        # print("_append " + self.buffer + " " + str(self.i))
        if self.i > self.maxPayload:
            raise Exception("Beyond the pale")

    def _room(self) -> int:
        return self.maxPayload - self.i

    def _send(self, eom: bool=False):
        if self.i == 2:  # Nothing but msgId in buffer!
            return
        if eom or self._room() < self.sensibleSpaceForContent:
            # print("sent "+str(len(self.buffer))+":"+self.buffer)
            self.s.sendto(self.buffer.encode('utf-8'), self.addr)
            self._initBuffer()
        
    def send(self, content: str, eom: bool) -> None:
        if self.firstContent:  # First content, use O and B.
            self.firstContent = False
            if eom:
                self._append("O")
            else:
                self._append("B%02x" % self.contentId)
                self.contentId += self.nextId( self.contentId )
        else:  # Next content, use F or C.
            if eom:
                self._append("F%02x" % self.contentId)
            else:
                self._append("C%02x" % self.contentId)
            self.contentId = self.nextId( self.contentId )
        contentLen = len(content)
        if self._room() >= self.chunkOHdrLen + contentLen:
            self._append("o" + ("%04x"%contentLen) + content)
            self._send(eom)
            return
        firstChunkId = True
        contentIdx = 0
        remainingContentLen = contentLen - contentIdx
        while remainingContentLen:
            r = self._room() - self.chunkHdrLen
            if firstChunkId:
                firstChunkId = False
                self._append("b")
            else:
                if remainingContentLen > r:
                    self._append("c")
                else:
                    self._append("f")
            if remainingContentLen > r:
                nxtContentIdx = contentIdx + r
            else:
                nxtContentIdx = contentIdx + remainingContentLen
            chunk = content[contentIdx:nxtContentIdx]
            contentIdx = nxtContentIdx
            self._append(("%02x" % self.chunkId) + ("%04x"%len(chunk)) + chunk)
            self.chunkId = self.nextId( self.chunkId )
            remainingContentLen = contentLen - contentIdx
            self._send(eom=(remainingContentLen>0))
        self._send(eom)

    def recv(self) -> str:
        while True:
            try:
                ready = select.select([self.s], [], [], 1)
                if not ready[0]:
                    break
                txt = ""
                (data, ip_port) = self.s.recvfrom( self.maxPayload )
                txt = data.decode('utf-8')
                for txt in self.decode(txt):
                    yield (txt, ip_port)
            except json.JSONDecodeError as err:
                traceback.print_exc()
                print((self.ip,self.port))
                print("Failed to parse cmds from " + str(ip_port))
                print(err)
                print(txt)
            except Exception as e:
                traceback.print_exc()
                print("Failed to parse cmds " + str(e) + " from " + str(ip_port))
                print(txt)

    def recvJson(self) -> dict:
        for txt, ip_port in self.recv():
            j = json.loads(txt)
            if "__remote_address__" not in j:
                j["__remote_address__"] = ip_port
            yield j

    def _decodeHex(self, size: int) -> int:
        try:
            nxtI = self.i + size
            ret = int(self.txt[self.i:nxtI],16)
            self.i = nxtI
            return ret
        except Exception as e:
            raise Exception(str(e)+"; at "+str(self.i)+":"+str(nxtI)+"="+self.txt[self.i:nxtI]+" l="+str(self.l)+"\nin "+self.txt)

    def _decodeStr(self, size: int) -> str:
        nxtI = self.i + size
        ret = self.txt[self.i:nxtI]
        self.i = nxtI
        return ret

    def _decodeRemaining(self) -> int:
        return self.l - self.i

    def decode(self, txt: str) -> str:
        self.txt = txt
        self.i = 0
        self.l = len(txt)
        rcvMsgId = self._decodeHex(2)
        if self.rcvMsgId != rcvMsgId:
            raise Exception("Bad msg id " + str(rcvMsgId) + " "+str(self.rcvMsgId))
        self.rcvMsgId = self.nextId( self.rcvMsgId )
        while self._decodeRemaining() > 0:
            label = self._decodeStr(1)
            if label in ["O", "B", "C", "F"]:
                self.content = ""
                if label in ["B", "C", "F"]:
                    contentId = self._decodeHex(2)
                    if self.contentId != contentId:
                        raise Exception("Bad contentId " + str(contentId))
                    self.contentId = self.nextId( self.contentId )
            elif label in ["o", "b", "c", "f"]:
                if label in ["b", "c", "f"]:
                    chunkId = self._decodeHex(2)
                    if self.chunkId != chunkId:
                        raise Exception("Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                    self.chunkId = self.nextId( self.chunkId )
                chunkLen = self._decodeHex(4)
                self.content += self._decodeStr(chunkLen)
                if label in ["o", "f"]:
                    yield self.content
                    self.content = ""
            else:
                raise Exception("Bad label " + label)

    @staticmethod
    def main():
        ip = "127.0.0.1"

        clientS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clientS.settimeout(5.0)
        clientS.bind((ip, 0))
        clientAddr = (ip, clientS.getsockname()[1])

        serverS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverS.settimeout(5.0)
        serverS.bind((ip, 0))
        serverAddr = (ip,serverS.getsockname()[1])

        client = MUDP(serverAddr,clientS, maxPayload=100)
        print(str(clientS.getsockname())+" > "+str(serverAddr))
        server = MUDP(clientAddr,serverS, maxPayload=100)
        print(str(serverS.getsockname())+" > "+str(clientAddr))

        l = [("abcdefghijklmnopqrstuvwxyz", True), ("__samples", False), ("1234", False), ("5678", True)]
        for (txt, eom) in l:
            print("sending " + txt + " " + str(eom))
            client.send(txt, eom=eom)
        for txt in server.recv():
            print(txt)
        for txt in server.recv():
            print(txt)
        
        
if __name__ == "__main__":
    MUDP.main()
