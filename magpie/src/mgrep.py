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
import os

# Testing uses the following file, test_mgrep.csv:
"""
1679327300,1
1679327312,2
1679327325,3
1679327326,4
1679327327,5
1679327359,55
1679327360,6
"""

# Assuming an ordered text file, ordering from smallest to largest, find
# the value at the start of a line in the file using the binary
# searching algorithm.
# Usage: To be used with an ordered index file containing single key values.
# I.e. 1234,5 would be the key 1234, and find("1234") returns this row.
# Hint: Include the key-separator in the search-key, as a short key returns
# the first matching result which is from near the middle of the section of
# matching indexed-keys. i.e. find("1679337") returns 1679327327 from the
# above test file, and find("1679337,") returns None.
class mGrep():
    def __init__(self, fn: str):
        self.f = open(fn,"r")
        self.f.seek(0, os.SEEK_END)
        self.size = self.f.tell()
        self.measure = 0
        self.maxdepth = 0

    def findX(self, k: str, kl: int, bi: int, mi: int, ei: int, depth: int) -> str:
        if depth > self.maxdepth:
            self.maxdepth = depth
        if depth > 100:
            raise Exception("recursion")
        if bi == mi == ei:
            return None
        # print(str(bi)+" "+str(mi)+" "+str(ei))
        self.measure += 1
        self.f.seek(mi)
        line = self.f.readline()
        if line: # Probably a partial line, the next read will be a full line.
            line = self.f.readline()
        if not line or self.f.tell() > ei: # Read EOF, or beyond scope.
            self.measure += 1
            self.f.seek(bi)
            line = self.f.readline()
            if bi > 0 and line:
                line = self.f.readline()
            while line:  # Smallest to largest is the file ordering.
                linek = line[0:kl]
                # print("linear search "+line.strip())
                if linek > k: # Larger row in file, stop searching.
                    return None
                elif k > linek: # Smaller row in file, keep searching.
                    self.measure += 1
                    line = self.f.readline()
                else:
                    return line.strip()
            return None
        linek = line[0:kl]
        # print("binary search "+line.strip())
        if k > linek: # Key is greate than current row(@mi), search about mi.
            return self.findX(k, kl, mi, mi+int((ei-mi)/2), ei, depth+1)
        if k < linek: # Key is less than current row, search below mi.
            return self.findX(k, kl, bi, bi+int((mi-bi)/2), mi, depth+1)
        return line.strip() # Found an exact match

    def find(self, k: str) -> str:
        self.measure = 0
        self.maxdepth = 0
        return self.findX(k, len(k), 0, int(self.size/2), self.size,0)

    def main():
        g = mGrep("test_mgrep.csv")
        for k,v in {
                "1679327":"1679327327,5",
                "1679327,":None,
                "1679327300,":"1679327300,1",
                "1679327360,":"1679327360,6",
                "1679327312,":"1679327312,2",
                "1679327324,":None,
                "1679327361,":None
                  }.items():
            i = g.find(k)
            if v != i:
                print("FAIL "+k+" "+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))
            else:
                print("PASS "+k+"="+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))


# Assuming an ordered text file, ordering from smallest to largest, find
# the nearest smallest value at the start of a line in the file using the binary
# searching algorithm.
# Usage: To be used with a index file containing a range of key values. The
# smallest key being first on the line. I.e. 1234:1236 would be the range
# from 1234 to 1236, and find("1235") returns this row.
# Hint: Include the key-separator in the search-key, as a short key returns
# the first matching result which is from near the middle of the section of
# matching indexed-keys. i.e. find("1679337") returns 1679327327 from the
# above test file, and find("1679337,") returns None.
class mGrepNearest():
    def __init__(self, fn: str):
        self.f = open(fn,"r")
        self.f.seek(0, os.SEEK_END)
        self.size = self.f.tell()
        self.measure = 0
        self.maxdepth = 0

    def findX(self, k: str, kl: int, bi: int, mi: int, ei: int, depth: int) -> str:
        if depth > self.maxdepth:
            self.maxdepth = depth
        if depth > 10:
            raise Exception("recursion")
        if bi == mi == ei:
            return None
        # print(str(bi)+" "+str(mi)+" "+str(ei))
        self.measure += 1
        self.f.seek(mi)
        line = self.f.readline()
        if line: # Probably a partial line, the enxt read will be a full line.
            line = self.f.readline()
        if not line or self.f.tell() > ei: # Read EOF, or beyond scope.
            # linear search, from bi until row is greater than key.
            self.measure += 1
            self.f.seek(bi)
            line = self.f.readline()
            if bi > 0 and line:
                line = self.f.readline()
            nearest = None
            while line:  # Smallest to largest is the file ordering.
                linek = line[0:kl]
                # print("linear search "+line.strip())
                if linek > k: # Larger row in file, stop searching.
                    if nearest:
                        return nearest.strip()
                    return nearest
                elif k > linek: # Smaller row in file, keep searching.
                    self.measure += 1
                    nearest = line
                    line = self.f.readline()
                else:
                    return line.strip()
            return None
        linek = line[0:kl]
        # print("binary search "+line.strip())
        if k > linek: # Key is greate than current row(@mi), search about mi.
            retval = self.findX(k, kl, mi, mi+int((ei-mi)/2), ei, depth+1)
            if retval is None:
                return line.strip()
            else:
                return retval
        if k < linek: # Key is less than current row, search below mi.
            return self.findX(k, kl, bi, bi+int((mi-bi)/2), mi, depth+1)
        return line.strip() # Found an exact match

    def find(self, k: str) -> str:
        self.measure = 0
        self.maxdepth = 0
        return self.findX(k, len(k), 0, int(self.size/2), self.size,0)

    def main():
        g = mGrepNearest("test_mgrep.csv")
        for k,v in {
                "1679327":"1679327327,5",
                "1679327,":None,
                "1679327300,":"1679327300,1",
                "1679327360,":"1679327360,6",
                "1679327312,":"1679327312,2",
                "1679327324,":"1679327312,2",
                "1679327361,":"1679327360,6"
                  }.items():
            i = g.find(k)
            if v != i:
                print("FAIL "+k+" "+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))
            else:
                print("PASS "+k+"="+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))


if __name__ == "__main__":
    print("mGrep")
    mGrep.main()
    print("mGrepNearest")
    mGrepNearest.main()
