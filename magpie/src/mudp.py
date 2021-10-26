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
# The Client API: see main()
import socket
import select
import traceback
import threading
from time import sleep
import random
import time


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
        self.skippingContent = False
        self.skipBad = True
        self.eom = False

    def __str__(self):
        s="Decode msg "
        s+=" reqId="+str(self.requestId)
        s+=" cntId="+str(self.contentId)
        s+=" cnkId="+str(self.chunkId)
        if self.skippingContent:
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
            print("Check MTU "+self.txt)
            raise Exception("Truncated message. Check MTU settings on servers!")
        ret = self.txt[self.i:nxtI]
        self.i = nxtI
        return ret

    def _decodeRemaining(self) -> int:
        return self.l - self.i

    def decode(self, txt: str) -> (str, bool):
        self.timer = 10
        self.txt = txt
        self.i = 4
        self.l = len(txt)
        if self.skipBad:
            if self.skippingContent:
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
                self.skippingContent = False
                print("Was skipping content, restarting content at: " + str(self.contentId) + "," + str(self.chunkId))
        while self._decodeRemaining() > 0:
            label = self._decodeStr(1)
            if label in ["O", "B", "C", "F"]:
                self.chunkId = 0
                self.content = ""
                contentId = self._decodeHex(2)
                if self.contentId != contentId:
                    if self.skipBad:
                        print("Starting skipping Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                        self.skippingContent = True
                        return
                    # print(self.txt + " " + str(self.i))
                    raise Exception("Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                if label in ["O", "F"]:
                    self.eom = True
            elif label in ["o", "b", "c", "f"]:
                if label in ["c", "f"]:
                    if len(self.content) == 0:
                        # Missing prior chunk.
                        self.skippingContent = True
                        return
                if label == "f":
                    contentId = self._decodeHex(2)
                    if self.contentId != contentId:
                        if self.skipBad:
                            print("Dropping content, Bad contentId in last chunk got " + str(contentId)+" expect "+str(self.contentId))
                            self.skippingContent = True
                            return
                        # print(self.txt + " " + str(self.i))
                        raise Exception("Bad contentId in last chunk, got " + str(contentId)+" expect "+str(self.contentId))
                    self.contentId = ( self.contentId + 1 ) & 0xff
                elif label == "o":
                    self.contentId = ( self.contentId + 1 ) & 0xff
                chunkId = self._decodeHex(2)
                if self.chunkId != chunkId:
                    if self.skipBad:
                        print("Starting skipping Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                        self.skippingContent = True
                        return
                    raise Exception("Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                self.chunkId = ( self.chunkId + 1 ) & 0xff
                chunkLen = self._decodeHex(4)
                self.content += self._decodeStr(chunkLen)
                if label in ["o", "f"]:
                    yield self.content, self.eom
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

    def addRequestId(self, requestId: int) -> None:
        self.decodeMsgs[requestId] = MUDPDecodeMsg(requestId)

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
    def __init__(self, socket: any, maxPayload: int, client: bool, skip: int):
        threading.Thread.__init__(self)
        self.s = socket
        self.stop = False
        self.newContent = {}
        self.newContentEOM = {}
        self.clientMode = client
        if self.clientMode:
            self.content = {}
            self.contentEOM = {}
        else:
            self.content = None
            self.contentEOM = None
        self.maxPayload = maxPayload
        self.decodeMsgs = MUDPDecodeMsgs()
        self.skip = skip
        self.packetCount = 0

    def _decodeRequestId(self, txt: str) -> int:
        try:
            return int(txt[0:4],16)
        except Exception:
            traceback.print_exc()
            return -1

    def addRequestId(self, requestId: int) -> None:
        if self.clientMode:
            self.decodeMsgs.addRequestId(requestId)
            self.content[requestId] = None

    # Add newly arrived content when consumer has read all of the prior
    # published contemt.
    # It's different from Server and Client. Client block on the request id,
    # and new content for that request id should be queued when other queues
    # are remain full. Server consumes all request ids and new content is
    # published when all prior content is consumed.
    def publish(self):
        if self.clientMode:
            deleteIDs = []
            for requestId in self.newContent.keys():
                if ( self.content[requestId] is None and
                     len(self.newContent[requestId]) ):
                    self.content[requestId] = self.newContent[requestId]
                    self.contentEOM[requestId] = self.newContentEOM[requestId]
                    if self.contentEOM[requestId][-1]:
                        deleteIDs.append(requestId)
                    else:
                        self.newContentEOM[requestId] = None
                        self.newContent[requestId] = None
            for requestId in deleteIDs:
                del self.newContent[requestId]
                del self.newContentEOM[requestId]
        else:
            if self.content is None and len(self.newContent):
                self.content = self.newContent
                self.newContent = {}
                self.contentEOM = self.newContentEOM
                self.newContentEOM = {}

    def timeout(self):
        for key, decodeMsg in self.decodeMsgs.getAllTimeout():
            self.newContentEOM.setdefault(key,[]).append(True)
            self.newContent.setdefault(key,[]).append(None)
        
    def run(self):
        while not self.stop:
            ip_port = None
            txt = None
            try:
                ready = select.select([self.s], [], [], 1)
                if not ready[0]:
                    self.timeout()
                    self.publish()
                    continue
                ret = self.s.recvfrom( self.maxPayload )
                if ret is None:  # Socket closed.
                    self.stop = True
                    break
                (data, ip_port) = ret
                # print("\nRecv "+str(data)+" from "+str(ip_port)+"\n")
                txt = data.decode('utf-8')
                if self.skip > 0:
                    self.skip -= 1
                    if self.skip == 0:
                        print("MUDPReader, causing problems; skipping " + txt)
                        continue
                self.packetCount += 1
                reqId = self._decodeRequestId(txt)
                if reqId == -1:
                    self.publish()
                    continue
                if self.clientMode:  # Collect content by requestid.
                    decodeMsg = self.decodeMsgs.find(reqId)
                    if decodeMsg is None:
                        print(self.decodeMsgs.decodeMsgs.keys())
                        print("Unexpected request id, ignoring id="+str(reqId))
                        self.publish()
                        continue
                    key = reqId
                else:  # Server mode, collect content by endpoint and requestid
                    decodeMsg = self.decodeMsgs.get(ip_port, reqId)
                    key = ip_port + (reqId,)
                for content, eom in decodeMsg.decode(txt):
                    self.newContentEOM.setdefault(key,[]).append(eom)
                    self.newContent.setdefault(key,[]).append(content)
                self.publish()
            except Exception as e:
                traceback.print_exc()
                print("Failed to parse cmds " + str(e) + " from " + str(ip_port))
                print(txt)
            except Exception:
                traceback.print_exc()
                self.stop = True


class MUDPBuildMsg():
    # <Label><content id><label><chunk id><chunk len><content>
    # <label><content id><chunk id><chunk len><content>
    ContentHdrLen = len("B11b223333".encode('utf-8'))
    sensibleSpaceForContent = ContentHdrLen + (ContentHdrLen * 2)
    ChunkHdrLen = len("f11223333".encode('utf-8'))

    requestId: int = int(random.random() * 0xffff)
    @staticmethod
    def nextId() -> int:
        MUDPBuildMsg.requestId = (MUDPBuildMsg.requestId + 1) & 0xffff
        return MUDPBuildMsg.requestId

    def __init__(self, remoteAddr: (str, int), maxPayload: int, requestId: int):
        self.remoteAddr = remoteAddr
        self.maxPayload = maxPayload
        self.firstContent = True
        if requestId is None:
            self.requestId = MUDPBuildMsg.nextId()
        else:
            self.requestId = requestId
        self.buffer = "".encode('utf-8')
        self.i = 0
        self.contentId = 0
        self.chunkId = 0
        self.reset()

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
        b = self.buffer
        self.reset()
        return b
    
    def getRemoteAddr(self) -> (str, int):
        return self.remoteAddr

    # Add content to msg. Return bytes to send when msg is full or eom.
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
                    self._appendStr("f%02x"%self.contentId)
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

    def __init__(self, socket: any, clientMode: bool, skip: int, maxPayload: int=65527):
        self.maxPayload = maxPayload
        if maxPayload > 65527:
            raise Exception("maxPayload above UDP maximum "+str(maxPayload))
        if maxPayload < MUDPBuildMsg.sensibleSpaceForContent:
            raise Exception(
                "maxPayload too small at "+str(maxPayload)
                +" smallest="+str(MUDPBuildMsg.sensibleSpaceForContent))

        self.s = socket
        self.reader = MUDPReader(socket,maxPayload,clientMode,skip)
        self.reader.start()
        self.stop = False
        self.slept = 0
        self.lastRequestId = -1

    def shutdown(self):
        self.stop = True
        self.reader.stop = True
        self.reader.join()

    def send(self, content: str, eom: bool, msg: MUDPBuildMsg) -> int:
        sent = False
        requestId = msg.requestId
        if eom:
            if requestId == self.lastRequestId:
                raise Exception("Multiple msg using the same requestId "+str(requestId))
            self.lastRequestId = requestId
        for b in msg.addContent(content,eom):
            # print("sent (content) "+str(len(b))+":"+str(b)+" to "+str(msg.getRemoteAddr()))
            sent = True
            self.s.sendto(b, msg.getRemoteAddr())
        if eom and msg.hasContent():
            b = msg.getBytes()
            # print("sent (eom) "+str(len(b))+":"+b+" to "+str(msg.getRemoteAddr()))
            sent = True
            self.s.sendto(b, msg.getRemoteAddr())
        if sent:
            self.reader.addRequestId(requestId)
            return requestId
        return -1

    # Get requests and responses.
    def recv(self) -> (any, str, bool):
        if self.reader.clientMode:
            raise Exception("Client should call recvRequestId")
        countDown = 30
        while countDown > 0:
            self.reader.publish()
            if self.reader.content is None:
                # Wait for something to arrive via the reader thread.
                countDown -= 1
                self.slept += 0.001
                sleep(0.001)
                continue
            countDown = 10
            for key, lst in self.reader.content.items():
                eomlst = self.reader.contentEOM[key]
                for i, txt in enumerate(lst):
                    yield key, txt, eomlst[i]
            self.reader.contentEOM = None
            self.reader.content = None

    # Get responses.
    def recvRequestId(self, requestId: int) -> (str, bool):
        if not self.reader.clientMode:
            raise Exception("Server should call recv")
        countDown = 30
        while countDown > 0:
            l = self.reader.content.get(requestId)
            if l is None:
                # Wait for something to arrive via the reader thread.
                countDown -= 1
                self.slept += 0.001
                sleep(0.001)
                continue
            countDown = 10
            eoml = self.reader.contentEOM.get(requestId)
            eom = False
            for i, txt in enumerate(l):
                yield txt, eoml[i]
            if eom:
                del self.reader.contentEOM[requestId]
                del self.reader.content[requestId]
            else:
                self.reader.contentEOM[requestId] = None
                self.reader.content[requestId] = None

    @staticmethod
    def test(skip: int, l: list, maxPayload: int) -> int:
        ip = "127.0.0.1"

        clientS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clientS.settimeout(5)
        clientS.bind((ip, 0))
        clientAddr = (ip, clientS.getsockname()[1])

        serverS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverS.settimeout(5)
        serverS.bind((ip, 0))
        serverAddr = (ip,serverS.getsockname()[1])

        client = MUDP(clientS, clientMode=True, skip=0, maxPayload=maxPayload)
        print(str(clientS.getsockname())+" > "+str(serverAddr))
        server = MUDP(serverS, clientMode=False, skip=skip, maxPayload=maxPayload)
        print(str(serverS.getsockname())+" > "+str(clientAddr))

        requestIds = []
        client_timestamps = []
        roundtrip_timestamps = []
        msg = MUDPBuildMsg(serverAddr,maxPayload,None)
        for txt, eom in l:
            client_timestamps.append(time.time())
            requestId = client.send(txt, eom, msg)
            print("Client sending " + txt + " eom=" + str(eom) + " id="+str(requestId))
            if eom:
                roundtrip_timestamps.append(time.time())
                requestIds.append(requestId)
        serverI = 0
        for (ip, port, requestId), txt, eom in server.recv():
            finish = time.time()
            expectedTxt, expectedEOM = l[serverI]
            serverI += 1
            print("%.5f"%(finish-client_timestamps[-1]), end="")
            failed = False
            while expectedTxt != txt:
                if serverI < len(l):
                    expectedTxt, expectedEOM = l[serverI]
                    serverI += 1
                else:
                    expectedTxt = None
                    break
            if expectedTxt is None:
                print(" FAILED (recv text not matching\nexp=%s\ngot=%s\n"%(expectedTxt,txt), end="")
                failed = True
            elif eom and not expectedEOM:
                print(" FAILED not expecting eom ", end="")
                failed = True
            elif not eom and expectedEOM:
                print(" FAILED expecting eom ", end="")
                failed = True
            else:
                print(" PASS ", end="")
            print(" Server receiving \""+txt+"\" from="+str(ip)+":"+str(port)+" id="+str(requestId)+ " eom="+str(eom))
            if failed:
                print(server.reader.content)
                print(server.reader.contentEOM)
                print(server.reader.newContent)
                print(server.reader.newContentEOM)
                raise Exception("STOPPING due to failure")
            del client_timestamps[-1]
            if eom:
                smsg = MUDPBuildMsg((ip,port),maxPayload,requestId)
                s = "Ack to "+str(requestId)
                print("Server Sending "+s)
                server.send(s, True, smsg)
        for requestId in requestIds:
            print("Client waiting for Ack to "+str(requestId))
            eom = False
            while not eom:
                for txt, eom in client.recvRequestId(requestId):
                    finish = time.time()
                    ts=finish-roundtrip_timestamps[-1]
                    del roundtrip_timestamps[-1]
                    if txt is None:
                        print("%.3f"%ts+" Client expired id="+str(requestId)+" eom="+str(eom))
                    else:
                        print("%.3f"%ts+" Client receiving \""+str(txt)+"\" id="+str(requestId)+" eom="+str(eom))
        print("Slept count client=%.5f"%client.slept+" server=%.5f"%server.slept)
        client.shutdown()
        recvPacketCount = server.reader.packetCount
        server.shutdown()
        return recvPacketCount

    @staticmethod
    def main():
        maxPayload=30
        l = [("abcdefghijklmnopqrstuvwxyz", True), ("__samples", False), ("12345678901234567", False), ("123456789012345678", False), ("1234567890123456", True)]
        print("*******\nTest without incoming packet loss at server\n*******")
        packetCount = MUDP.test(0, l, maxPayload)
        print("Server packet count=%d\n"%packetCount)
        for skip in range(1,packetCount+1):
            print("*******\nTest with incoming packet %d lost at server\n*******"%skip)
            MUDP.test(skip, l, maxPayload)
        
if __name__ == "__main__":
    MUDP.main()
