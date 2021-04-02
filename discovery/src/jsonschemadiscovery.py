#!/usr/bin/env python3
# JSON Schema Discovery learns the document structure from a sample of JSON documents. And can take a stream of JSON
# documents to continuously discover structural changes.
#
# JSONSchemaDiscovery is needed when the JSON documents are too complex for human analysis to find traits and for a
# human to get any kind of understanding across all of the documents. The same documents are loaded into
# JSONSchemaDiscovery which identifies a structure that is true across all of the documents.
#
# For example,
#   jps = JSONSchemaDiscovery()
#   jps.load([1,2,3])
#   jps.load([4,5])
#   jps.dumps()
#   {"t": "list", "v": {"t": "int", "v": "1", "v2": "2"}}
#
# The representation a key-value pair of "t" that identifies the type and "v" the value. The leaf values
# are int, float, and str. The leaf has a second value (v2) when in the sample documents there is a second value
# that is not the same as the first.
#
# The type can be "dict" and "switch".
#
# For example, two documents of the format {"f1": "2", "f2": 4} and {"f1": "2"}, are discovered as
# field "f1" being required ("R") as in always present, and field "f2" being optional ("O") as in not always present.
#   {"t": "dict", "v" {"R": {"f1": {"t": "int", "v": "2"}}, "O": {"f2": {"t": "int", "v": "4"}}}
#
# A switch example, two document of the format {"a": 2, "b": 2} and {"a": 3, "c": 3}, are discovered as
# field "a" being common and {"a": 2} is always followed by {"b": 2], and {"a": 3} is always followed by {"c": 3},
# and it is described by a switch ("S") on the value in field "a". The switch is a list of cases.
#   {"t": "list", "v":
#     {"t": "switch", "v" [
#       {"S": {"a": {"t": "int", "v": "2"}}, "R": {"b": {"t": "int", "v": "2"}}, "O": {}},
#       {"S": {"a": {"t": "int", "v": "3"}}, "R": {"c": {"t": "int", "v": "3"}}, "O": {}}
#     ]
#   }
#
# Incompatible documents are detected and an IncompatibleException is raised.
#
# For example, [1,2,3] is incompatible with ["a", "b", "c"], and {"a": 1} is incompatible with {"a": "a"}.
#
# Change detection is an optional feature that detects changes to the structure of documents.
# Change detection works by recording the time when an element was last seen, and elements are deleted when they are
# older than ageoff_hour_limit which is a parameter to JSONSchemaDiscovery(). Documents may have the time when they
# were created. The name of these timestamp fields is specified by time_fields which is a parameter to
# JSONSchemaDiscovery(). Discovery may need to be run on an initial sample in order to determine the field name.
# A relative field name is used to identify fields that are not uniquely named. A the relative name uses a dot(.)
# to separate the name of the parent field, for example, the following structure has two "time" fields, and
# the parent name is used to identify "written.time" as the time when the document was created.
# {"written": {"host": "DO123", "time": "20210428T06:46:22"},
#  "firstSeen": {"host": "DO345", "time": "20200428T06:46:22"}}}
# Change Detection is deactivated when ageoff_hour_limit is zero. And, the system clock is used when time_fields is
# None.
#
from magpie.src.mistype import MIsType
import copy
import difflib
import hashlib
import json
from magpie.src.mzdatetime import MZdatetime


class IncompatibleException(Exception):
    pass


