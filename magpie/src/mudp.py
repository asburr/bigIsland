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
# A UDP wrapper
# =============
# Designed for database request and response.
# Using Python multi-threads, there is a reader thread that ensures the
# socket recv buffer does not overflow. It queues content in memory.
# A MUDP object is created for each socket, all threads send and receive on
# this socket using the same MUDP instance.
# UDP loss is detected.
# =====================
# MUDP can be configured (skipBad=True) to recovered from
# loss by skipping the content that was lost, and reporting the content that
# can be salvaged from the lossy communication. Alternatively, MUDP is
# configured (skipBad=False) which drops the request when lossy communication
# is detected, in this case, the application is expected to detect the loss
# by checking what recv() yields, loss is reported as a None content with the
# EOM of True.
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
# The Client API
# ==============
# see examples in main()
import socket
import select
import traceback
import threading
from time import sleep
import random
import time
import copy


# MUDPKey : msgs can be sent in chunks, partial msg are keyed by ip, port, and rid.
class MUDPKey():

    requestId: int = int(random.random()) & 0xffff
    def __init__(self, addr: (str, int), requestId: int=-1):
        if requestId == -1:
            requestId = MUDPKey.requestId = (MUDPKey.requestId + 1) & 0xffff
        self._key = addr + (requestId,)

    def nextRequestId(self) -> 'MUDPKey':
        return MUDPKey(self.getAddr())

    def getIP(self) -> str:
        return self._key[0]

    def getPort(self) -> int:
        return self._key[1]

    def getAddr(self) -> (str,int):
        return (self.getIP(), self.getPort())
    
    def getRequestId(self) -> int:
        return self._key[2]


    # for: if key == key2:
    def __eq__(self, other: 'MUDPKey') -> bool:
        if other is None:
            return False
        return self._key == other._key
    
    # for: printf(key)
    def __str__(self) -> str:
        return str(self._key)
    
    # for: hash(key)
    def __hash__(self) -> int:
        return hash(self._key)
    
    # for: copy()
    def __copy__(self) -> 'MUDPKey':
        return MUDPKey(self.getAddr(), self.getRequestId())


