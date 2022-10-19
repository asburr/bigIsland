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
# Wrapper around python threads.
#
# Why python threads?
# Threading makes better use of the CPU in the case when a program is
# interrupted by writing to output or reading from input and the CPU is idle
# while the program is waiting for those operations to complete. 
# Multiple threads runs multiple programs in a interleaved fashion such that
# another programs will run when the currently running program blocks waiting
# for input or output.
#
# Why MThreads?
# MThreads determines the number of threads that is needed to keep the CPU
# busy while not overloading the CPU. Too much CPU usage and the threads run
# inefficently as they compete for the same CPU. Too few threads and the CPU
# is underutilized. CPU utilization is critical on platforms with horizontal
# pod autoscalers, like Kubernetes. Too little CPU usage and the scalers
# wont ever be triggered, too much cpu usage overloads the pod.
#
# Okay, so what does MThreads do?
# MThreads creates an additional thread that measures idleness. MThreads
# creates threads up until the idle threashold is reached. MThreads deletes
# threads when the CPU is too busy. 
#
from time import sleep
import threading
import logging
from magpie.src.mlogger import MLogger
from magpie.src.mzdatetime import MZdatetime
import traceback
import argparse


class MThread(threading.Thread):
    peakRunningCount = 0
    runningCount = 0

    def __init__(self):
        threading.Thread.__init__(self)
        self.running = False
        self.stop = False

    def ThreadRunning(self) -> None:
        MThread.runningCount += 1
        if MThread.runningCount > MThread.peakRunningCount:
            MThread.peakRunningCount = MThread.runningCount
        self.running = True

    def ThreadStopped(self) -> None:
        MThread.runningCount -= 1
        if MThread.runningCount < 0:
            MThread.runningCount = 0
        self.running = False


class MThreadIdle(threading.Thread):
    def __init__(self, delay: float, sampleDuration: float):
        threading.Thread.__init__(self)
        self.count = 0.0
        self.idle = 0
        self.idleCountPerSecond = 0
        self.stop = False
        self.cstart = 0.0
        self.startCalibrate = False
        self.stopCalibrate = False
        self.calibrating = True
        self.delay = delay
        self.delayX = 0.0
        self.sampleDuration = sampleDuration

    def calibrate(self, report: bool = False):
        start = MZdatetime().timestamp()
        sleep(1.0)  # Test how long delay actually delays.
        d = MZdatetime().timestamp() - start
        self.delayX = self.delay + (d - 1.0)
        if report:
            print("Calibrate")
            print("  delay=" + str(self.delay))
            print("  delayX=" + str(self.delayX))

        self.calibrating = True
        self.startCalibrate = True
        self.stopCalibrate = False
        sleep(0.1)  # Give time for calibrate to start.
        if self.startCalibrate:
            raise Exception("calibration did not start in the " +
                            str(self.sampleDuration) +
                            " seconds wait period")
        sleep(1.0)  # calibrate for a second.
        # Get calibration results.
        c, start = self.count, self.cstart
        d = MZdatetime().timestamp() - start
        self.idleCountPerSecond = int(c / d)
        self.stopCalibrate = True
        self.calibrating = False
        # Wait for idle thread to stop calibration
        while self.stopCalibrate:
            sleep(0.1)
        if report:
            print("Calibrate")
            print("  dur=" + str(d))
            print("  count=" + str(c))
            print("  perSec=" + str(self.idleCountPerSecond))

    def run(self) -> None:
        start = MZdatetime().timestamp()
        self.count = 0.0
        while not self.stop:
            if self.startCalibrate:
                self.cstart = MZdatetime().timestamp()
                self.count = 0.0
                self.startCalibrate = False
            if self.stopCalibrate:
                start = MZdatetime().timestamp()
                self.count = 0.0
                self.stopCalibrate = False
            cb = MZdatetime().timestamp() # Another yield!
            sleep(self.delay)  # Yield
            c = MZdatetime().timestamp() # Another yield!
            d = c - cb
            if d < self.delay:
                raise Exception("Slept too less " + str(d))
            elif d < self.delayX:
                self.count += 1
            d = c - start
            if d > self.sampleDuration:
                if not self.calibrating:
                    if self.count:
                        print("idle c="+str(self.count)+" d="+
                              str(d) + " lowest="+
                              str(self.idleCountPerSecond))
                        countPerSecond = self.count / d
                        if countPerSecond > self.idleCountPerSecond:
                            # if self.logger.isEnabledFor(logging.WARNING):
                            #    self.logger.warning(
                            #        "mthread new idle count=%d was=%d",
                            #        countPerSecond,
                            #        self.idleCountPerSecond)
                            self.idleCountPerSecond = countPerSecond
                        self.idle = int(countPerSecond /
                                        self.idleCountPerSecond * 100)
                        self.count = 0.0
                    else:
                        self.idle = 0
                start = MZdatetime().timestamp()

    def getIdle(self) -> int:
        return self.idle


