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
# This is Zulu datetime
#
# Usage is similar to datetime,
#  from datetime import timedelta
#  from magoie.MZdatetime import MZdatetime
#  import copy
#
#  dt: MZdatetime = MZdatetime()
#  dt.inc(timedelta(days=3))
#  s: str = dt.strftime()
#  dt = MZdatetime.strptime()
#  ts: float = dt.timestamp()
#  dt = MZdatetime.fromtimestamp(ts)
#  dt2: MZdatetime = copy.copy(dt)
#
# Why use MZdatetime?
# 1. Python assumes local timezone.
#    1.1 utcnow returns a UTC time with implied local timezone.
#    1.2 datetime with a timezone shall converts the UTC time to local time.
# 2. Python requires programs to explicity identify timezone.
# 3. String with a "Z" at the end is a UTC time, the datetime implies local timezone.
from datetime import datetime, timezone, timedelta
import dateutil.parser  # Note that dateutil.parser does not handle all case and date parsing is re-implemented.
import copy


class MZdatetime:

    def __init__(self):
        self.dt = datetime.utcnow().replace(tzinfo=timezone.utc)

    def now(self):
        self.dt = datetime.utcnow().replace(tzinfo=timezone.utc)

    @classmethod
    def _getDateFmt(cls, s: str, ln: int) -> (str, str, str):
        if s[2] == "/":
            if ln == 8:
                return "%m/%d/%y", s, ""
            elif ln == 10:
                return "%m/%d/%Y", s, ""
            elif s[8].isdigit():
                return "%m/%d/%Y", s[0:10], s[10:]
            else:
                return "%m/%d/%y", s[0:8], s[8:]
        elif s[2] == "-":
            fmt = "%y-%m-%d"
            if ln == 8:
                return fmt, s, ""
            else:
                return fmt, s[0:8], s[8:]
        elif s[4] == "-":
            fmt = "%Y-%m-%d"
            if ln == 10:
                return fmt, s, ""
            else:
                return fmt, s[0:10], s[10:]
        raise Exception("mzdatetime:" + s)

    # Pls see main() for cases not handled by dateutil.parser and why it is not used here.
    @classmethod
    def strptime(cls, s: str) -> 'MZdatetime':
        dt = cls()
        ln = len(s)
        if ln < 8:
            raise Exception("mzdatetime:" + s)
        fmt, d, t = cls._getDateFmt(s, ln)
        if not t:
            dt.dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt
        ln = len(t)
        if ln < 9:
            raise Exception("mzdatetime:" + s)
        if t[0] == "T" or t[0] == " ":
            fmt += t[0] + "%H:%M:%S"
        else:
            raise Exception("mzdatetime:" + s)
        if ln == 9:
            dt.dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        elif ln == 10:
            dt.dt = datetime.strptime(s, fmt + "Z").replace(tzinfo=timezone.utc)
        elif ln == 12:
            if t[9] == ".":
                dt.dt = datetime.strptime(s, fmt + ".%f").replace(tzinfo=timezone.utc)
            elif t[10].isdigit():
                dt.dt = datetime.strptime(d+t[0:9], fmt).replace(tzinfo=timezone.utc)
                dt.dt += timedelta(hours=int(t[9:12], 10))
            elif t[10].isalpha():
                fmt = fmt.replace("%H", "%I")  # %I is 12 hour clock and needed for %p to work!
                fmt += " %p"
                dt.dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            else:
                raise Exception("mzdatetine:" + s)
        elif ln == 15:
            dt.dt = datetime.strptime(d+t[0:9], fmt).replace(tzinfo=timezone.utc)
            # Note the sign(-+) is added to the minutes - as hour sign is lost on a zero hour increment
            dt.dt += timedelta(hours=int(t[9:12], 10), minutes=int(t[9] + t[13:15], 10))
        elif ln == 16:
            dt.dt = datetime.strptime(s, fmt + ".%f").replace(tzinfo=timezone.utc)
        else:
            dt.dt = datetime.strptime(s, fmt + ".%fZ").replace(tzinfo=timezone.utc)
        return dt

    def strftime(self, short: bool = False, fmt: str = "%Y-%m-%dT%H:%M:%S.%fZ") -> str:
        if short:
            return self.dt.strftime("%Y-%m-%dT%H:%M:%S")
        return self.dt.strftime(fmt)

    def timestamp(self) -> float:
        return self.dt.timestamp()

    @classmethod
    def fromdatetime(cls, d: datetime) -> 'MZdatetime':
        dt = cls()
        dt.dt = d.replace(tzinfo=timezone.utc)
        return dt

    def todatetime(self) -> datetime:
        return self.dt.replace(tzinfo=None)

    @classmethod
    def fromtimestamp(cls, ts: float) -> 'MZdatetime':
        dt = cls()
        dt.dt = datetime.fromtimestamp(ts, timezone.utc)
        return dt

    # op(+) is monomorphic
    # 1/ op(+) timedelta, returns MZdatetime
    # 2/ op(+) datetime, raises exception.
    def __add__(self, other: timedelta) -> 'MZdatetime':
        dt = MZdatetime()
        dt.dt = self.dt + other
        return dt

    # op(+=) is monomorphic
    # 1/ op(+=) timedelta, returns MZdatetime
    # 2/ op(+=) datetime, raises exception.
    def __iadd__(self, other: timedelta) -> 'MZdatetime':
        self.dt += other
        return self

    # op(-) is polymorphic
    # 1/ op(-) timedelta, returns MZdatetime
    # 2/ op(-) MZdatetime, returns timedelta.
    def __sub__(self, other: any) -> any:
        if isinstance(other, MZdatetime):
            if self < other:
                raise Exception("MZdatetime < MZdatetime for " + str(self) + " - " + str(other))
            return self.dt - other.dt  # Type timedelta
        if isinstance(other, timedelta):
            dt = MZdatetime()
            dt.dt = self.dt - other
            return dt
        raise Exception("MZdatetime op(-) MZdatetime/timedelta not " + str(type(other)))

    # op(-=) is polymorphic
    # 1/ op(-=) timedelta, returns MZdatetime
    # 2/ op(-=) MZdatetime, returns timedelta.
    # but #1 converts the varaible MZdatetime to timedelta. This behaviour is not
    # liked. Thus only support #2.
    def __isub__(self, other: any) -> any:
        self.dt -= other
        return self

    def __eq__(self, other: 'MZdatetime') -> bool:
        return self.dt == other.dt

    def __gt__(self, other: 'MZdatetime') -> bool:
        return self.dt > other.dt

    def __ge__(self, other: 'MZdatetime') -> bool:
        return self.dt >= other.dt

    def __lt__(self, other: 'MZdatetime') -> bool:
        return self.dt < other.dt

    def __le__(self, other: 'MZdatetime') -> bool:
        return self.dt <= other.dt

    def __str__(self) -> str:
        return self.strftime()

    def __copy__(self) -> 'MZdatetime':
        return self.fromtimestamp(self.timestamp())

    def __deepcopy__(self, memo: dict) -> 'MZdatetime':
        return self.__copy__()

    def replace(self, year=None, month=None, day=None, hour=None,
                minute=None, second=None, microsecond=None) -> 'MZdatetime':
        dt = MZdatetime()
        dt.dt = self.dt
        if year:
            dt.dt = dt.dt.replace(year=year)
        if month:
            dt.dt = dt.dt.replace(month=month)
        if day:
            dt.dt = dt.dt.replace(day=day)
        if hour:
            dt.dt = dt.dt.replace(hour=hour)
        if minute:
            dt.dt = dt.dt.replace(minute=minute)
        if second:
            dt.dt = dt.dt.replace(second=second)
        if microsecond:
            dt.dt = dt.dt.replace(microsecond=microsecond)
        return dt

    @staticmethod
    def main():
        s = "2020-12-25T00:40:54.252020Z"
        dt = MZdatetime.strptime(s)
        t = dt.strftime()
        if t != s:
            raise Exception("Failed " + t)
        dt += timedelta(days=3)
        if dt.strftime() != "2020-12-28T00:40:54.252020Z":
            raise Exception("Failed " + str(dt))
        ts = dt.timestamp()
        if ts != 1609116054.25202:
            raise Exception("Failed " + str(ts))
        dt2 = MZdatetime.fromtimestamp(ts)
        if dt2 != dt:
            raise Exception("Failed " + str(dt2) + " " + str(dt))
        dt2 = copy.copy(dt)
        if dt2 != dt:
            raise Exception("Failed " + str(dt2) + " " + str(dt))
        dt2 += timedelta(seconds=4)
        if dt2.strftime() != "2020-12-28T00:40:58.252020Z":
            raise Exception("Failed " + str(dt))
        td = dt2 - dt
        if td != timedelta(seconds=4):
            raise Exception("Failed " + str(dt))
        dt3 = copy.copy(dt)
        dt += td
        if dt != dt2:
            raise Exception("Failed " + str(dt) + " " + str(dt2))
        dt -= td
        if dt != dt3:
            raise Exception("Failed " + str(dt) + " " + str(dt3))
        for string, result in [
            # 123456789012345678901234567 - Length
            # 012345678901234567890123456 - Index
            ("2012-12-12", "2012-12-12T00:00:00.000000Z"),
            ("2012-12-12T10:53:43", "2012-12-12T10:53:43.000000Z"),
            ("2012-12-12 10:53:43", "2012-12-12T10:53:43.000000Z"),
            ("12/12/12 10:53:43", "2012-12-12T10:53:43.000000Z"),
            ("2012-12-12T10:53:43Z", "2012-12-12T10:53:43.000000Z"),
            ("2012-12-12T10:53:43-08", "2012-12-12T02:53:43.000000Z"),
            ("2012-12-12T10:53:43+08", "2012-12-12T18:53:43.000000Z"),
            ("2012-12-12T10:53:43 08", "2012-12-12T18:53:43.000000Z"),
            ("2012-12-12T10:53:43 am", "2012-12-12T10:53:43.000000Z"),
            ("2012-12-12T10:53:43 pm", "2012-12-12T22:53:43.000000Z"),
            ("2012-12-12T10:53:43 PM", "2012-12-12T22:53:43.000000Z"),
            ("2012-12-12T10:53:43-08:00", "2012-12-12T02:53:43.000000Z"),
            ("2012-12-12T10:53:43-08:10", "2012-12-12T02:43:43.000000Z"),
            ("2012-12-12T10:53:43-08:30", "2012-12-12T02:23:43.000000Z"),
            ("2012-12-12T10:53:43+00:03", "2012-12-12T10:56:43.000000Z"),
            ("2012-12-12T10:53:43.00", "2012-12-12T10:53:43.000000Z"),
            ("2012-12-12T10:53:43.123456", "2012-12-12T10:53:43.123456Z"),
            ("2012-12-12T10:53:43.123456Z", "2012-12-12T10:53:43.123456Z")
        ]:
            try:
                dt = MZdatetime.strptime(string)
                got = dt.strftime()
                if got != result:
                    raise Exception("Failed " + string + " " + got + " != " + result)
                try:
                    dt = MZdatetime.fromdatetime(dateutil.parser.parse(string))
                    got = dt.strftime()
                    if got != result:
                        print("INFO : dateutil failed " + string + " " + got + " != " + result)
                except Exception:
                    print("INFO : dateutil failed " + string)
            except Exception:
                print("Failed " + string)
                raise


if __name__ == "__main__":
    MZdatetime.main()
