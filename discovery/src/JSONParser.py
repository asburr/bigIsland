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
import re


class JSONStats:
    """
    stats = {
        "<fieldname>": {
            "c": <occ>,
            "e": <example>,
            "dt": {
                "<datatype>": {
                    "c": <occ>,
                    "e": <example>
               }
            },
            "v": {
                "<value>": {
                    "c": <occ>
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
        self.values = set()

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
                    "c": 0,
                    "e": obj,
                    "dt": {},
                    "v": {}
                }
            d = self.stats[label]
            d["c"] += 1
            t = MIsType.isType(label, type(obj), str(obj))
            if t is not None:
                dt = d["dt"]
                if t not in dt:
                    dt[t] = {
                        "c": 0,
                        "e": obj
                    }
                dt = dt[t]
                dt["c"] += 1
                if label in self.values:
                    dv = d["v"]
                    if obj not in dv:
                        dv[obj] = {"c": 0}
                    d = dv[obj]
                    d["c"] += 1

    def merge(self, other: "JSONStats") -> None:
        for k, v in other.stats.items():
            if k not in self.stats:
                self.stats[k] = v
            else:
                d = self.stats[k]
                d["c"] += v["c"]
                dt = d["dt"]
                for t, tv in v["dt"].items():
                    if t not in dt:
                        dt[t] = tv
                    else:
                        dt[t]["c"] += tv["c"]
                dv = d["v"]
                for v, vv in v["v"].items():
                    if v not in dv:
                        dv[v] = vv
                    else:
                        dv["c"] += vv["c"]

    def addValues(self, valueFieldNames: list) -> None:
        for valueFieldName in valueFieldNames:
            self.values.add(valueFieldName)


class JSONParser(Parser):
    def __init__(self):
        self.stats = JSONStats()
        self.j = {}
        self.valueLabels = {}
        self.truncs = {}
        self.parent = None
        self.valueLabelStates = {
            "Rguard": "Rreplace", "Rreplace": "Rvalue", "Rvalue": "end",
            "Nguard": "Nvalue", "Nvalue": "end",
            "nguard": "end",
        }
        self.valueLabelNodes = []
        self.ignores = set()
        self.nests = set()

    def parse(self, file: str) -> list:
        self.j = self.toJSON(file)
        print(self.j)
        self.stats.gatherStats("", self.j)
        print(self.stats.stats)
        
    # A JSON dict with duplicate keys is loaded into a list of values.
    @staticmethod
    def dict_duplicate_keys_to_list(ordered_pairs):
        d = {}
        for k, v in ordered_pairs:
            if k in d:
                if type(d[k]) is list:
                    d[k].append(v)
                else:
                    d[k] = [d[k],v]
            else:
               d[k] = v
        return d

    def toJSON(self, file: str) -> any:
        with open(file, "r") as f:
            self.j = json.load(f,
                               object_pairs_hook=self.dict_duplicate_keys_to_list)
            self.renameLabels = []
            self.j = self._walk(self.j)
            return self.j

    def getStats(self) -> JSONStats:
        self.stats.gatherStats("", self.j)
        return self.stats

    # Add a label whose values will be tracked by the stats.
    def addValues(self, valueFieldNames: list) -> None:
        self.stats.addValues(valueFieldNames)

    # To address generic label names where the real label is in a value.
    # For example, wireshark decodes json using labels: json, json.key, and
    # json.member. The real label name is found in the value of json.key.
    # In this case, the valueLabel cfg is ["json", "json.key", "json.member"].
    # Which says, within the nested structure of tag “json”, replace the nearest
    # label json.member with the value found in the nested json.key.
    # i.e.
    #  { “json”: {“json.object”: {"json.member": {"json.value.number": 123,"json.key": "v2"}}}}
    # Becomes,
    #  { “json”: {“json.object”: {"v2": {"json.value.number": 123}}}}

    # Add the initial state (guard) for the value labels.
    def addValueLabels(self, valueLabels: list) -> None:
        for valueLabel in valueLabels:
            if True:  # Sanity checks.
                pstate = None
                for state in valueLabel.keys():
                    if pstate:
                        nstate = self.valueLabelStates[pstate]
                        if state != nstate:
                            raise Exception("Unknown trans " + pstate + " to "+
                                            nstate + " in valuelabel " +
                                            str(valueLabel))
                    pstate = state
                    if pstate not in self.valueLabelStates:
                        raise Exception("Unknown state " + pstate + " in "
                                        "valuelabel " + str(valueLabel))
            if "Rguard" in valueLabel:
                state = "Rguard"
            elif "Nguard" in valueLabel:
                state = "Nguard"
            elif "nguard" in valueLabel:
                state = "nguard"
            else:
                raise Exception("Unknown state in valuelabel " +
                                str(valueLabel))
            label = valueLabel[state]
            if label not in self.valueLabels:
                self.valueLabels[label] = []
            n = {
                "labels": valueLabel,
                "state": state,
                "parent": None,
                "replaceField": "",
                "renameLabels": [],
                "nestedLabels": []
            }
            n["guardNode"] = n
            self.valueLabels[label].append(n)

    def addIgnore(self, ignores: list) -> None:
        for field in ignores:
            self.ignores.add(field)

    def addNest(self, nests: list) -> None:
        for field in nests:
            self.nests.add(field)

    def addTrunc(self, truncs: dict) -> None:
        for field, value in truncs.items():
            self.truncs[field] = value

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

    def _wiresharkDict(self, obj: dict) -> any:
        lst = list(obj.keys())
        # Move wireshark labels that are value summaries.
        wiresharkSummaryFields = True
        delField = set()
        for field in lst:
            # Wireshark summaries contain ": " in
            # the field name that is a dictionary.
            if (
                ": " not in field
                or not isinstance(obj[field], dict)
            ):
                wiresharkSummaryFields = False
                break
        if wiresharkSummaryFields:
            # Convert dict to list.
            l = []
            for field in lst:
                v = obj[field]
                v["__ws_summary"] = field
                l.append(v)
            return l
        # Remove the wireshark hexdumps.
        for field in lst:
            if (
                    field.endswith("data") or
                    field.endswith("padding") or
                    field.endswith("unused")
                ):
                if self.ishexdump(obj[field]):
                    delField.add(field)
        if delField:
            for field in delField:
                del obj[field]
        return obj

    def decodehttpparam(self, obj: dict, field: str, v: str, ) -> None:
        try:
            pn, pv = v.split(":")
        except:
            return
        l = pv.split(";")
        if pn not in obj:
            obj[pn] = {}
        obj = obj[pn]
        if "value" not in obj:
            obj["value"] = l[0].strip()
        for p in l[1:]:
            try:
                pn, pv = p.split("=")
            except:
                continue
            pn = pn.replace("-","_").strip().lower()
            if pn not in obj:
                obj[pn] = pv.strip()

    def decodehttpparams(self, obj: dict) -> None:
        for field in list(obj.keys()):
            if field in ["http.response.line", "http.request.line"]:
                v = obj[field]
                del obj[field]
                if isinstance(v, list):
                    for p in v:
                        if isinstance(p, str):
                            self.decodehttpparam(obj, field, p)
                        else:
                            raise Exception("http param " + field + " is " +
                                            str(type(p)))
                elif isinstance(v, str):
                    self.decodehttpparam(obj, field, v)
                else:
                    raise Exception("http param " + field + " is " +
                                    str(type(v)))

    def _walk(self, obj: any) -> any:
        if isinstance(obj, dict):
            obj = self._wiresharkDict(obj)
        if isinstance(obj, dict):
            fields =  list(obj.keys())
            delField = []
            for field in fields:
                if field in self.ignores:
                    delField.append(field)
                    continue
                if field == "http":
                    self.decodehttpparams(obj[field])
                if field in self.truncs:
                    v = obj[field]
                    if not isinstance(v, str):
                        raise Exception("trunc field " + field + " is " +
                                        str(type(v)))
                    t = self.truncs[field]
                    if t in v:
                        obj[field] = v[:v.index(t)+len(t)]
                if field in self.nests:
                    parentobj = obj[field]
                    nxtfields = list(parentobj.keys())
                    pobj = parentobj[nxtfields[0]]
                    for nxtfield in nxtfields[1:]:
                        nxtobj = parentobj[nxtfield]
                        del parentobj[nxtfield]
                        # nxtfield = field + "_" + nxtfield
                        if not isinstance(nxtobj, dict):
                            raise Exception(
                                "nesting field is not a dict " + nxtfield +
                                " " + str(type(nxtobj))
                                )
                        if nxtfield in pobj:
                            raise Exception(
                                "nesting field " + nxtfield + " exists in " +
                                str(pobj))
                        pobj[nxtfield] = nxtobj
                        pobj = nxtobj
                if field in self.valueLabels:
                    # Use recently added node against this label.
                    n = self.valueLabels[field][-1]
                    state = n["state"]
                    nextState = self.valueLabelStates[state]
                    if nextState == "end":
                        parent = n["parent"]
                        if parent:
                            if (isinstance(obj[field], dict) or
                                isinstance(obj[field], list)
                                ):
                                raise Exception(
                                    "valueField " + str(n["labels"]) +
                                    " value is composite type:"+
                                    str(type(obj[field]))
                                    )
                            # Problem, field is changed in nested iteration
                            # here it's added back!
                            obj[field] = self._walk(obj[field])
                            oldfield = n["parentField"]
                            newfield = obj[field]
                            if newfield in parent:
                                raise Exception(newfield + " exists in " +
                                                str(parent))
                            if state == "Rvalue":  # Replace
                                n["guardNode"]["renameLabels"].append(
                                        [parent, oldfield, newfield])
                            elif state == "Nvalue":  # Nest structures
                                n["guardNode"]["nestedLabels"].append(
                                        [parent, oldfield, newfield])
                            else:
                                raise Exception("unexpected state " + n["state"])
                            # Ignore multiple nested labels.
                            n["parent"] = None
                        else:  # Second label is ignored.
                            obj[field] = self._walk(obj[field])
                    else:
                        nextLabel = n["labels"][nextState]
                        if nextLabel not in self.valueLabels:
                            self.valueLabels[nextLabel] = []
                        self.valueLabels[nextLabel].append({
                                "labels": n["labels"],
                                "state": nextState,
                                "parentField": field,
                                "parent": obj,
                                "guardNode": n["guardNode"]
                        })
                        obj[field] = self._walk(obj[field])
                        # Remove the new node after processing the sub-tree.
                        nextn = self.valueLabels[nextLabel].pop()
                        if not len(self.valueLabels[field]):
                            del self.valueLabels[field]
                        if nextn["state"] == "end" and nextn["parent"] != None:
                            raise Exception(
                                    "Error in valueField " +
                                    str(nextn["labels"]) +
                                    " did not match, no replacement done!"
                            )
                    # Here is the most effient save place to change the
                    # fields in sub-tree. Sub-tree cannot be changed at
                    # state == "end" that's within a loop over the
                    # sub-tree's fields that need to change.
                    if n["state"] == "Rguard":
                        for parent, oldfield, newfield in n["renameLabels"]:
                            parent[newfield] = parent[oldfield]
                            del parent[oldfield]
                    if n["state"] == "Nguard":
                        for parent, oldfield, newfield in n["nestedLabels"]:
                            temp = parent[oldfield]
                            parent[oldfield] = {newfield: temp}
                else:
                    obj[field] = self._walk(obj[field])
            for field in delField:
                del obj[field]
            return obj
        elif isinstance(obj, list):
            return [self._walk(v) for v in obj]
        else:
            return obj

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="JSON Parser")
        parser.add_argument('input', help="input file")
        parser.add_argument('-o', '--output', help="expected output file")
        parser.add_argument('-v', '--values', help="name of file with a list of fields whose values to track")
        parser.add_argument('-l', '--valuelabels', help="name of file with a list of <blocklabel>,<keylabel>,<replacelabel>")
        parser.add_argument('-i', '--ignore', help="name of file with a list of fields to ignore")
        parser.add_argument('-n', '--nest', help="name of file with list of fields to nest")
        parser.add_argument('-t', '--trunc', help="name of file with list of fields, value to be truncated beyond value")
        args = parser.parse_args()
        p = JSONParser()
        p2 = JSONParser()
        if args.values:
            with open(args.values, "r") as f:
                p.addValues(json.load(f))
        if args.valuelabels:
            with open(args.valuelabels, "r") as f:
                p.addValueLabels(json.load(f))
        if args.ignore:
            with open(args.ignore, "r") as f:
                p.addIgnore(json.load(f))
        if args.nest:
            with open(args.nest, "r") as f:
                p.addNest(json.load(f))
        if args.trunc:
            with open(args.trunc, "r") as f:
                p.addTrunc(json.load(f))
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
        if False:
            print(p.getStats().stats)
            p2.stats.merge(p.stats)
            print(p2.stats.stats)


if __name__ == "__main__":
    JSONParser.main()