class MThreads:
    # idleDelay: Delay can be yield to other threads without wait(0) or yield with a wait.
    # sampleDuration: duration is the sampling window for determining the next idle.
    # idlePercentageGoal: percentage of the CPU to remain idle on average.
    def __init__(self,
                 idleDelay: float = 0.01,
                 sampleDuration: float = 2.0,
                 idlePercentageGoal: int = 20):
        self.maxThreadLogged = False
        self.logger = MLogger.getLogger()
        self.threads = []
        self.threadClass = None
        self.threadCfg = None
        self.idleTarget = 30
        self.minThreads = None
        self.maxThreads = None
        self.idleThread = MThreadIdle(delay=idleDelay, sampleDuration=sampleDuration)
        self.idlePercentageGoal = idlePercentageGoal

    def threadCount(self) -> int:
        return len(self.threads)

    def startup(self,
                threadClass: any,
                threadCfg: dict,
                idleTarget: int = 30,
                minThreads: int = 1,
                maxThreads: int = 10) -> None:
        if minThreads > maxThreads:
            raise Exception(
                "MThreads minthreads=%d maxThreads=%d" %
                (minThreads, maxThreads)
            )
        self.threadClass = threadClass
        self.threadCfg = threadCfg
        self.idleTarget = idleTarget
        self.minThreads = minThreads
        self.maxThreads = maxThreads
        self.idleThread.start()
        self.idleThread.calibrate()
        for i in range(self.minThreads):
            s = self.threadClass(self.threadCfg)
            s.start()
            self.threads.append(s)

    def check(self) -> int:
        idle = self.idleThread.getIdle()
        size = len(self.threads)
        # Add a thread when all threads ran in this period and there is spare
        # CPU (idle is above the goal).
        if idle > self.idlePercentageGoal:
            if size < self.maxThreads:
                self.maxThreadLogged = False
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(
                        "MThreads: %d/%d threads running idle=%d target=%d "
                        "max=%d, creating one more",
                        MThread.peakRunningCount, size, idle,
                        self.idlePercentageGoal, self.maxThreads)
                # noinspection PyBroadException
                try:
                    s = self.threadClass(self.threadCfg)
                    self.threads.append(s)
                    s.start()
                except Exception:
                    if self.logger.isEnabledFor(logging.ERROR):
                        self.logger.error(
                            "mthread for %s; failed to start thread %s",
                            self.threadClass.__name__,
                            traceback.format_exc())
            else:
                if not self.maxThreadLogged:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug(
                            "MThreads: %d/%d threads running, reach max %d and wont create more",
                                          MThread.peakRunningCount, size, self.maxThreads)
        elif idle < self.idlePercentageGoal and size > self.minThreads:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug("MThreads: %d/%d threads running idle=%d, stopped one",
                                    MThread.peakRunningCount, size, idle)
            notRunning = self.threads[0]
            notRunning.stop = True
            notRunning.join()
            self.threads.remove(notRunning)
        MThread.peakRunningCount = MThread.runningCount
        return idle

    def shutdown(self) -> None:
        self.idleThread.stop = True
        for s in self.threads:
            s.stop = True
        for s in self.threads:
            s.join()
        self.threads = []
        MThread.runningCount = 0

    def show(self, details: bool = True) -> None:
        print("Idle=%d%% threads=%d" %
              (self.idleThread.getIdle(),
               MThread.peakRunningCount,
               ))
        if details:
            i = 0
            for s in self.threads:
                i += 1
                print("%d Running=%s stop=%s" % (i, s.running, s.stop))

    def getIdle(self) -> int:
        return self.idleThread.getIdle()


