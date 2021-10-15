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
# A UDP wrapper, designed for database request and response.
# A reader thread ensures the socket recv buffer does not overflow,
# it queues content in memory. UDP loss is detected and recovered from,
# by skipping the content that was lost.
# A client waits for the response to a particular request.
# A server wait for the next request and for particular responses.
# Using Python multi-threads, there is a MUDP object is used for each socket,
# all thread threads send and receive on this socket using the
# same MUDP instance.
# 
# UDP loss is detect by gaps in sequence ids:
# 1. Request id is four hex digits, initial value is random then one up.
# 2. Content id is two hex digits, initial value is zero then one up.
# 3. Chunk id is a two hex digit, initial value is zero then one up.
# The messages formats:
#  <request id>O<content id>o<chunk id><only content>
#  <request id>B<content id>o<chunk id><first content>
#  <request id>C<content id>o<chunk id><next content>
#  <request id>F<content id>o<chunk id><last content>
# Check formats:
#  <request id>O<content id>o<chunkid><only chunk>
#  <request id>O<content id>b<chunkid><first chunk>
#  <request id>O<content id>c<chunkid><next chunk>
#  <request id>O<content id>f<chunkid><last chunk>
# The Client API:
#  c = MUDP(serverAddr, clientSocket)
#  requestId = c.requestId()
#  c.send("hello", requestId)
#  c.sendEOM("hello", requestId)
#  for content in c.recv(requestId):
#    print(content)
# The server API:
#  s = MUDP(None,serverSocket)
#  for addr, requestId, request in s.recv():
#    s.send("responsing to content", requestId, eom=True)
import socket
import select
import traceback
import threading
from time import sleep
import random


