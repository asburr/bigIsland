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

# Assuming an ordered text file, from smallest to largest, find value
# in file using the binary searching algorithm.
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
        if depth > 10:
            raise Exception("recursion")
        if bi == mi == ei:
            return None
        # print(str(bi)+" "+str(mi)+" "+str(ei))
        self.measure += 1
        self.f.seek(mi)
        line = self.f.readline()
        if line:
            line = self.f.readline()
        if not line or self.f.tell() > ei:
            self.measure += 1
            self.f.seek(bi)
            line = self.f.readline()
            while line:
                linek = line[0:kl]
                # print(line)
                if k < linek:
                    return None
                elif k > linek:
                    self.measure += 1
                    line = self.f.readline()
                else:
                    return line.strip()
            return None
        linek = line[0:kl]
        # print("looking at "+line)
        if k > linek:
            return self.findX(k, kl, mi, mi+int((ei-mi)/2), ei, depth+1)
        if k < linek:
            return self.findX(k, kl, bi, bi+int((mi-bi)/2), mi, depth+1)
        return line.strip()

    def find(self, k: str) -> str:
        self.measure = 0
        self.maxdepth = 0
        return self.findX(k, len(k), 0, int(self.size/2), self.size,0)

    def main():
        g = mGrep("mgrep.txt")
        for k in ["12345","12350","12355","12370"]:
            print(k+"="+str(g.find(k))+" "+str(g.measure)+" "+str(g.maxdepth))
            
if __name__ == "__main__":
    mGrep.main()