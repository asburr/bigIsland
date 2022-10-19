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
        """ duration is seconds. """
        self.timers={}
        self.dur = duration

    def start(self, k:str, v: any = None) -> None:
        if k in self.timers:
            return
        self.timers[k] = (time() + self.dur, v)

    def stop(self, k: str) -> bool:
        try:
            del self.timers[k]
        except:
            return False
        return True

    def get(self, k: str) -> any:
        return self.timers.get(k,None)

    def getStop(self, k: str) -> any:
        """ Stops timer and return the value for the stopped timer, or None when timer does not exist. """
        retval = self.get(k)
        self.stop(k)
        return retval

    def walk(self) -> [(str, bool, any)]:
        """ Not a generator to allow stop within a loop over walk(). """
        t = time()
        return [(k, (t > v[0]), v[1]) for k, v in self.timers.items()]

    def expired(self) -> (str, any):
        """ Expired timers are stopped and k,v pair is returned. """
        t = time()
        expired = []
        for k, v in self.timers.items():
            if v[0] > t: # Dict maintains order of insert.
                break
            expired.append((k,v[1]))
        for k, v in expired:
            del self.timers[k]
            yield (k,v)

    @staticmethod
    def main():
        # Test the module.
        t = mTimer(1)
        test = [("1",1.1),("2",1.2),("3",1.3),("4",1.4),("5",1.5),("6",1.6)]
        start = time()
        print("Starting timers with a .1 interval")
        for v in test:
            sleep(0.1)
            t.start(v[0],v[1])
        for v in test:
            print("TEST")
            print(v)
            timeout = False
            while not timeout:
                for (ek, ev) in t.expired():
                    timeout = True
                    d = round(time() - start,1)
                    try:
                        if ev != d:
                            raise Exception("Error : expected dur="+str(ev)+" actual="+str(d))
                        if ek != v[0]:
                            raise Exception("Error wrong expiration key "+ek+" != "+v[0])
                        if d > v[1]:
                            raise Exception("Error no expiration "+str(ev)+" != "+str(d))
                    except Exception as e:
                        print(e)
                    print("Pass "+ek+" expired in "+str(d))
                if not timeout:
                    sleep(0.1)


if __name__ == "__main__":
    mTimer.main()