# Manage ids and content for a request and timeout too.
class MUDPDecodeMsg():
    def __init__(self, requestId: int):
        self.requestId = requestId
        if self.requestId is None:
            raise Exception("No request id.")
        self.contentId = 0
        self.chunkId= 0
        self.content = ""
        self.timer = 10
        self.i = 0
        self.l = 0
        self.txt = None
        self.skipContentId = -1
        self.skipBad = True

    def __str__(self):
        s="Decode msg "
        s+=" reqId="+str(self.requestId)
        s+=" cntId="+str(self.contentId)
        s+=" cnkId="+str(self.chunkId)
        if self.skipContentId != -1:
            s+=" Skipping content"
        return s

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
            print("Truncated message. Check MTU settings on servers!")
        ret = self.txt[self.i:nxtI]
        self.i = nxtI
        return ret

    def _decodeRemaining(self) -> int:
        return self.l - self.i

    def decode(self, txt: str) -> str:
        self.timer = 10
        self.txt = txt
        self.i = 4
        self.l = len(txt)
        if self.skipBad:
            if self.skipContentId != -1:
                # Reset ids, but only for a first packet i.e. O or B.
                label = self._decodeStr(1)
                if label not in ["O", "B"]:
                    return
                self.contentId = self._decodeHex(2)
                label = self._decodeStr(1)
                if label not in ["o", "b"]:
                    return
                self.chunkId = self._decodeHex(2)
                self.i = 4
                self.skipContentId = -1
                print("resetting ids to: " + str(self.contentId) + "," + str(self.chunkId))
        while self._decodeRemaining() > 0:
            label = self._decodeStr(1)
            if label in ["O", "B", "C", "F"]:
                self.chunkId = 0
                self.content = ""
                contentId = self._decodeHex(2)
                if self.contentId != contentId:
                    if self.skipBad:
                        print("Starting skipping Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                        self.skipContentId = contentId
                        return
                    # print(self.txt + " " + str(self.i))
                    raise Exception("Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                if label in ["O", "F"]:
                    self.contentId = 0
                else:
                    self.contentId = ( self.contentId + 1 ) & 0xff
            elif label in ["o", "b", "c", "f"]:
                chunkId = self._decodeHex(2)
                if self.chunkId != chunkId:
                    if self.skipBad:
                        print("Starting skipping Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                        self.skipContentId = contentId
                        return
                    raise Exception("Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                self.chunkId = ( self.chunkId + 1 ) & 0xff
                chunkLen = self._decodeHex(4)
                self.content += self._decodeStr(chunkLen)
                if label in ["o", "f"]:
                    yield self.content
                    self.content = ""
            else:
                raise Exception("Bad label " + label)

    def isTimeout(self) -> bool:
        if self.timer > 0:
            self.timer -= 1
        return self.timer == 0


class MUDPDecodeMsgs():
    def __init__(self):
        self.decodeMsgs = {}
    
    # Find existing MUDPBuildMsg, or return None
    def find(self, reqId: int) -> MUDPDecodeMsg:
        return self.decodeMsgs.get(reqId)

    # Find existing MUDPBuildMsg, or creates a new one.
    def get(self, remoteAddr: (str, int), reqId: int) -> MUDPDecodeMsg:
        key = remoteAddr + (reqId,)
        decodeMsg = self.decodeMsgs.get(key)
        if decodeMsg is None:
            decodeMsg = MUDPDecodeMsg(reqId)
            self.decodeMsgs[key] = decodeMsg
        return decodeMsg

    # Yields all MUDPBuildMsg that expired.
    def getAllTimeout(self) -> (any, MUDPDecodeMsg):
        toDelete = []
        for k, v in self.decodeMsgs.items():
            if v.isTimeout():
                toDelete.append(k)
                yield k, v
        for k in toDelete:
            del self.decodeMsgs[k]

# Reader has two modes: Client mode, or collection mode, were responses from
# different nodes are stored against the request id. Server mode were
# responses are store against the node address and request id.
class MUDPReader(threading.Thread):
    def __init__(self, socket: any, maxPayload: int, client: bool):
        threading.Thread.__init__(self)
        self.s = socket
        self.stop = False
        self.newContent = {}
        self.content = None
        self.maxPayload = maxPayload
        self.clientMode = client
        self.decodeMsgs = MUDPDecodeMsgs()

    def _decodeRequestId(self, txt: str) -> int:
        try:
            return int(txt[0:4],16)
        except Exception:
            traceback.print_exc()
            return -1

    def run(self):
        while not self.stop:
            ip_port = None
            txt = None
            try:
                ready = select.select([self.s], [], [], 1)
                if self.content is None and len(self.newContent):
                    self.content = self.newContent
                    self.newContent = {}
                if not ready[0]:
                    for key, decodeMsg in self.decodeMsgs.getAllTimeout():
                        self.newContent.setdefault(key,[]).append(decodeMsg.content)
                    continue
                ret = self.s.recvfrom( self.maxPayload )
                if ret is None:  # Socket closed.
                    self.stop = True
                    break
                (data, ip_port) = ret
                # print("Recv "+str(data)+" from "+str(ip_port))
                txt = data.decode('utf-8')
                reqId = self._decodeRequestId(txt)
                if reqId == -1:
                    continue
                if self.clientMode:  # Collect content by requestid.
                    decodeMsg = self.decodeMsgs.find(reqId)
                    if decodeMsg is None:
                        print("Unexpected request id, ignoring id="+str(reqId))
                        continue
                    key = reqId
                else:  # Server mode, collect content by endpoint and requestid
                    decodeMsg = self.decodeMsgs.get(ip_port, reqId)
                    key = ip_port + (reqId,)
                for content in decodeMsg.decode(txt):
                    # print("Posting content "+str(key)+" "+content)
                    self.newContent.setdefault(key,[]).append(content)
                if self.content is None and len(self.newContent):
                    self.content = self.newContent
                    self.newContent = {}
            except Exception as e:
                traceback.print_exc()
                print("Failed to parse cmds " + str(e) + " from " + str(ip_port))
                print(txt)
            except Exception:
                traceback.print_exc()
                self.stop = True


class MUDPBuildMsg():
    # <Label><content id><label><chunk id><chunk len><content>
    ContentHdrLen = len("B11b223333".encode('utf-8'))
    sensibleSpaceForContent = ContentHdrLen + (ContentHdrLen * 2)
    ChunkHdrLen = len("b223333".encode('utf-8'))

    requestId: int = int(random.random() * 0xffff)
    @staticmethod
    def nextId() -> int:
        MUDPBuildMsg.requestId = (MUDPBuildMsg.requestId + 1) & 0xffff
        return MUDPBuildMsg.requestId

    def __init__(self, remoteAddr: (str, int), maxPayload: int):
        self.remoteAddr = remoteAddr
        self.maxPayload = maxPayload
        self.firstContent = True
        self.requestId = MUDPBuildMsg.nextId()
        self.buffer = "".encode('utf-8')
        self.i = 0
        self.contentId = 0
        self.chunkId = 0
        self.reset()
        self.eom = False

    def reset(self) -> None:
        self.buffer = ("%04x" % self.requestId).encode('utf-8')
        self.i = 4
        
    def _appendBytes(self, b: bytes) -> None:
        self.buffer += b
        self.i += len(b)
        # print("_append " + self.buffer + " " + str(self.i) +" " +s)
        if self.i > self.maxPayload:
            raise Exception("Beyond the pale")

    def _appendStr(self, s: str) -> None:
        self._appendBytes(s.encode('utf-8'))

    def room(self) -> int:
        return self.maxPayload - self.i

    def hasRoom(self, size: int) -> int:
        return self.room() >= size

    def hasSpaceForMoreContent(self) -> bool:
        return self.room() >= MUDPBuildMsg.sensibleSpaceForContent

    def hasContent(self) -> bool:
        return self.i > 4

    def getBytes(self) -> bytes:
        txt = self.buffer
        self.reset()
        return txt
    
    def getRemoteAddr(self) -> (str, int):
        return self.remoteAddr

    # Add content to msg. Return txt to send when msg is full or eom.
    def addContent(self, content: str, eom: bool) -> bytes:
        if self.firstContent:  # First content, use O and B.
            if eom:
                self.firstContent = True
                self.contentId = 0
                self._appendStr("O%02x"%self.contentId)
            else:
                self.firstContent = False
                self.contentId = 0
                self._appendStr("B%02x"%self.contentId)
        else:  # Next content, use F or C.
            if eom:
                self.firstContent = True
                self.contentId = ( self.contentId + 1 ) & 0xff
                self._appendStr("F%02x"%self.contentId)
            else:
                self.firstContent = False
                self.contentId = ( self.contentId + 1 ) & 0xff
                self._appendStr("C%02x"%self.contentId)
        self.chunkId = 0
        b = content.encode('utf-8')
        contentLen = len(b)
        if self.hasRoom(contentLen + 7):
            self._appendStr("o%02x%04x"%(self.chunkId, contentLen))
            self._appendBytes(b)
            if eom:
                self.requestId = MUDPBuildMsg.nextId()
            if eom or not self.hasSpaceForMoreContent():
                yield self.getBytes()
                self.reset()
            return
        firstChunkId = True
        contentIdx = 0
        remainingContentLen = contentLen - contentIdx
        while remainingContentLen:
            r = self.room() - self.ChunkHdrLen
            if firstChunkId:
                firstChunkId = False
                self._appendStr("b")
            else:
                if remainingContentLen > r:
                    self._appendStr("c")
                else:
                    self._appendStr("f")
            if remainingContentLen > r:
                nxtContentIdx = contentIdx + r
            else:
                nxtContentIdx = contentIdx + remainingContentLen
            chunk = content[contentIdx:nxtContentIdx].encode('utf-8')
            contentIdx = nxtContentIdx
            chunkLen = len(chunk)
            self._appendStr("%02x%04x" % (self.chunkId, chunkLen))
            self.chunkId = ( self.chunkId + 1) & 0xff
            self._appendBytes(chunk)
            yield self.getBytes()
            remainingContentLen = contentLen - contentIdx
            if eom and remainingContentLen == 0:
                self.requestId = MUDPBuildMsg.nextId()
            self.reset()


class MUDP:
    @staticmethod
    def nextId(i: int) -> int:
        return (i + 1) & 0xff

    @staticmethod
    def prevId(i: int) -> int:
        return (i - 1) & 0xff

    @staticmethod
    def getIPAddressForTheInternet() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ret = s.getsockname()[0]
        s.close()
        return ret

    def __init__(self, socket: any, clientMode: bool, maxPayload: int=65527):
        self.maxPayload = maxPayload
        if maxPayload > 65527:
            raise Exception("maxPayload above UDP maximum "+str(maxPayload))
        if maxPayload < MUDPBuildMsg.sensibleSpaceForContent:
            raise Exception(
                "maxPayload too small at "+str(maxPayload)
                +" smallest="+str(MUDPBuildMsg.sensibleSpaceForContent))

        self.s = socket
        self.reader = MUDPReader(socket,maxPayload,clientMode)
        self.reader.start()

        self.stop = False

    def shutdown(self):
        self.stop = True
        self.reader.stop = True
        self.reader.join()

    def send(self, content: str, eom: bool, msg: MUDPBuildMsg):
        for b in msg.addContent(content,eom):
            # print("sent (content) "+str(len(b))+":"+str(b)+" to "+str(msg.getRemoteAddr()))
            self.s.sendto(b, msg.getRemoteAddr())
        if msg.eom and msg.hasContent():
            b = msg.getBytes()
            # print("sent (eom) "+str(len(b))+":"+b+" to "+str(msg.getRemoteAddr()))
            self.s.sendto(b, msg.getRemoteAddr())

    def recv(self) -> (any, str):
        countDown = 30
        while countDown > 0:
            if self.reader.content is None:
                # Wait for something to arrive via the reader thread.
                countDown -= 1
                sleep(0.03)
                continue
            countDown = 10
            for key, lst in self.reader.content.items():
                for txt in lst:
                    if self.skip > 0:
                        self.skip -= 1
                        if self.skip == 0:
                            print("causing problems; skipping " + txt)
                            continue
                    # print("recv " +txt+" on key "+str(key))
                    yield key, txt
            self.reader.content = None

    @staticmethod
    def main():
        ip = "127.0.0.1"

        clientS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clientS.settimeout(.5)
        clientS.bind((ip, 0))
        clientAddr = (ip, clientS.getsockname()[1])

        serverS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverS.settimeout(.5)
        serverS.bind((ip, 0))
        serverAddr = (ip,serverS.getsockname()[1])

        maxPayload=30
        client = MUDP(clientS, clientMode=True, maxPayload=maxPayload)
        print(str(clientS.getsockname())+" > "+str(serverAddr))
        server = MUDP(serverS, clientMode=False, maxPayload=maxPayload)
        print(str(serverS.getsockname())+" > "+str(clientAddr))
        server.skip = 0

        l = [("abcdefghijklmnopqrstuvwxyz", True), ("__samples", False), ("12345678901234567", False), ("123456789012345678", False), ("1234567890123456", True)]
        msg = MUDPBuildMsg(serverAddr,maxPayload)
        for txt, eom in l:
            print("sending " + txt + " " + str(eom))
            client.send(txt, eom, msg)
        for key, txt in server.recv():
            print("receiving \""+txt+"\" from"+str(key))
        for key, txt in server.recv():
            print("receiving \""+txt+"\" from"+str(key))
        client.shutdown()
        server.shutdown()
        
if __name__ == "__main__":
    MUDP.main()