class JSONSchemaDiscovery:
    numericTypes = ["int", "float", "num"]

    def __init__(self, debug: bool = False, ageoff_hour_limit: int = 0, time_fields: list = None):
        self.debug = debug
        self.r = {}
        self.mzdatetime = MZdatetime()
        self.ageoff_hour_limit = ageoff_hour_limit
        self.time_fields = time_fields
        self.ts = int(self.mzdatetime.timestamp())

    @classmethod
    def diffmark(cls, old: 'JSONSchemaDiscovery', new: 'JSONSchemaDiscovery') -> str:
        old_lst = []
        cls._getStringRepresentation(parent="", r=old.r, rtn=old_lst, leaves=True, values=True)
        new_lst = []
        cls._getStringRepresentation(parent="", r=new.r, rtn=new_lst, leaves=True, values=True)
        diff = ""
        for y in difflib.unified_diff(a=old_lst, b=new_lst, fromfile="old", tofile="new", n=10000):
            if diff:
                diff += "\n"
            diff += y
        return diff

    def jdump(self, f: any):
        json.dump(self.r, f)

    def jload(self, f: any):
        self.r = json.load(f)

    # Human readable formatted representation.
    def dumps(self) -> str:
        # return json.dumps(self.r, indent=4)
        return self._dumps(self.r, "")

    # Machine readable formatted representation.
    def getStringRepresentation(self, leaves: bool) -> str:
        lst = []
        self._getStringRepresentation(parent="", r=self.r, rtn=lst, leaves=leaves)
        return "\n".join(lst)

    def load(self, obj: any) -> None:
        self.ts = int(self.mzdatetime.timestamp())
        r = self._load("", obj)
        if self.r:
            self.r = self.merge(self.r, r, level=1)
        else:
            self.r = r

    def _load(self, label: str, obj: any) -> dict:
        if isinstance(obj, dict):
            d = {}
            for field in obj.keys():
                d[field] = self._load(field, obj[field])
            if d:
                return {"t": "dict", "ts": self.ts, "v": {"R": d, "O": {}}}
            else:
                return {"t": "dict", "ts": self.ts, "v": {"R": {}, "O": {}}}
        elif isinstance(obj, list):
            c = 0
            f = None
            for v in obj:
                c += 1
                o = self._load(label, v)
                if f is None:
                    f = o
                else:
                    f = self.merge(o1=f, o2=o, level=1)
            return {"t": "list", "ts": self.ts, "v": f}
        else:
            jtype = type(obj).__name__
            sobj = str(obj)
            t = MIsType.isType(label.lower(), jtype, sobj)
            if not t:
                t = jtype
            d = {"t": t, "ts": self.ts, "v": sobj}
            return d

    # Merge o2 into o1.
    # o2 and o1 may be re-used when creating the merge. clone o1 and o2 using copy.deepcopy() when there is
    # a need to retain their value.
    def merge(self, o1: dict, o2: dict, level: int = False) -> dict:
        t1 = o1["t"]
        t2 = o2["t"]
        if t1 == "switch":
            if t2 == "dict":
                return self.mergeSwitchDict(o1, o2, level=level)
            if t2 == "switch":
                return self.mergeSwitchSwitch(o1, o2, level=level)
            if t2 == "list":
                raise IncompatibleException("Merge switch and list")
            self.mergeSwitchValue(o1, o2, level=level)
        if t1 == "dict":
            if t2 == "switch":
                return self.mergeSwitchDict(o2, o1, level=level)
            if t2 == "dict":
                try:
                    return self.mergeDictDict(o1, o2, level=level)
                except IncompatibleException:
                    pass
                return self.mergeDictDictToSwitch(o1, o2, level=level)
            if t2 == "list":
                raise IncompatibleException("Merge dict and list")
            return self.mergeDictValue(o1, o2, level=level)
        if t1 == "list":
            if t2 == "list":
                return self.mergeListList(o1, o2, level=level)
            else:
                raise IncompatibleException("Merge list and " + t2)
        if t2 == "list":
            raise IncompatibleException("Merge " + t1 + " and list")
        if t2 == "switch":
            return self.mergeSwitchValue(o2, o1, level=level)
        if t2 == "dict":
            return self.mergeDictValue(o2, o1, level=level)
        return self.mergeValueValue(o1, o2, level=level)

    def mergeListList(self, l1: dict, l2: dict, level: int) -> dict:
        if self.debug:
            print(str(level) + " mergeListList")
            print(l1)
            print(l2)
        nl = {
            "t": "list", "ts": self.ts,
            "v": self.mergeValueValue(l1["v"], l2["v"], level=level)
        }
        if self.debug:
            print(str(level) + " mergeListList")
            print(nl)
        return nl

    def _caseToDict(self, c: dict) -> dict:
        d = {"t": "dict", "ts": self.ts, "v": {"R": c["R"], "O": c["O"]}}
        cs = c["S"]
        for f in cs:
            d["v"]["R"][f] = cs[f]
        return d

    @classmethod
    def _dictBackToCase(cls, d: dict, oldc: dict, mayReduceSelected: bool = False) -> dict:
        dvr, dvo = (d["v"]["R"], d["v"]["O"])
        os = oldc["S"]
        rtn = {"S": {}, "R": {}, "O": dvo}
        rs, rr, ro = (rtn["S"], rtn["R"], rtn["O"])
        for f in os:
            if f in dvr:
                rs[f] = dvr[f]
            elif not mayReduceSelected:
                raise IncompatibleException("Cannot reduce selected " + str(os) + " " + str(dvr))
        for f in dvr:
            if f not in rs:
                rr[f] = dvr[f]
        if not rs:
            raise IncompatibleException("Dict has no selected fields " + str(rtn) + " " + str(d))
        if not rr and not ro:
            raise IncompatibleException("Dict is all selected with no R/O fields " + str(rtn) + " " + str(d))
        return rtn

    def mergeSwitchDict(self, s: dict, d: dict, level: int) -> dict:
        if self.debug:
            print(str(level) + " mergeSwitchDict")
            print(s)
            print(d)
        ov = s["v"]
        rtn = {"t": "switch", "v": ov}
        rv = rtn["v"]
        # First, does dict fits into one of the cases.
        for i, c in enumerate(ov):
            try:
                oc = rv[i]
                rv[i] = self._dictBackToCase(self.mergeDictDict(self._caseToDict(c), d, level=level), c)
                if self.debug:
                    print(str(level) + " mergeSwitchDict")
                    print(d)
                    print(oc)
                    print(rv[i])
                return rtn
            except IncompatibleException:
                continue
        oc = ov[0]  # Any old case will do.
        ocs = oc["S"]
        # Second, generate a new case.
        try:
            nc = self._dictBackToCase(d, oc, mayReduceSelected=True)
        except IncompatibleException:
            raise
        ncs = nc["S"]
        # third, a new case with less selected fields and check if other cases can be merged.
        if len(ncs) < len(ocs):
            # 3.1, the smaller selector must be unique of all of the old cases.
            ocKeys = set()  # Set to test for uniqueness.
            for oc in ov:
                ocKey = ""
                ocs = oc["S"]
                for f, v in ocs.items():
                    if f in ncs:
                        ocKey += ";" + v.getStringRepresentation(leaves=True)
                if ocKey in ocKeys:  # Another case has the same key.
                    raise IncompatibleException("Dict missing selectors " + str(nc["S"]) + " " + str(oc["S"]))
                ocKeys.add(ocKey)
            # 3.2, reduce the selectors in all of the old cases.
            rv = rtn["v"] = []
            for oc in ov:
                c = {"S": {}, "R": copy.copy(oc["R"]), "O": oc["O"]}
                cs = c["S"]
                cr = c["R"]
                for f, v in oc["S"].items():
                    if f in ncs:
                        cs[f] = v
                    else:
                        cr[f] = v
                rv.append(c)
        rv.append(nc)
        return s

    def mergeSwitchSwitch(self, s1: dict, s2: dict, level: int) -> dict:
        if self.debug:
            print(str(level) + " mergeSwitchSwitch")
            print(s1)
            print(s2)
        rtn = s2
        for c in s1["v"]:
            rtn = self.mergeSwitchDict(rtn, self._caseToDict(c), level=level)
        if self.debug:
            print(str(level) + " mergeSwitchSwitch")
            print(rtn)
        return rtn

    def mergeDictDict(self, d1: dict, d2: dict, level: int) -> dict:
        if self.debug:
            print(str(level) + " mergeDictDict")
            print(d1)
            print(d2)
        r1, o1 = (d1["v"]["R"], d1["v"]["O"])
        r2, o2 = (d2["v"]["R"], d2["v"]["O"])
        newd = {"t": "dict", "ts": self.ts, "v": {"R": {}, "O": {}}}
        newr, newo = (newd["v"]["R"], newd["v"]["O"])
        for f1 in r1:
            if f1 in r2:
                newr[f1] = self.merge(r1[f1], r2[f1], level=level + 1)
            elif f1 in o2:
                newo[f1] = self.merge(r1[f1], o2[f1], level=level + 1)
            else:
                newo[f1] = r1[f1]
        for f1 in o1:
            if f1 in r2:
                newo[f1] = self.merge(o1[f1], r2[f1], level=level + 1)
            elif f1 in o2:
                newo[f1] = self.merge(o1[f1], o2[f1], level=level + 1)
            else:
                newo[f1] = o1[f1]
        for f2 in r2:
            if f2 not in r1 and f2 not in o1:
                newo[f2] = r2[f2]
        for f2 in o2:
            if f2 not in r1 and f2 not in o1:
                newo[f2] = o2[f2]
        if self.debug:
            print(str(level) + " mergeDictDict")
            print(newd)
        return newd

    # Merge two t="dict" to create t="switch".
    def mergeDictDictToSwitch(self, d1: dict, d2: dict, level: int) -> dict:
        if self.debug:
            print(str(level) + " mergeDictDictToSwitch")
            print(d1)
            print(d2)
        r1, o1 = (d1["v"]["R"], d1["v"]["O"])
        r2, o2 = (d2["v"]["R"], d2["v"]["O"])
        # First, find fields that are in both dict to select the cases.
        newS = {}
        for f1 in r1:
            if f1 in r2:
                try:
                    newS[f1] = self.merge(r1[f1], r2[f1], level=level + 1)
                except IncompatibleException:
                    pass
        if not newS:
            raise IncompatibleException("No common fields to select on")
        field_same_value = []
        for f in newS:
            if r1[f].getStringRepresentation(leaves=True) == r2[f].getStringRepresentation(leaves=True):
                field_same_value.append(f)
        for f in field_same_value:
            del newS[f]
        if not newS:
            raise IncompatibleException("Nothing to switch on. Common fields have the same values.")
        new = {"t": "switch", "ts": self.ts, "v": [
            {"S": {}, "R": {}, "O": o1},
            {"S": {}, "R": {}, "O": o2}
        ]}
        newv = new["v"]
        for f in newS:
            newv[0][f] = r1[f]
            newv[1][f] = r2[f]
        for f, v in r1.items():
            if f not in newS:
                newv[0]["R"][f] = v
        for f, v in r2.items():
            if f not in newS:
                newv[1]["R"][f] = v
        if self.debug:
            print(str(level) + " mergeDictDictToSwitch")
            print(new)
        return new

    def mergeDictValue(self, d: dict, v: dict, level: int) -> dict:
        raise IncompatibleException("mergeDictValue need field name to merge into dict " + str(d) + " value " + str(v))

    def mergeSwitchValue(self, s: dict, v: dict, level: int) -> dict:
        raise IncompatibleException("mergeSwitchValue need field name to merge into switch " + str(s) + " value " +
                                    str(v))

    # Generate a string representation of the structure in "r". For t="switch" it generated the same representation
    # as though it were a t="dict".
    @classmethod
    def _getStringRepresentation(cls, parent: str, r: dict, rtn: list, leaves: bool = True, values: bool = False):
        t = r["t"]
        v = r["v"]
        if not v:
            return
        if t == "switch":
            fields = {}
            for c in v:
                for xn, x in c.items():  # O, R, and S
                    if xn == "S":
                        xn = "R"
                    for fn, f in x.items():
                        fields[parent + "." + xn + "." + fn] = f
            for n, v in sorted(fields.items()):
                cls._getStringRepresentation(n, v, rtn=rtn, leaves=leaves)
        if t == "dict":
            for xn, x in sorted(v.items()):  # O and R
                for fn, f in sorted(x.items()):
                    cls._getStringRepresentation(parent + "." + xn + "." + fn, f, rtn=rtn, leaves=leaves)
        if t == "list":
            cls._getStringRepresentation(parent + ".list.", v, rtn=rtn, leaves=leaves)
        if not leaves:
            rtn.append(parent)
        # TODO: All types should have a comparable domain like num:int, num:float; and, host:ip, host:domain.
        # Then here the comparable part of the type is used.
        if t in ["int", "float", "num"]:
            t = "num"
        if ":" in t:
            t = t[:t.index(":")]
        if t in ["ip", "domain"]:
            t = "host"
        if values:
            rtn.append(parent + "." + t + "=" + v)
        rtn.append(parent + "." + t)

    # Walks the representation putting the structure and leaf values into the returned string.
    @classmethod
    def _dumps(cls, r: dict, indent: str) -> str:
        t = r["t"]
        v = r["v"]
        rtn = indent
        if "an" in t:
            rtn += "optional "
        if t == "list":
            rtn += "list:\n"
            indent += "    "
            return rtn + cls._dumps(v, indent)
        if t == "dict":
            rtn += "dict:\n"
            indent += "    "
            for f in v["R"]:
                rtn += indent + "'" + f + "'" + " (required):\n"
                rtn += cls._dumps(v["R"][f], indent + "    ")
            for f in v["O"]:
                rtn += indent + "'" + f + "'" + " (optional):\n"
                rtn += cls._dumps(v["O"][f], indent + "    ")
            return rtn
        if t == "switch":
            cases = {}
            for c in v:
                cs = c["S"]
                lst = []
                for f in cs:
                    cls._getStringRepresentation(parent=f + "=", r=cs[f], rtn=lst, leaves=True, values=True)
                cn = hashlib.shake_128(";".join(lst).encode()).hexdigest(1)
                cases[cn] = c
            rtn += "switch:\n"
            indent += "    "
            for n, c in sorted(cases.items()):
                rtn += indent + "case:" + n + "\n"
                rtn += indent + "S:" + "\n"
                for f in c["S"]:
                    rtn += indent + "    " + f + "\n"
                    rtn += cls._dumps(c["S"][f], indent + "    ")
                if c["R"]:
                    rtn += indent + "R:" + "\n"
                    for f in c["R"]:
                        rtn += indent + "    " + f + "\n"
                        rtn += cls._dumps(c["R"][f], indent + "    ")
                if c["O"]:
                    rtn += indent + "O:" + "\n"
                    for f in c["O"]:
                        rtn += indent + "    " + f + "\n"
                        rtn += cls._dumps(c["O"][f], indent + "    ")
            return rtn
        if "v2" in r:
            return rtn + t + "=[" + v + "," + r["v2"] + "]\n"
        return rtn + t + "=" + str(v) + "\n"

    # Returna list of fields that have aged off.
    def ageOff(self) -> list:
        rtn = []
        self.ts = self.mzdatetime.timestamp() - (self.ageoff_hour_limit * 60)
        if self._ageOff(parent="", r=self.r, rtn=rtn):
            self._getStringRepresentation(parent="", r=self.r, rtn=rtn, leaves=True, values=True)
            self.r = {}
        return rtn

    def _ageOff(self, parent: str, r: dict, rtn: list) -> bool:
        t = r["t"]
        v = r["v"]
        if t == "list":
            if r["ts"] < self.ts:
                return True
            return self._ageOff(parent=parent + ".list", r=v, rtn=rtn)
        if t == "dict":
            if r["ts"] < self.ts:
                return True
            lst = []
            for f in v["R"]:
                if self._ageOff(parent=parent + ".dict.R", r=v["R"][f], rtn=rtn):
                    lst.append(f)
            for f in lst:
                self._getStringRepresentation(parent=parent + ".dict.R", r=v["R"][f], rtn=rtn, leaves=True, values=True)
                del v["R"][f]
            lst = []
            for f in v["O"]:
                if self._ageOff(parent=parent + ".dict.O", r=v["O"][f], rtn=rtn):
                    lst.append(f)
            for f in lst:
                self._getStringRepresentation(parent=parent + ".dict.O", r=v["O"][f], rtn=rtn, leaves=True, values=True)
                del v["O"][f]
            return False
        if t == "switch":
            if r["ts"] < self.ts:
                return True
            for c in v:
                lst = []
                for f in c["S"]:
                    if self._ageOff(parent=parent + "switch.S", r=c["S"][f], rtn=rtn):
                        lst.append(f)
                for f in lst:
                    self._getStringRepresentation(parent=parent + "switch.S", r=c["S"][f], rtn=rtn,
                                                  leaves=True, values=True)
                    del c["S"][f]
                    raise Exception("Aging odd selected fields, must rebuild the switch")
                    # TODO: rebuild switch or should the case be deleted?
                if c["R"]:
                    lst = []
                    for f in c["R"]:
                        if self._ageOff(parent=parent + "switch.R", r=c["R"][f], rtn=rtn):
                            lst.append(f)
                    for f in lst:
                        self._getStringRepresentation(parent=parent + "switch.R", r=c["R"][f],
                                                      rtn=rtn, leaves=True, values=True)
                        del c["R"][f]
                if c["O"]:
                    lst = []
                    for f in c["O"]:
                        if self._ageOff(parent=parent + "switch.O", r=c["O"][f], rtn=rtn):
                            lst.append(f)
                    for f in lst:
                        self._getStringRepresentation(parent=parent + "switch.O", r=c["O"][f],
                                                      rtn=rtn, leaves=True, values=True)
                        del c["O"][f]
            return False
        return r["ts"] < self.ts

    @classmethod
    def mainType(cls, t: str) -> str:
        if ":" in t:
            return t[t.index(":") + 1:]
        return t

    def mergeValueValue(self, v1: dict, v2: dict, level: int) -> dict:
        if self.debug:
            print(str(level) + " mergeValueValue")
            print(v1)
            print(v2)
        newv = {}
        newv["t"] = t1 = v1["t"]
        t2 = v2["t"]
        if t1 != t2:
            newv["t"] = t1 = self.mainType(v1["t"])
            t2 = self.mainType(v2["t"])
            if t1 != t2:
                raise IncompatibleException("mergeValueValue " + t1 + " " + t2)
        newv["v"] = v1["v"]
        if "v2" in v1:
            newv["v2"] = v1["v2"]
        else:
            if newv["v"] != v1["v"]:
                if newv["v"] < v2["v"]:
                    newv["v2"] = v2["v"]
                else:
                    newv["v2"] = newv["v"]
                    newv["v"] = v2["v"]
            elif "v2" in v2 and v2["v2"] != newv["v"]:
                if newv["v"] < v2["v2"]:
                    newv["v2"] = v2["v2"]
                else:
                    newv["v2"] = newv["v"]
                    newv["v"] = v2["v2"]
        newv["an"] = ("an" in v2 or "an" in v1)
        if self.debug:
            print(str(level) + " mergeValueValue")
            print(newv)
        return newv

    @staticmethod
    def main():
        js = JSONSchemaDiscovery(debug=False)
        d = {"h": 1, "f": [2, 3, 4], "g": "a", "j": {"f": 5}}
        print("**load** " + str(d))
        js.load(d)
        d = {"h": 1, "f": [6, 7, 8], "g": "b"}
        print("**load**" + str(d))
        js.load(d)
        d = {"h": 9, "i": 10}
        print("**load**" + str(d))
        js.load(d)
        print(js.dumps())
        print(js.getStringRepresentation(leaves=True))
        js = JSONSchemaDiscovery(debug=False)
        js.load({"k": 1, "sk": 11, "f": "A"})
        print(js.r)
        js.load({"k": 2, "sk": 22, "f": "B"})
        print(js.r)
        # js.load({"k": 3, "sk": 31, "h": 9})
        # print(js.r)
        js.load({"k": 4, "i": 10})
        print(js.r)


if __name__ == "__main__":
    JSONSchemaDiscovery.main()
