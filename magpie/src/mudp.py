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

# A UDP wrapper, designed for database request and response.
# UDP loss is detected.  Remote user is notified of the loss, and can decide
# to continue to receive the remaining content, or stop receiving the
# remaining content.
# 
# UDP loss is detect by gaps in sequence ids:
# 1. Message id is two hex digits.
# 2. Content id is two hex digits.
# 3. Chunk id is a two hex digit.
# The messages formats:
#  <message id>O<request id><single content>
#  <message id>B<request id>o<content id><first content>
#  <message id>Co<content id><next content>
#  <message id>Fo<content id><last content>
# When content is too large it is divided into chunks:
#  <message id>O<request id>b<chunkid><first chunk>
#  <message id>c<chunkid><next chunk>
#  <message id>f<chunkid><last chunk>
# The Client API:
#  c = MUDP(serverAddr,clientSocket, maxPayload=128)
#  c.send("hello", requestId=1, eom=False)
#  c.send("hello", eom=True)
#  c.send("world", eom=True)
# The server API:
#  s = MUDP(None,serverSocket, maxPayload=128)
#  for content in s.recv():
#    print(content)
import socket
import select
import json
import traceback


class MUDP:
    @staticmethod
    def nextId(i: int) -> int:
        return (i + 1) & 0xff

    @staticmethod
    def prevId(i: int) -> int:
        return (i - 1) & 0xff

    def __init__(self, addr: any, socket: any,
                 maxPayload: int=65527):
        self.maxPayload = maxPayload
        self.addr = addr
        self.s = socket
        self.contentId = 0
        self.firstContent = True
        self.chunkId = 0
        self.requestId = 0
        self.sndMsgId = 0
        self.rcvMsgId = 0
        self.buffer = "%02x" % self.sndMsgId
        self.i = 2
        self.recvMsgs = {}
        self.contentHdrLen = len("B00")         # B<requestid>
        self.chunkOHdrLen = len("o001111")    # o<contentId><chunkLen>
        self.chunkHdrLen = len("b00112222")   # b<contentId><chunkId><chunkLen>
        self.sensibleSpaceForContent = self.contentHdrLen + (self.chunkHdrLen * 2)
        if maxPayload > 65527:
            raise Exception("maxPayload above UDP maximum "+str(maxPayload))
        if maxPayload < self.sensibleSpaceForContent:
            raise Exception("maxPayload too small at "+str(maxPayload)+" smallest="+str(self.sensibleSpaceForContent))
        self.skipBad = True
        self.skipMsgId = -1

    def _append(self, s: str):
        self.buffer += s
        self.i += len(s)
        # print("_append " + self.buffer + " " + str(self.i) +" " +s)
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
            self.sndMsgId = self.nextId( self.sndMsgId )
            self.buffer = "%02x" % self.sndMsgId
            self.i = 2
        
    def send(self, content: str, requestid:int, eom: bool) -> None:
        if self.firstContent:  # First content, use O and B.
            if eom:
                self.firstContent = True
                self._append("O%02x"%requestid)
            else:
                self.firstContent = False
                self._append("B%02x"%requestid)
        else:  # Next content, use F or C.
            if eom:
                self._append("F")
                self.firstContent = True
            else:
                self.firstContent = False
                self._append("C")
        self.contentId = self.nextId( self.contentId )
        contentLen = len(content)
        if self._room() >= self.chunkHdrLen + contentLen:
            self._append("o" + ("%02x%02x%04x"%(self.contentId, self.chunkId, contentLen) ) )
            self._append(content)
            self.chunkId = self.nextId( self.chunkId )
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
            self._append("%02x%02x%04x" % (self.contentId, self.chunkId, len(chunk)))
            self._append(chunk)
            self.chunkId = self.nextId( self.chunkId )
            remainingContentLen = contentLen - contentIdx
            self._send(eom=(remainingContentLen>0))
        self._send(eom=eom)

    def recv(self) -> str:
        while True:
            try:
                ready = select.select([self.s], [], [], 1)
                if not ready[0]:
                    break
                txt = ""
                (data, ip_port) = self.s.recvfrom( self.maxPayload )
                txt = data.decode('utf-8')
                if self.skip > 0:
                    self.skip -= 1
                    if self.skip == 0:
                        # print("Skipping " + txt)
                        continue
                # print("recv " +txt)
                for msgid, txt in self.decode(txt):
                    yield (msgid, txt, ip_port)
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
        if nxtI > self.l:
            print("Truncated message. Check MTU settings on all servers!")
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
        if self.skipBad:
            if self.skipMsgId != -1:
                self.skipMsgId = -1
                # Reset ids, but only for a first packet i.e. O or B.
                self.rcvMsgId = rcvMsgId
                label = self._decodeStr(1)
                if label not in ["O", "B"]:
                    self.skipMsgId = rcvMsgId
                    return
                self.requestId = self._decodeHex(2)
                label = self._decodeStr(1)
                if label not in ["o", "b"]:
                    self.skipMsgId = rcvMsgId
                    return
                self.contentId = self.prevId(self._decodeHex(2))
                self.chunkId = self._decodeHex(2)
                self.i = 2
                
                # print("resetting ids to: "+str(self.rcvMsgId)+ "," + str(self.contentId) + "," + str(self.chunkId))
        if self.rcvMsgId != rcvMsgId:
            if self.skipBad:
                # print("Starting skipping Bad msg id " + str(rcvMsgId) + " "+str(self.rcvMsgId))
                self.skipMsgId = rcvMsgId
                return
            else:
                raise Exception("Bad msg id " + str(rcvMsgId) + " "+str(self.rcvMsgId))
        self.rcvMsgId = self.nextId( self.rcvMsgId )
        while self._decodeRemaining() > 0:
            label = self._decodeStr(1)
            if label in ["O", "B", "C", "F"]:
                if label in ["O", "B"]:
                    self.requestId = self._decodeHex(2)
                self.content = ""
                self.contentId = self.nextId( self.contentId )
            elif label in ["o", "b", "c", "f"]:
                contentId = self._decodeHex(2)
                if self.contentId != contentId:
                    if self.skipBad:
                        # print("Starting skipping Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                        self.skipMsgId = rcvMsgId
                        return
                    # print(self.txt + " " + str(self.i))
                    raise Exception("Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                chunkId = self._decodeHex(2)
                if self.chunkId != chunkId:
                    if self.skipBad:
                        # print("Starting skipping Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                        self.skipMsgId = rcvMsgId
                        return
                    raise Exception("Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                self.chunkId = self.nextId( self.chunkId )
                chunkLen = self._decodeHex(4)
                self.content += self._decodeStr(chunkLen)
                if label in ["o", "f"]:
                    yield (self.requestId, self.content)
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

        client = MUDP(serverAddr,clientS, maxPayload=30)
        print(str(clientS.getsockname())+" > "+str(serverAddr))
        server = MUDP(None,serverS, maxPayload=30)
        print(str(serverS.getsockname())+" > "+str(clientAddr))
        server.skip = 0

        l = [("abcdefghijklmnopqrstuvwxyz", True), ("__samples", False), ("12345678901234567", False), ("123456789012345678", False), ("1234567890123456", True)]
        requestid = 0
        for txt, eom in l:
            # print("sending " + txt + " " + str(eom))
            client.send(txt, requestid=requestid, eom=eom)
            if eom:
                requestid += 1
        for requestid, txt, ip_port in server.recv():
            print("requestid("+str(requestid)+") \""+txt+"\" from"+str(ip_port))
        for requestid, txt, ip_por in server.recv():
            print("requestid("+str(requestid)+") \""+txt+"\" from"+str(ip_port))
        print("Msg ids, send %d, recv %d" % (client.sndMsgId, server.rcvMsgId))

        
if __name__ == "__main__":
    MUDP.main()
