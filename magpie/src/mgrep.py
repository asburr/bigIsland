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
# Description
#============
# mgrep performes a bubble search through a text file and returns a matching
# line.
# Testing
#========
# Examples use the following text file, in lexical order, named test_mgrep.csv:
"""
1679327300,1679327311,1
1679327312,1679327314,2
1679327325,1679327325,3
1679327326,1679327326,4
1679327327,1679327330,5
1679327359,1679327359,55
1679327360,1679327360,6
1679328,1679330,7
"""
# Examples use the following text file, in integer order, named test_mgrep_int_order.csv:
"""
1679328,1679330,7
1679327312,1679327314,2
1679327325,1679327325,3
1679327326,1679327326,4
1679327327,1679327330,5
1679327359,1679327359,55
1679327360,1679327360,6
"""
# Caution/limitations
#====================
# 1 - The file is ordered, smallest key first.
# 2 - The key starts the line.
# 3 - The key is plain text; without double quotes, backslash, and escaping.
# 4 - The key has an end-of-key character that separates the key from
#     the rest of the line. For example, a coma is used in the example file.
# 5 - Not thread safe, must create a mGrep instance for each thread.
# Use cases
#==========
# 1 - Pseudo-random match
#   A partial-key returns the line from the middle of the matching keys.
#     mgrep = mGrep("test_mgrep.csv")
#     mgrep.find("1679327") => "1679327327,1679327330,5".
# 2 - Exact match
#   A full-key returns the matching line.
#     mgrep = mGrep("test_mgrep.csv")
#     mgrep.find("1679327312,") => "1679327312,1679327314,2"
#     mgrep.find("1679327324,") => None
# 3 - Nearest match
#   A full-key returns the line with the nearest and smallest key.
#     mgrep = mGrepNearest("test_mgrep.csv")
#     mgrep.find("1679327324,") => "1679327312,1679327314,2"
#     mgrep.find("1679327361,") => "1679327360,1679327360,6"
# 4 - Matching key ranges, is supported by the nearest match.
#   The example has ranges. Lines have a start key and end key, with a
#   separator (a coma is used in the example). mgrep finds the matching
#   start of the range. and whether the key is within the end of the range
#   is outside the scope of mgrep i.e. extra logic is required to determine
#   if a key is within the range.
#     mgrep = mGrepNearest("test_mgrep.csv")
#     mgrep.find("1679327324,") => "1679327312,1679327314,2"
#     mgrep.find("1679327361,") => "1679327360,1679327360,6"
# 5 - Integer key matching.
#   Integer key matching is needed when the file is in Integer order.
#   An example of 
import os


class mGrep():
    def __init__(self, fn: str, maxLineLength: int=100):
        # Reading starts at a ramdon location, and will most likely read
        # a partial line, and a second readline is used to read a complete
        # that is nearest the location. The buffer size is increased
        # whenever the size of a line is larger than maxLineLength.
        self.maxLineLength = maxLineLength
        self.fn = fn
        self.f = open(self.fn,"r", self.maxLineLength*2)
        self.f.seek(0, os.SEEK_END)
        self.size = self.f.tell()
        self.numberOfDiskReads = 0
        self.maxdepth = 0
        self.nearest = None

    # Key is greater than line(1), or less than line(-1), or equal to line(0)
    def compareKeyToLine(self, k: (str, int), line:str) -> int:
        linek = line[0:k[1]]
        if k[0] > linek:
            return 1
        if k[0] < linek:
            return -1
        return 0

    def readLine(self, pos: int) -> str:
        self.numberOfDiskReads += 1
        self.f.seek(pos)
        line = self.f.readline()
        if pos > 0 and line: # Probably a partial line, the next read will be a full line.
            line = self.f.readline()
        # print(str(self.numberOfDiskReads)+":"+str(pos)+":line="+line.strip())
        l = len(line)
        if l > self.maxLineLength:
            self.maxLineLength = l
            self.f.close()
            self.f = open(self.fn,"r", self.maxLineLength*2)
        return line

    def findX(self, k: any, bi: int, mi: int, ei: int, depth: int) -> str:
        if depth > self.maxdepth:
            self.maxdepth = depth
        if depth > 100:
            raise Exception("Recursion too deep")
        if bi == mi == ei:
            return None
        line = self.readLine(mi)
        if not line or self.f.tell() > ei:
            line = self.readLine(bi)
            while line:
                i = self.compareKeyToLine(k,line)
                # print(k+" "+line.strip()+" "+str(i))
                if i>0:
                    self.numberOfDiskReads += 1
                    self.nearest = line
                    line = self.f.readline()
                elif i<0:
                    return None
                else:
                    return line.strip()
            return None
        i = self.compareKeyToLine(k,line)
        # print(k+" "+line.strip()+" "+str(i))
        if i>0:
            return self.findX(k, mi, mi+int((ei-mi)/2), ei, depth+1)
        if i<0:
            return self.findX(k, bi, bi+int((mi-bi)/2), mi, depth+1)
        return line.strip()

    def find(self, k: str) -> str:
        self.nearest = None
        self.numberOfDiskReads = 0
        self.maxdepth = 0
        return self.findX((k, len(k)), 0, int(self.size/2), self.size,0)

    @staticmethod
    def main():
        g = mGrep("test_mgrep.csv",10)
        for k,v in {
                "1679328":"1679328,1679330,7",
                "1679327":"1679327327,1679327330,5",
                "1679327,":None,
                "1679327300,":"1679327300,1679327311,1",
                "1679327360,":"1679327360,1679327360,6",
                "1679327312,":"1679327312,1679327314,2",
                "1679327324,":None,
                "1679327361,":None
                  }.items():
            i = g.find(k)
            if v != i:
                raise Exception("FAIL "+k+" expect="+str(v)+" got="+str(i)+" reads="+str(g.numberOfDiskReads)+" depth="+str(g.maxdepth))
            else:
                print("PASS "+k+" got "+str(i)+" reads="+str(g.numberOfDiskReads)+" depth="+str(g.maxdepth))