# HellowWorld hogs the CPU by a percentage defined in cfg["usage"]
# If sleeps for the other percentage and runs maths while using the CPU.
# it can be tested using the followi g procedures and using Unix "top" to watch the CPU usage
# which should/will be cfg["usage"]
# For example,
# from magpie.mthreads import HellowWorld
# x = HelloWorld({"usage": 33})
# x.start()
# Why when using larger slice count do the smaller hogs run longer.
#     when using smaller slice count the hogs uniformally run longer.
#     15 20 25 30 35 40 45 50
# 7 slices,
# 007 19 24 29 33 39 43 48 53
#      4  4  4  3  4  3  3  3
# 20 slices,
# 007 25    33             54
#     10     8              4
# 100 slices
# 007 30    39             51
#     15    14              1
class HelloWorld(MThread):
    HWlst = []
    pause = False

    @classmethod
    def setup(cls):
        start = MZdatetime().timestamp()
        count = 30000000
        for i in range(30000000):
            _x = 1234 / 12.34
        dur = MZdatetime().timestamp() - start
        HelloWorld.countPerSecond = int(count / dur)
        print("HelloWorld count="+str(count)+" took="+str(dur)+
              " countSec="+str(HelloWorld.countPerSecond))

    def __init__(self, cfg: dict):
        MThread.__init__(self)
        self.logger = MLogger.getLogger()
        self.HWlst.append(self)
        p = cfg["usage"] / 100
        # tick 100 times a second.
        self.countForProcessing = int(HelloWorld.countPerSecond * p / 100)
        self.sleep = (1 - p) / 100
        self.tick = 0
        print("HelloWorld: countP="+str(self.countForProcessing)+
              " sleep="+str(self.sleep))
        start = MZdatetime().timestamp()
        sleep(self.sleep)
        d = MZdatetime().timestamp() - start
        if d < self.sleep:
            raise Exception("HelloWorld sleep too small, sleep "
                            + str(self.sleep) + " slept " +
                            str(d))

    def run(self) -> None:
        self.ThreadRunning()
        while not self.stop:
            if HelloWorld.pause:
                sleep(1)
            else:
                self.tick += 1
                sleep(self.sleep)
                for i in range(self.countForProcessing):
                    _x = 1234 / 12.34
        self.ThreadStopped()


def main():
    HelloWorld.setup()
    parser = argparse.ArgumentParser(description="Mthreads")
    parser.add_argument('usage',
                        help="CPU usage per thread", type=int)
    parser.add_argument('target',
                        help="Target CPU idle", type=int)
    parser.add_argument('-w', '--helloworld', help="Run hello world",
                        type=int)
    parser.add_argument('-i', '--idlethread', help="Run hello world with idle",
                        action="store_true")
    args = parser.parse_args()
    if args.helloworld is not None:
        if args.idlethread:
            idleThread = MThreadIdle(delay=0.01, sampleDuration=2.0)
            idleThread.start()
            idleThread.calibrate(report=True)
        hellos = []
        for i in range(args.helloworld):
            helloworld = HelloWorld(cfg={"usage":args.usage})
            hellos.append(helloworld)
            helloworld.start()
            sleep(4.0)
            if args.idlethread:
                print("Setup Idle=" + str(idleThread.getIdle()) + "%")
            ticks = []
            for hello in hellos:
                ticks.append(hello.tick)
                hello.tick = 0
            print("Setup hellos ran for " + str(ticks))
        while True:
            sleep(4.0)
            if args.idlethread:
                print("Idle=" + str(idleThread.getIdle()) + "%")
            ticks = []
            for hello in hellos:
                ticks.append(hello.tick)
                hello.tick = 0
            print("Hellos ran for " + str(ticks))
    else:
        MLogger.setLevel(logging.WARNING)
        m = MThreads()
        perThreadUsage = args.usage
        m.startup(HelloWorld,
                  threadCfg={"usage": perThreadUsage},
                  idleTarget=args.target,
                  minThreads=1,
                  maxThreads=200)
        sleep(1)
        print("#1: waited one second for things to startup")
        m.show()
        dur = m.idleThread.sampleDuration + 1
        sleep(dur)
        print("#2: should be " + str(perThreadUsage) + "% busy")
        m.show()
        HelloWorld.pause = True
        sleep(dur)
        print("#3: paused worker should be 100% idle")
        m.show()
        HelloWorld.pause = False
        peakTick = 0
        peakThread = 0
        print("#4 letting workers run freely, idle should read 30% and not get below that")
        for i in range(100):
            m.check()
            sleep(5)
            tick = 0
            for hw in HelloWorld.HWlst:
                tick += hw.tick
                hw.tick = 0
            if tick > peakTick:
                peakTick = tick
                peakThread = m.threadCount()
                print("%d: threads=%d idle=%d. %d +> %d" % (
                    i, peakThread, m.getIdle(), peakTick, tick))
            else:
                print("%d: threads=%d idle=%d. %d => %d" % (
                    i, peakThread, m.getIdle(),peakTick, tick))
        m.shutdown()


if __name__ == "__main__":
    main()
