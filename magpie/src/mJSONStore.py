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
import json
import argparse
from magpie.src.mgrep import mGrep

class mJsonStore:
    """ Maintain an ordered list of a small number keyed objects on disk in json format. """

    def __init__(self, file: str):
        """ File that is the JSON store. """
        self.file = os.path.abspath(file)
        self.tmpfile = os.path.join(os.path.dirname(self.file),"."+os.path.basename())
        self.mgrep = mGrep(self.file,1000)

    def add(self, j:dict, key:str):
        """ Maintain objects in key order in file. Rewrites file for each add. """
        found = False
        with open(self.tmpfile,"w") as w:
            with open(self.file,"r") as f:
                for line in f:
                    if not found:
                        fkey = json.loads(line)[0]
                        if fkey == key:
                            raise Exception("Duplicate key "+fkey)
                        if fkey > key:
                            w.write(json.dumps((key,j)))
                    w.write(line)
        with open(self.file,"a+") as f:
            f.write(json.dumps((j[self.key],j))+"\n")
        os.rename(self.tmpfile,self.file)

    def find(self, key:str) -> dict:
        """ Finds object matching j[key] in object store. """
        s = self.mgrep.find('["'+key+'",')
        if s:
            return json.loads(s)[1]
        return None

    def delete(self, key:str) -> bool:
        """ Rewrite file without object."""
        found = False
        with open(self.tmpfile,"w") as w:
            with open(self.file,"r") as f:
                for line in f:
                    if found:
                        w.write(line)
                    else:
                        fkey = json.loads(line)[0]
                        found = fkey == key
                        if not found:
                            w.write(line)
        os.rename(self.tmpfile,self.file)
        
    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Testing mJsonStore")
        parser.add_argument('file', help="File that is the JSON store")
        args = parser.parse_args()
        js = mJsonStore(args.file,")
        js.add({"1":1},"1")
        js.add({"2":1},"2")
        js.add({"3":1},"3")


if __name__ == "__main__":
    mJsonStore.main()