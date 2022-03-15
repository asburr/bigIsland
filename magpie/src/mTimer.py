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
from time import time, sleep
# Check the version of python, version 3.6.9 retains ordering of insert
# into dicts. Prior versions, do not retain ordering of insert.
# insert order is relied upon when expiring old timer.
import platform
if platform.python_version_tuple() < ('3', '6', '9'):
    raise Exception("Wrong version of python, requires 3.6.9 or more recent")


class mTimer():
    def __init__(self, duration: int):
        self.debug = False
        self.timers={}
        self.dur = duration

    def start(self, k:str, v: any = None) -> None:
        if self.debug:
            print(" timing start "+k+" "+str(self.dur))
        self.timers[k] = (time() + self.dur, v)

    def stop(self, k: str) -> bool:
        if self.debug:
            print(" timing stop "+k, flush=True)
        if self.times.get(k,None) == None:
            return False
        del self.timers[k]
        return True

    def expired(self) -> (str, any):
        t = time()
        expired = []
        for k, v in self.timers.items():
            if v[0] > t: # Dict maintains order of insert.
                break
            if self.debug:
                print(" Expire "+k+" at "+str(t)+" for "+str(v[0])+" at "+str(t))
            expired.append((k,v[1]))
        for k, v in expired:
            yield (k,v)
            del self.timers[k]

    @staticmethod
    def main():
        # Test the module.
        t = mTimer(1)
        t.debug = False
        start = time()
        test = [("1",1.1),("2",1.2),("3",1.3),("4",1.4),("5",1.5),("6",1.6)]
        for v in test:
            sleep(0.1)
            t.start(v[0],v[1])

        for v in test:
            timeout=False
            while not timeout:
                sleep(0.1)
                d = round(time() - start,1)
                for e in t.expired():
                    timeout=True
                    (ek, ev) = e
                    if ev != d:
                        raise Exception("Error wrong expiration dur "+str(ev)+" != "+str(d))
                    if ek != v[0]:
                        raise Exception("Error wrong expiration key "+ek+" != "+v[0])
                    if d > v[1]:
                        raise Exception("Error no expiration "+str(ev)+" != "+str(d))
                    print("Pass "+ek+" expired in "+str(d))

        
if __name__ == "__main__":
    mTimer.main()