class mGrepNearest(mGrep):

    def find(self, k: str) -> str:
        found = super().find(k)
        if found is not None:
            return found
        if self.nearest is not None:
            return self.nearest.strip()
        return None

    @staticmethod
    def main():
        g = mGrepNearest("test_mgrep.csv")
        for k,v in {
                "1679328":"1679328,1679330,7",
                "1679327":"1679327327,1679327330,5",
                "1679327,":None,
                "1679327300,":"1679327300,1679327311,1",
                "1679327360,":"1679327360,1679327360,6",
                "1679327312,":"1679327312,1679327314,2",
                "1679327324,":"1679327312,1679327314,2",
                "1679327361,":"1679327360,1679327360,6"
                  }.items():
            i = g.find(k)
            if v != i:
                raise Exception("FAIL "+k+" expecting="+str(v)+", but got="+str(i)+" reads="+str(g.numberOfDiskReads)+" depth="+str(g.maxdepth))
            else:
                print("PASS "+k+" got "+str(i)+" reads="+str(g.numberOfDiskReads)+" depth="+str(g.maxdepth))


class mGrepNearestInt(mGrepNearest):

    def __init__(self, fn: str, separator: str, maxLineLength: int=100):
        super().__init__(fn, maxLineLength)
        self.separator = separator

    def compareKeyToLine(self, k: int, line:str) -> int:
        linek = int(line[0:line.index(self.separator)])
        if k > linek:
            return 1
        if k < linek:
            return -1
        return 0

    def find(self, k: int) -> str:
        self.nearest = None
        self.numberOfDiskReads = 0
        self.maxdepth = 0
        found = self.findX(k, 0, int(self.size/2), self.size,0)
        if found is not None:
            return found
        if self.nearest is not None:
            return self.nearest.strip()
        return None

    @staticmethod
    def main():
        g = mGrepNearestInt("test_mgrep_int_order.csv",",")
        for k,v in {
                1679328:"1679328,1679330,7",
                1679327:None,
                1679327:None,
                1679327300:"1679327300,1679327311,1",
                1679327360:"1679327360,1679327360,6",
                1679327312:"1679327312,1679327314,2",
                1679327324:"1679327312,1679327314,2",
                1679327361:"1679327360,1679327360,6"
                  }.items():
            i = g.find(k)
            if v != i:
                raise Exception("FAIL "+str(k)+" expecting="+str(v)+", but got="+str(i)+" reads="+str(g.numberOfDiskReads)+" depth="+str(g.maxdepth))
            else:
                print("PASS "+str(k)+" got "+str(i)+" reads="+str(g.numberOfDiskReads)+" depth="+str(g.maxdepth))


if __name__ == "__main__":
    print("mGrep")
    mGrep.main()
    print("mGrepNearest")
    mGrepNearest.main()
    print("mGrepNearestInt")
    mGrepNearestInt.main()
