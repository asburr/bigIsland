#!/usr/bin/env python3
from time import sleep
import threading
import logging
from magpie.mlogger import MLogger
from magpie.mzdatetime import MZdatetime
import traceback


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
        self.sampleDuration = sampleDuration
        self.rangeStart = 59
        self.rangeSize = 35

    def calibrate(self, report: bool = False):
        self.calibrating = True
        self.startCalibrate = True
        self.stopCalibrate = False
        sleep(self.sampleDuration)
        if self.startCalibrate:
            raise Exception("calibration did not start in the " + str(self.sampleDuration) + " seconds wait period")
        c = self.count
        d = MZdatetime().timestamp() - self.cstart
        self.cstart = 0.0
        self.idleCountPerSecond = c / d
        self.stopCalibrate = True
        # Wait for idle thread to ack the stopping of calibration before saying it's complete
        while self.startCalibrate:
            sleep(0.1)
        self.calibrating = False
        sleep(1)
        newRangeStart = self.getIdle()
        h = HelloWorld({"usage": 50})
        h.start()
        sleep(self.sampleDuration)
        newRangeSize = newRangeStart - ((newRangeStart - self.getIdle()) * 2)
        h.stop = True
        sleep(1)  # Give some time for HelloWorld to stop.
        self.rangeStart = newRangeStart
        self.rangeSize = newRangeSize
        if report:
            print("Calibrate dur=" + str(d))
            print("Calibrate count=" + str(c))
            print("Calibrate c" + str(self.idleCountPerSecond))
            print("Calibrate rangeStart=" + str(self.rangeStart))

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
            cb = MZdatetime().timestamp()
            sleep(self.delay)  # Yield
            c = MZdatetime().timestamp()
            d = c - cb
            if d < self.delay:
                raise Exception("Slept too less " + str(d))
            self.count += 1
            d = c - start
            if d > self.sampleDuration:
                if not self.calibrating:
                    countPerSecond = self.count / d
                    # Hmm, new idle value.
                    if countPerSecond > self.idleCountPerSecond:
                        self.idleCountPerSecond = countPerSecond
                    i = countPerSecond / self.idleCountPerSecond * 100
                    self.idle = ((i - 63) / 37) * 100
                    self.count = 0.0
                start = MZdatetime().timestamp()

    def getIdle(self) -> int:
        return self.idle


class MThreads:
    # idleDelay: Delay can be yield to other threads without wiat(0) or yield with a wait.
    # sampleDuration: duration is the sampling window for determining the next idle.
    # idlePercentageGoal: percentage of the CPU to remain idle on average.
    def __init__(self, idleDelay: float = 0.01, sampleDuration: float = 2.0, idlePercentageGoal: int = 20):
        self.maxThreadLogged = False
        self.logger = MLogger.getLogger()
        self.threads = []
        self.threadClass = None
        self.threadCfg = None
        self.minThreads = None
        self.maxThreads = None
        self.idleThread = MThreadIdle(delay=idleDelay, sampleDuration=sampleDuration)
        self.idlePercentageGoal = idlePercentageGoal

    def threadCount(self) -> int:
        return len(self.threads)

    def startup(self, threadClass: any, threadCfg: dict, minThreads: int, maxThreads: int) -> None:
        if minThreads > maxThreads:
            raise Exception(
                "MThreads minthreads=%d maxThreads=%d must be more than 2 difference" % (minThreads, maxThreads)
            )
        self.threadClass = threadClass
        self.threadCfg = threadCfg
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
        if size:
            usagePerThread = (100 - idle) / size
            idleLimit = self.idlePercentageGoal + usagePerThread
        else:
            idleLimit = 50
        # Add a thread when all threads ran in this period and there is space CPU (idle is above the goal).
        if MThread.peakRunningCount == size and idle > idleLimit:
            if size < self.maxThreads:
                self.maxThreadLogged = False
                if self.logger.isEnabledFor(logging.WARNING):
                    self.logger.warning("MThreads: %d/%d threads running idle=%d max=%d, creating one more",
                                        MThread.peakRunningCount, size, idle, self.maxThreads)
                # noinspection PyBroadException
                try:
                    s = self.threadClass(self.threadCfg)
                    self.threads.append(s)
                    s.start()
                except Exception:
                    if self.logger.isEnabledFor(logging.ERROR):
                        self.logger.error("mthread for %s; failed to start thread %s", self.threadClass.__name__,
                                          traceback.format_exc())
            else:
                if not self.maxThreadLogged:
                    if self.logger.isEnabledFor(logging.DEBUG):
                        self.logger.debug("MThreads: %d/%d threads running, reach max %d and wont create more",
                                          MThread.peakRunningCount, size, self.maxThreads)
        # Remove a thread when one (or more) thread did not run in this period
        elif MThread.peakRunningCount < (size - 1) and size > self.minThreads:
            if self.logger.isEnabledFor(logging.WARNING):
                self.logger.warning("MThreads: %d/%d threads running idle=%d, stopped one",
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
        print("Capacity %d%% threads ran %d" % (self.idleThread.getIdle(), MThread.peakRunningCount))
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
class HelloWorld(MThread):
    HWlst = []
    pause = False

    def __init__(self, cfg: dict):
        MThread.__init__(self)
        self.logger = MLogger.getLogger()
        self.HWlst.append(self)
        p = cfg["usage"] / 100
        self.processing = 0.1 * p
        self.sleep = 0.1 * (1 - p)
        self.tick = 0

    def run(self) -> None:
        self.ThreadRunning()
        while not self.stop:
            self.tick += 1
            if HelloWorld.pause:
                sleep(1)
            sleep(self.sleep)
            start = MZdatetime().timestamp()
            while (MZdatetime().timestamp() - start) < self.processing:
                _x = 1234 / 12.34
        self.ThreadStopped()


def main():
    MLogger.setLevel(logging.INFO)
    cfg = {"usage": 17}
    m = MThreads()
    m.startup(HelloWorld, cfg, 1, 200)
    print("#1: Pausing workers, idle should be 100%")
    HelloWorld.pause = True
    sleep(m.idleThread.sampleDuration + 1)
    print("#1: after one period")
    m.show()
    sleep(m.idleThread.sampleDuration + 1)
    print("#1: finished: resuming workers")
    HelloWorld.pause = False
    peakTick = 0
    peakThread = 0
    print("#2 letting workers run freely, idle should read 30% and not get below that")
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
            print("%d: %d peak threads. %d idle. Ran more Hello worlds %d => %d" % (
                i, peakThread, m.getIdle(), peakTick, tick))
        else:
            print("%d: %d peak threads. %d idle. Ran less Hello worlds %d(%d) => %d" % (
                i, peakThread, m.getIdle(), peakTick, peakThread, tick))
    m.shutdown()


if __name__ == "__main__":
    main()
