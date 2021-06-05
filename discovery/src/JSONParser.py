#!/usr/bin/env python3
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

import json
import argparse
from discovery.src.parser import Parser
from magpie.src.mistype import MIsType

class JSONStats:
    """
    stats = {
        "<fieldname>": {
            "count": <occ>,
            "example": <example>,
            "datatypes": {
                "<datatype>": {
                    "count": <occ>,
                    "example": <example>
               }
            },
            "values": {
                "<value>": {
                    "count": <occ>
                }
            }
        }
    }
    values = {
        "<fieldname>": {}
    }
    """
    def __init__(self):
        self.stats = {}
        self.values = {}

    def gatherStats(self, label: str, obj: any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.gatherStats(label+"->"+k, v)
        elif isinstance(obj, list):
            for v in obj:
                self.gatherStats(label+"->item", v)
        else:
            if label not in self.stats:
                self.stats[label] = {
                    "count": 0,
                    "example": obj,
                    "datatypes": {},
                    "values": {}
                }
            d = self.stats[label]
            d["count"] += 1
            t = MIsType.isType(label, type(obj), obj)
            dt = d["datatypes"]
            if t not in dt:
                dt[t] = {
                    "count": 0,
                    "example": obj
                }
            d = dt[t]
            d["count"] += 1
            if label in self.values:
                dv = d["values"]
                if obj not in dv:
                    dv[obj] = {"count": 0}
                d = dv[obj]
                d["count"] += 1

    def merge(self, other: "JSONStats") -> None:
        for k, v in other.stats:
            if k not in self.stats:
                self.stats[k] = other.v
            else:
                d = self.stats[k]
                d["count"] += v["count"]
                dt = d["datatypes"]
                for t, tv in v["datatypes"]:
                    if t not in dt:
                        dt[t] = tv
                    else:
                        dt[t]["count"] += tv["count"]
                dv = d["values"]
                for v, vv in v["values"]:
                    if v not in dv:
                        dv[v] = vv
                    else:
                        dv["count"] += vv["count"]


class JSONParser(Parser):
    def __init__(self):
        self.stats = JSONStats()
        self.j = {}
        
    def parse(self, file: str) -> list:
        self.j = self.toJSON(file)
        print(self.j)
        self.stats.gatherStats("", self.j)
        print(self.stats.stats)
        
    def toJSON(self, file: str) -> any:
        with open(file, "r") as f:
            self.j = json.load(f)
            self.j = self._wireshark(self.j)
            return self.j

    def getStats(self) -> JSONStats:
        self.stats.gatherStats("", self.j)
        return self.stats

    # Wireshark has hexdumps within fields.
    def ishexdump(self, s: str) -> bool:
        i = 0
        e = len(s)
        retval = False
        while True:
            if i == e:
                return retval
            if (
                    (s[i] >= '0' and s[i] <= '9') or
                    (s[i] >= 'a' and s[i] <= 'f')
                ):
                i += 1
            else:
                return False
            if i == e:
                return retval
            if (
                    (s[i] >= '0' and s[i] <= '9') or
                    (s[i] >= 'a' and s[i] <= 'f')
                ):
                i += 1
                retval = True
            else:
                return False
            if i == e:
                return retval
            if s[i] == ":":
                i += 1
            else:
                return False
        return retval

    def _wireshark(self, obj: any) -> any:
        """See wireshark_test1_input.json and wireshark_test1_output.json
        """
        if isinstance(obj, dict):
            lst = list(obj.keys())
            wiresharkSummaryFields = True
            delField = set()
            for field in lst:
                # Wireshark values in field names have ": " in
                # the field name that is a dictionary. This is true
                # for all fields.
                if ": " not in field or not isinstance(obj[field], dict):
                    wiresharkSummaryFields = False
                if (
                        field.endswith("data") or
                        field.endswith("padding") or
                        field.endswith("unused")
                    ):
                    if self.ishexdump(obj[field]):
                        delField.add(field)
            if wiresharkSummaryFields:
                l = []
                for field in lst:
                    v = obj[field]
                    v["__ws_summary"] = field
                    l.append(self._wireshark(v))
                return l
            else:
                if delField:
                    for field in delField:
                        del obj[field]
                    lst = list(obj.keys())
                for field in lst:
                    obj[field] = self._wireshark(obj[field])
                return obj
        elif isinstance(obj, list):
            return [self._wireshark(v) for v in obj]
        else:
            return obj

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="JSON Parser")
        parser.add_argument('input', help="input file")
        parser.add_argument('-o', '--output', help="expected output file")
        args = parser.parse_args()
        p = JSONParser()
        j = p.toJSON(file=args.input)
        if args.output:
            with open(args.output, "r") as f:
                oj = json.load(f)
                if oj != j:
                    print("ERROR : mismatch output")
                    print(j)
                    print(oj)
                else:
                    print("PASS")
        else:
            print(j)
        print(p.getStats().stats)


if __name__ == "__main__":
    JSONParser.main()
