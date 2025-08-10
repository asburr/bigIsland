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
# MUsage is a wrapper for psutil, providing six functions that return
# percentage usage:
#  memoryUsage(), memoryFree()
#  cpuUsage(), cpuFree()
#  diskUsage(dir="/"), diskFree(dir="/")
# Notes:
# CPU Usage is complex. CPU values are running totals. Current
# percentage is derived from the different between current totals and totals
# gather a least a second ago. See the list self.cpuidle. cpuidle[0] is
# total from at least one second ago. cpuidle[1] is recent totals. cpuidle[2]
# is current usage.

import psutil
from time import sleep
import socket


class MUsage():
    """
    MUsage is a wrapper for psutil, providing six functions that return
    percentage usage:
      memoryUsage(), memoryFree()
      cpuUsage(), cpuFree()
      diskUsage(dir="/"), diskFree(dir="/")
     CPU Usage is complex. CPU values are running totals. Current
     percentage is derived from the different between current totals and totals
     gather a least a second ago. See the list self.cpuidle. cpuidle[0] is
     total from at least one second ago. cpuidle[1] is recent totals. cpuidle[2]
     is current usage.
    """

    def __init__(self):
        self.cpuusage = [0, 0, 0]
        self.cpuidle = [0, 0, 0]
        u = psutil.cpu_times()
        self.cpuusage[0] = (
                u.user + u.nice + u.system + # u.idle +
                u.iowait + u.irq + u.softirq + u.steal +
                u.guest + u.guest_nice
        )
        self.cpuidle[0] = u.idle
        sleep(1)
        u = psutil.cpu_times()
        self.cpuusage[1] = (
                u.user + u.nice + u.system + # u.idle +
                u.iowait + u.irq + u.softirq + u.steal +
                u.guest + u.guest_nice
        )
        self.cpuidle[1] = u.idle
        dt = (self.cpuusage[1] - self.cpuusage[0])
        di = (self.cpuidle[1] - self.cpuidle[0])
        self.oneSecondDelta = dt + di
        if not self.oneSecondDelta:
            raise Exception("psutil did not return CPU counts while sleep(1) during initialization")
        self.host = socket.gethostname()
        if not self.host:
            raise Exception("No hostname")

    def memoryUsage(self) -> int:
        return int(psutil.virtual_memory().percent)

    def memoryFree(self) -> int:
        return int(psutil.virtual_memory().available * 100 /
                   psutil.virtual_memory().total)

    def _cpuUpdate(self, init: bool = False) -> (int, int):
        u = psutil.cpu_times()
        self.cpuusage[2] = (
                u.user + u.nice + u.system + # u.idle +
                u.iowait + u.irq + u.softirq + u.steal +
                u.guest + u.guest_nice
        )
        self.cpuidle[2] = u.idle
        dt = (self.cpuusage[2] - self.cpuusage[1])
        di = (self.cpuidle[2] - self.cpuidle[1])
        d = dt + di
        if d > self.oneSecondDelta:
            # One second of total counts between [2] and [1], move
            # counts down:
            self.cpuusage[0] = self.cpuusage[1]
            self.cpuidle[0] = self.cpuidle[1]
            self.cpuusage[1] = self.cpuusage[2]
            self.cpuidle[1] = self.cpuidle[2]
        dt = (self.cpuusage[2] - self.cpuusage[0])
        di = (self.cpuidle[2] - self.cpuidle[0])
        return dt+di, dt, di

    def cpuUsage(self) -> int:
        t, u, i = self._cpuUpdate()
        if t:
            return int(u * 100 / t)
        return 0

    def cpuFree(self) -> int:
        t, u, i = self._cpuUpdate()
        if t:
            return int(i * 100 / t)
        return 0

    # dir is the partition root directory.
    def diskUsage(self, dir: str) -> int:
        u = psutil.disk_usage(dir)
        return int(u.used * 100 / u.total)

    def diskFree(self, dir: str) -> int:
        u = psutil.disk_usage(dir)
        return int(u.free * 100 / u.total)
    
    @staticmethod
    def main():
        u = MUsage()
        i = 10
        while i:
            i -= 1
            sleep(1)
            print(u.host+" cpuUsage:" + str(u.cpuUsage()))
            print(u.host+" diskUsage:" + str(u.diskUsage("/")))
            print(u.host+" memoryUsage:" + str(u.memoryUsage()))


if __name__ == "__main__":
    MUsage.main()