# MUDPDecodeMsg assembles chunks into content, holds partial
# content while it waits for the remaining chunk(s), and yields the content.
# Content id and Chunk id are used to detect missing chunks and chunks
# that are received out of order.
# A timestamp is used to measure the period in between content, and the
# message is expired when this period is too large.
class MUDPDecodeMsg():
    expiredSeconds : int = 10
    def __init__(self, requestId: int, skipBad: bool):
        self.requestId = requestId
        if self.requestId is None:
            raise Exception("No request id.")
        self.contentId = 0
        self.chunkId= 0
        self.content = ""
        self.expiration = time.time() + self.expiredSeconds
        self.i = 0
        self.l = 0
        self.txt = None
        self.skippingContent = False
        self.skipBad = skipBad
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
            # print("Was skipping content, restarting content at: " + str(self.contentId) + "," + str(self.chunkId))
        while self._decodeRemaining() > 0:
            label = self._decodeStr(1)
            if label in ["O", "B", "C", "F"]:
                self.chunkId = 0
                self.content = ""
                contentId = self._decodeHex(2)
                if self.contentId != contentId:
                    if self.skipBad:
                        # print("Starting skipping Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                        self.skippingContent = True
                        return
                    else:
                        # print(self.txt + " " + str(self.i))
                        # raise Exception("Bad contentId got " + str(contentId)+" expect "+str(self.contentId))
                        yield None, True
                        return
                if label in ["O", "F"]:
                    self.eom = True
            elif label in ["o", "b", "c", "f"]:
                if label in ["c", "f"]:
                    if len(self.content) == 0:
                        # Missing prior chunk.
                        if self.skipBad:
                            self.skippingContent = True
                            return
                        else:
                            yield None, True
                            return
                if label == "f":
                    contentId = self._decodeHex(2)
                    if self.contentId != contentId:
                        if self.skipBad:
                            print("Dropping content, Bad contentId in last chunk got " + str(contentId)+" expect "+str(self.contentId))
                            self.skippingContent = True
                            return
                        else:
                            # print(self.txt + " " + str(self.i))
                            # raise Exception("Bad contentId in last chunk, got " + str(contentId)+" expect "+str(self.contentId))
                            yield None, True
                            return
                    self.contentId = ( self.contentId + 1 ) & 0xff
                elif label == "o":
                    self.contentId = ( self.contentId + 1 ) & 0xff
                chunkId = self._decodeHex(2)
                if self.chunkId != chunkId:
                    if self.skipBad:
                        print("Starting skipping Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                        self.skippingContent = True
                        return
                    else:
                        # raise Exception("Bad chunkId " + str(chunkId) + " want " + str(self.chunkId))
                        yield None, True
                        return
                self.chunkId = ( self.chunkId + 1 ) & 0xff
                chunkLen = self._decodeHex(4)
                self.content += self._decodeStr(chunkLen)
                if label in ["o", "f"]:
                    self.expiration = time.time() + self.expiredSeconds
                    yield self.content, self.eom
                    self.content = ""
            else:
                if self.skipbad:
                    return
                else:
                    yield None, True
                    return

    def isExpired(self, t : float) -> bool:
        return self.expiration >= t


# A dictionary of Messages being received. get() keys by IP Address and
# Request Id. All messages can expire.
class MUDPDecodeMsgs():
    def __init__(self, skipBad: bool):
        self.decodeMsgs = {}
        self.skipBad = skipBad

    # Find existing MUDPBuildMsg, or creates a new one. Key is IP, port, rid
    def getDecodeMsg(self, key: MUDPKey) -> MUDPDecodeMsg:
        decodeMsg = self.decodeMsgs.get(key)
        if decodeMsg is None:
            decodeMsg = MUDPDecodeMsg(requestId=key.getRequestId(), skipBad=self.skipBad)
            self.decodeMsgs[key] = decodeMsg
        return decodeMsg

    def getAllTimeout(self) -> (MUDPKey, MUDPDecodeMsg):
        toDelete = []
        t = time.time()
        for k, v in self.decodeMsgs.items():
            if v.isExpired(t):
                toDelete.append(k)
                yield k, v
        for k in toDelete:
            del self.decodeMsgs[k]

    def delete(self, key: MUDPKey) -> None:
        if key in self.decodeMsgs:
            del self.decodeMsgs[key]


# Reader-thead receives packets, each packet contains a chunk of a message.
# The chunks are assembled to make Content which is published to the
# consumer threads.
#
# The communication between the Reader-thread and Consumer-thread is using a
# principle used by device-drivers which does not need a mutex. There is a
# single variable, called self.content. When None, it is assigned a list of
# new content by the Reader-thread. When not None, the Consumer-thread
# starts consuming the new content but first self.content is set back to None.
# Using a variable in this way does not require a mutex.
class MUDPReader(threading.Thread):
    def __init__(self, socket: any, maxPayload: int, skip: int, skipBad: bool, cancelUnknownRequests: bool = True):
        threading.Thread.__init__(self)
        self.cancelUnknownRequests = cancelUnknownRequests
        self.s = socket
        if self.s is None:
            raise Exception("None")
        self.stop = False
        self.newContent = {}
        self.newContentEOM = {}
        self.content = None
        self.contentEOM = None
        self.maxPayload = maxPayload
        self.decodeMsgs = MUDPDecodeMsgs(skipBad)
        self.skip = skip
        self.packetCount = 0
        self.cancelRequest = {}

    def getDecodeMsg(self, key: MUDPKey) -> MUDPDecodeMsg:
        return self.decodeMsgs.getDecodeMsg(key)

    def _decodeRequestId(self, txt: str) -> int:
        try:
            return int(txt[0:4],16), txt[4]
        except Exception:
            traceback.print_exc()
            return -1

    # Remove message builder for the key.
    # Should a message be received at a later time, the "X" command is sent
    # to the remote end that's sending the messages, to cancel further
    # messages. But all that needs to be done here, is to remove the builder.
    def delete(self, key: MUDPKey) -> None:
        self.decodeMsgs.delete(key)
        if key in self.newContent:
            del self.newContent[key]
            del self.newContentEOM[key]
        if key in self.content:
            del self.content[key]
            del self.contentEOM[key]

    # Publish new content when (past) content has been consumed (i.e. content
    # is None).
    def publish(self) -> None:
        if self.content is None and len(self.newContent)>0:
            self.content = self.newContent
            self.newContent = {}
            self.contentEOM = self.newContentEOM
            self.newContentEOM = {}

    # Expired message builders are indicated by eom(True) and content(None).
    # Expired cancelled keys are simply removed.
    def timeout(self, t: float):
        for key, decodeMsg in self.decodeMsgs.getAllTimeout():
            self.newContentEOM.setdefault(key,[]).append(True)
            self.newContent.setdefault(key,[]).append(None)
        if len(self.cancelRequest) > 0:
            l = []
            for key, rt in self.cancelRequest.items():
                if rt > t:
                    l.append(key)
            for key in l:
                del self.cancelRequest[key]

    def run(self):
        ticking = time.time() + 1
        while not self.stop:
            ip_port = None
            txt = None
            try:
                ready = select.select([self.s], [], [], 1)
                t = time.time()
                if t > ticking:
                    ticking = t + 1
                    self.timeout(t)
                    self.publish()
                if not ready[0]:
                    continue
                ret = self.s.recvfrom( self.maxPayload )
                if ret is None:  # Socket closed.
                    self.stop = True
                    break
                (data, ip_port) = ret
                txt = data.decode('utf-8')
                if self.skip > 0:
                    self.skip -= 1
                    if self.skip == 0:
                        print("MUDPReader, causing problems; skipping " + txt)
                        continue
                self.packetCount += 1
                reqId, cmd = self._decodeRequestId(txt)
                if reqId == -1:
                    self.publish()
                    continue
                key = MUDPKey(ip_port,reqId)
                # print("\n"+str(time.time())+" Recv "+str(data)+" from "+str(key)+"\n")
                if cmd == 'X':
                    # Keep a cancel for 4 seconds.
                    self.cancelRequest[key] = time.time() + 4
                    continue
                decodeMsg = self.decodeMsgs.getDecodeMsg(key)
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


# Response and Request messages have the same structure (see header comments)
# and MUDPBuildMsg creates both.
class MUDPBuildMsg():
    # <Label><content id><label><chunk id><chunk len><content>
    # <label><content id><chunk id><chunk len><content>
    ContentHdrLen = len("B11b223333".encode('utf-8'))
    sensibleSpaceForContent = ContentHdrLen + (ContentHdrLen * 2)
    ChunkHdrLen = len("f11223333".encode('utf-8'))

    def __init__(self, key: MUDPKey):
        self.key = key
        self.firstContent = True
        self.buffer = "".encode('utf-8')
        self.i = 0
        self.maxPayload = -1
        self.contentId = 0
        self.chunkId = 0
        self.reset()

    def setMaxPayload(self, maxPayload: int) -> None:
        self.maxPayload = maxPayload

    def reset(self) -> None:
        self.buffer = ("%04x" % self.key.getRequestId()).encode('utf-8')
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
    
    def getKey(self) -> MUDPKey:
        return self.key
    
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
                self.key = self.key.nextRequestId()
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
                self.key = self.key.nextRequestId()
            self.reset()


# See file header comments.
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

    def __init__(self,
                 socket: any,
                 skipBad: bool, # Ignore bad chunk (True), or fail all chunks when one is bad (False).
                 skip: int = 0,
                 maxPayload: int=65527):
        self.maxPayload = maxPayload
        if maxPayload > 65527:
            raise Exception("maxPayload above UDP maximum "+str(maxPayload))
        if maxPayload < MUDPBuildMsg.sensibleSpaceForContent:
            raise Exception(
                "maxPayload too small at "+str(maxPayload)
                +" smallest="+str(MUDPBuildMsg.sensibleSpaceForContent))

        self.s = socket
        self.reader = MUDPReader(socket,maxPayload,skip,skipBad)
        self.reader.start()
        self.stop = False
        self.slept = 0
        self.lastKey = None

    def shutdown(self):
        self.stop = True
        self.reader.stop = True
        self.reader.join()

    def _send(self, content: str, eom: bool, msg: MUDPBuildMsg) -> MUDPKey:
        sent = False
        key = msg.getKey()
        msg.setMaxPayload(self.maxPayload)
        if eom:
            if key == self.lastKey:  # Sanity check!
                raise Exception("Multiple send using the same requestId "+str(key))
            self.lastKey = copy.copy(key)
        for b in msg.addContent(content,eom):
            # print("sent (content) "+str(len(b))+":"+str(b)+" to "+str(msg.getRemoteAddr()))
            sent = True
            self.s.sendto(b, msg.getKey().getAddr())
        if eom and msg.hasContent():
            b = msg.getBytes()
            # print("sent (eom) "+str(len(b))+":"+b+" to "+str(msg.getRemoteAddr()))
            sent = True
            self.s.sendto(b, msg.getKey().getAddr())
        if sent:
            return key
        else:
            return None

    def sendRequest(self, content: str, eom: bool, msg: MUDPBuildMsg) -> MUDPKey:
        key = msg.getKey()
        # Ask reader thread to create a response receiver.
        self.reader.getDecodeMsg(key)   
        k = self._send(content, eom, msg)
        if k is None: # Failed to send request!
            # Delete the receiver.
            self.reader.delete(key)
        else:
            if k != key:
                raise Exception("Insane "+str(k)+" "+str(key))
        return k

    def sendResponse(self, content: str, eom: bool, msg: MUDPBuildMsg) -> None:
        self._send(content, eom, msg)

    # Cancel the rest of the content for this response.
    def cancelRequest(self, key: MUDPKey) -> None:
        self.reader.delete(key)

    # Return ((ip:str, port:int, requestId:int), .content:str, eom:bool)
    # When an error occcurs, and skipBad is False, content=None
    # and eom=True, and the request is cancelled.
    def recv(self) -> (MUDPKey, str, bool):
        countDown = 30
        while countDown > 0:
            self.reader.publish()
            content = self.reader.content
            if content is None:
                # Wait for something to arrive via the reader thread.
                countDown -= 1
                self.slept += 0.001
                sleep(0.001)
                continue
            contentEOM = self.reader.contentEOM
            # Let the reader thread publish more content while we process
            # what has already been published.
            self.reader.contentEOM = None
            self.reader.content = None
            countDown = 10
            for key, lst in content.items():
                eomlst = contentEOM[key]
                for i, txt in enumerate(lst):
                    eom= eomlst[i]
                    if eom and txt is None:
                        # Unrecoverable error, shutdown the request.
                        self.cancelRequestId(key)
                        yield key, None, True
                        return
                    yield key, txt, eomlst[i]

    # Before responding to a request, check that the user
    # has not cancelled the request, in which case do not bother.
    def cancelledRequest(self, key: MUDPKey) -> bool:
        return (key in self.reader.cancelRequest)

    # Wait for the response to a specific request.
    def recvResponse(self, key: MUDPKey, wait:float=0.0) -> (str, bool):
        countDown = 30
        while countDown > 0:
            if self.reader.content is not None:
                l = self.reader.content.get(key)
            else:
                l = None
            if l is None:
                if wait > 0.0:
                    countDown -= 1
                    self.slept += wait
                    sleep(wait)
                    continue
                else:
                    return
            countDown = 10
            eoml = self.reader.contentEOM.get(key)
            eom = False
            for i, txt in enumerate(l):
                yield txt, eoml[i]
            if eom:
                del self.reader.contentEOM[key]
                del self.reader.content[key]
            else:
                self.reader.contentEOM[key] = None
                self.reader.content[key] = None

    # Runs the testcases found in the list. The List is tuples of content and
    # a boolean value. True means last content for the message, False
    # means first or next content for the message.
    # Skip can be set to trigger message loss. A skip number of zero means
    # don't loose any packet, A skip number of one(1) means ignore the first
    # packet, etc.
    @staticmethod
    def test(skip: int, l: list, skipBad: bool, maxPayload: int) -> int:
        ip = "127.0.0.1"

        clientS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        clientS.settimeout(5)
        clientS.bind((ip, 0))
        clientAddr = (ip, clientS.getsockname()[1])

        serverS = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        serverS.settimeout(5)
        serverS.bind((ip, 0))
        serverAddr = (ip,serverS.getsockname()[1])

        client = MUDP(clientS, skip=0, skipBad=skipBad, maxPayload=maxPayload)
        server = MUDP(serverS, skip=skip, skipBad=skipBad, maxPayload=maxPayload)
        print("Client "+str(clientS.getsockname())+" > Server "+str(serverS.getsockname()))

        serverKeys = []
        client_timestamps = []
        roundtrip_timestamps = []
        key = MUDPKey(serverAddr)
        msg = MUDPBuildMsg(key)
        
        # Send all the content from the List.
        # Grab the time of sending each content, for measuring content latency.
        # Grab the time of sending each last content, for measuring round trip latency.
        for txt, eom in l:
            client_timestamps.append(time.time())
            print("Client sending " + txt + " eom=" + str(eom) + " key="+str(msg.getKey()))
            key = client.sendRequest(txt, eom, msg)
            if eom:
                roundtrip_timestamps.append(time.time())
        serverI = 0
        for key, txt, eom in server.recv():
            if serverI >= len(l):
                raise Exception("End of test cases and received from "+str(key)+" content "+str(txt)+" "+str(eom))
            finish = time.time()
            expectedTxt, expectedEOM = l[serverI]
            serverI += 1
            failed = False
            while expectedTxt != txt:
                if serverI < len(l):
                    print("WARNING: skipping forward, did not receive %s" % expectedTxt)
                    expectedTxt, expectedEOM = l[serverI]
                    serverI += 1
                else:
                    expectedTxt = None
                    break
            print("%.5f"%(finish-client_timestamps[-1]), end="")
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
            print(" Server receiving \""+txt+"\" from="+str(key)+" eom="+str(eom))
            if failed:
                print(server.reader.content)
                print(server.reader.contentEOM)
                print(server.reader.newContent)
                print(server.reader.newContentEOM)
                raise Exception("STOPPING due to failure")
            if eom:
                # Respond to client with the same requestId.
                serverKeys.append(key)
                key = MUDPKey(addr=clientAddr, requestId=key.getRequestId())
                smsg = MUDPBuildMsg(key)
                s = "Ack to "+str(key)
                print("Server responding "+s)
                server.sendResponse(s, True, smsg)
        for key in serverKeys:
            print("Client waiting for Ack from "+str(key))
            for txt, eom in client.recvResponse(key=key):
                finish = time.time()
                ts=finish-roundtrip_timestamps[-1]
                del roundtrip_timestamps[-1]
                if txt is None:
                    print("%.3f"%ts+" Client expired id="+str(key)+" eom="+str(eom))
                else:
                    print("%.3f"%ts+" Client receiving \""+str(txt)+"\" id="+str(key)+" eom="+str(eom))
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
        packetCount = MUDP.test(skip=0, l=l, skipBad=True, maxPayload=maxPayload)
        print("Server packet count=%d\n"%packetCount)
        for skip in range(1,packetCount+1):
            print("*******\nTest with incoming packet %d lost at server\n*******"%skip)
            MUDP.test(skip=skip, l=l, skipBad=True, maxPayload=maxPayload)
        
if __name__ == "__main__":
    MUDP.main()
