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
# Examples use the following file, test_mgrep.csv:
"""
1679327300,1679327311,1
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
# 2 - The key is at the start of the line.
# 3 - The key is plain text. Double quotes and backslash and other escaping
#     can be used in the rest of the line but not the key.
# 4 - The key has an end-of-key character that separates the key from
#     the rest of the line. For example, a coma is used in the example file.
# Usage
#======
# 1 - Pseudo-random
#   A partial-key returns the line from the middle of the matching keys.
#     mgrep = mGrep("test_mgrep.csv")
#     mgrep.find("1679327") => "1679327327,1679327330,5".
# 2 - Exact
#   A full-key returns the matching line.
#     mgrep = mGrep("test_mgrep.csv")
#     mgrep.find("1679327312,") => "1679327312,1679327314,2"
#     mgrep.find("1679327324,") => None
# 3 - Nearest
#   A full-key returns the line with the nearest and smallest key.
#     mgrep = mGrepNearest("test_mgrep.csv")
#     mgrep.find("1679327324,") => "1679327312,1679327314,2"
#     mgrep.find("1679327361,") => "1679327360,1679327360,6"
# 4 - Range
#   The example has ranges. Lines have a start key and end key, with a
#   separator (a coma is used in the example). mgrep finds the matching
#   start of the range. and whether the key is within the end of the range
#   is outside the scope of mgrep i.e. extra logic is required to determine
#   if a key is within the range.
#     mgrep = mGrepNearest("test_mgrep.csv")
#     mgrep.find("1679327324,") => "1679327312,1679327314,2"
#     mgrep.find("1679327361,") => "1679327360,1679327360,6"
import os


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
                print("FAIL "+k+" "+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))
            else:
                print("PASS "+k+"="+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))


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
                print("FAIL "+k+" "+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))
            else:
                print("PASS "+k+"="+str(v)+" != "+str(i)+" "+str(g.measure)+" "+str(g.maxdepth))


if __name__ == "__main__":
    print("mGrep")
    mGrep.main()
    print("mGrepNearest")
    mGrepNearest.main()
