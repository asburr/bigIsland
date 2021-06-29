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
# The only complexity is cpu usage which handles being called too frequently
# by comparing usage at least one second in the past.
import psutil
from time import sleep

class MUsage():
    
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
            raise Exception("no memory inc during initialization")

    def memoryUsage(self) -> int:
        return int(psutil.virtual_memory().percent)

    def memoryFree(self) -> int:
        return int(psutil.virtual_memory().available * 100 /
                   psutil.virtual_memory().total)

    # 0 at least one second ago but could be more.
    # 1 most recent usage.
    # 2 Current usage.
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