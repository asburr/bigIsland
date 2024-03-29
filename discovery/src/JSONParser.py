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

# The standard JSON parser reads the whole file into memeory. There is not
# enough memory for huge files or, streams of json which never end. The
# iterative JSON library is used instead, it parses chunks.

import ijson  # Iterative json.
import json
import argparse
from discovery.src.parser import Parser
from magpie.src.mistype import MIsType


# Create a schema for a python data structure that can be a flat dict,
# or nexted lists and dicts.
# while building the schema, the type of values is determined and
# inserted into the schema
# {"host": "www.hello.world.com"}
# Generates the schema:
# {"host": {'c': 1, 'e': 123, 'dt': {'': {'c': 1, 'e': 123}}, 'v': {}}
# The format's full definition:
#        "<fieldname>": {
#            "c": <occ counter>,
#            "e": <example>,
#            "dt": {
#                "<datatype>": {
#                    "c": <occ counter>,
#                    "e": <example>
#               }
#            },
#            "v": {
#                "<value>": {
#                    "c": <occ counter>
#                }
#            }
#        }
# Note that "v" is populated when values are being tracked by the schema,
# this is activated by calls to addValues(), otherwise it's always empty.
class JSONSchema:
    def __init__(self):
        self.stats = {}
        self.values = set()

    def gather(self, label: str, obj: any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.gather(label+" "+k, v)
        elif isinstance(obj, list):
            for v in obj:
                self.gather(label+" __repeated_item__", v)
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
            t, subfields = MIsType.isType(label, type(obj), str(obj))
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

    def merge(self, other: "JSONSchema") -> None:
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

    def __str__(self):
        s="Stats:\n"
        for k, v in self.stats.items():
            s+=k+" = "+str(v)+"\n"
        return s


class JSONParser(Parser):
    def __init__(self):
        self.stats = JSONSchema()
        self.j = None
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
        self.eventHandlers={
            "start_map": self.__start_map,
            "end_map": self.__end_map,
            "map_key": self.__map_key,
            "start_array": self.__start_array,
            "end_array": self.__end_array,
            "string": self.__value,
            "number": self.__value
        }
        self.stack = []
        self.c = None
        self.key = None
        self.r = None
        self.debug = False

    def __start_map(self, value: str):
        c = {}
        if self.c is not None:
            self.__value(c)
            self.r = None
            self.stack.append(self.c)
        self.c = c

    def __end_map(self, value: str):
        if len(self.stack) > 1:
            self.c = self.stack.pop()
        else:
            self.r = self.c
            self.c = None

    def __map_key(self, value: str):
        self.key = value

    def __start_array(self, value: str):
        c = []
        if self.c is not None:
            self.__value(c)
            self.r = None
            self.stack.append(self.c)
        self.c = c

    def __end_array(self, value: str):
        if len(self.stack) == 1:
            self.r = self.c
            self.c = None
        else:
            self.c = self.stack.pop()

    def __value(self, value: any):
        if type(self.c) == dict:
            if self.key in self.c:
                if type(self.c[self.key]) != list:
                    self.c[self.key] = [self.c[self.key]]
                self.c[self.key].append(value)
            else:
                self.c[self.key] = value
            self.key = None
        elif type(self.c) == list:
            if len(self.stack) == 1:
                self.r = value
            else:
                self.c.append(value)
        else:
            self.r = value

    # Read objects from a file into a list, return list.
    def parse(self, file: str) -> list:
        r = []
        for j in self.toJSON({"filename": file}):
            self.stats.gather("", j)
            r.append(j)
        return r

    # Read objects from a file, yield each object.
    def toJSON(self, param: dict) -> any:
        self.c = self.j = None
        self.key = None
        self.r = None
        with open(param["filename"], "r") as f:
            param["file"] = f
            for j in self.toJSON_FD(param):
                yield j
    
    # Read objects from file descriptor, yield each object.
    def toJSON_FD(self, param: dict) -> any:
        p = ijson.basic_parse(param["file"])
        offset = param["offset"]
        for i, (event, value) in enumerate(p):
            if i < offset:
                continue
            if self.debug:
                print(">" + str(event) + " " + str(value) + " " + str(self.c))
            self.eventHandlers[event](value)
            if self.debug:
                print("<" + str(event) + " " + str(value) + " " + str(self.c))
                if len(self.stack) > 0:
                    print(" STACK " + str(len(self.stack)) + " " +
                          str(self.stack[-1]))
            if self.r:
                if self.debug:
                    print("YIELD "+ str(self.r))
                self.renameLabels = []
                self.r = self._walk(self.r)
                self.stats.gather("", self.r)
                yield self.r
                self.r = None
        if self.c:
            yield self.c
            self.c = None

    def getStats(self) -> JSONSchema:
        self.stats.gather("", self.j)
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

    # Compare two structure, return True when differences.
    def diff(self, label: str, obj: any, obj2: any) -> bool:
        if type(obj) != type(obj2):
            print("*** Different types " + label + " " + type(obj) + " " + type(obj2))
            return False
        if isinstance(obj, dict):
            fields =  list(obj.keys())
            fields2 = list(obj2.keys())
            if fields != fields2:
                print("*** Different keys in dictionary " + label)
                print(fields)
                print(fields2)
                return False
            for field in fields:
                if not self.diff(label + "." + field, obj[field], obj2[field]):
                    return False
        elif isinstance(obj, list):
            l = len(obj)
            l2 = len(obj2)
            if l != l2:
                print(label)
                print("Lists are different sizes " + str(l) + " " + str(l2))
                return False
            for i, v in enumerate(obj):
                if not self.diff(label + ".lst." + str(i), v, obj2[i]):
                    return False
        else:
            if obj != obj2:
                print(label)
                print("Objs are different " + str(obj) + " " + str(obj2))
                return False
        return True

    # Walk an object and clean it up. Remove fields that are
    # to be ignored. Decode http fields. Truncs fields.
    # Value labels.
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
        parser.add_argument('-d', '--debug', help="activate debugging", action="store_true")
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
        j = []
        p.debug = args.debug
        for d in p.toJSON(param={"filename": args.input, "offset": 0}):
            j.append(d)
        if args.output:
            with open(args.output, "r") as f:
                oj = json.load(f)
                if oj != j:
                    print("ERROR : mismatch output")
                    p.diff("",j,oj)
                else:
                    print("PASS")
        else:
            print(j)
        print(p.stats)
        if False:
            print(p.getStats().stats)
            p2.stats.merge(p.stats)
            print(p2.stats.stats)


if __name__ == "__main__":
    JSONParser.main()
