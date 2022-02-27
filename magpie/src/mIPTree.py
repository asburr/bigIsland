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

class mIPTree:
    def __init__(self):
        self.tree = {}

    def add(self, ip:int, data: any) -> any:
        msi = ip & 0xffffff00
        lsi = ip & 0x000000ff
        return self.tree.setdefault(msi,{}).setdefault(lsi,data)

    def find(self, ip:int) -> any:
        msi = ip & 0xffffff00
        lsi = ip & 0x000000ff
        return self.tree.get(msi,{}).get(lsi,None)

    @staticmethod
    def main():
        miptree = mIPTree()
        tests = [(1674307,1),(1674407,2)]
        for t in tests:
            miptree.add(t[0],t[1])
        for t in tests:
            f = miptree.find(t[0])
            if t[1] != f:
                raise Exception("Error "+str(t[1])+" != "+str(f))
        
        
if __name__ == "__main__":
    mIPTree.main()