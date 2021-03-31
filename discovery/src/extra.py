#!/usr/bin/env python3
# Extra functionality to compare the first level of fields in two dict, and return value between 0 and 1
# to indicate the number of fields that have identical structure.

# Comparing two structures of t="dict" or t="switch".
# Counting the number of fields with comparable structures.
# Returning the ratio of comparable fields.
def cmpDictDict(self, d1: dict, d2: dict) -> float:
    h1 = self.getHashDictForCmp(d1)
    h2 = self.getHashDictForCmp(d2)
    s1 = set(h1.keys())
    s2 = set(h2.keys())
    cnt = 0
    tot = 0
    for f in s1:
        tot += 1
        if f in s2:
            if h1[f] == h2[f]:
                cnt += 1
    for f in s2:
        if f not in s1:
            tot += 1
    if not tot:
        return 1.0
    return cnt / tot


# Works with t="dict" or t="switch". Generates a string representation for each field's value.
# Returns a dictionary of field to the string representation.
def getHashDictForCmp(self, r: dict) -> dict:
    t = r["t"]
    v = r["v"]
    if not v:
        return {}
    if t == "switch":
        d = {}
        fields = {}
        for cn, c in v.items():  # Cases
            for xn, x in c.items():  # O, R, and S
                if xn == "S":
                    xn = "R"
                for fn, f in x.items():
                    fields[xn + "." + fn] = (fn, f)
        for n, v in sorted(fields.items()):
            fn, f = v
            d[fn] = self._getStringRepresentation(parent=n, r=f)
        return d
    elif t == "dict":
        d = {}
        for xn, x in sorted(v.items()):  # O and R
            for fn, f in sorted(x.items()):
                d[fn] = self._getStringRepresentation(parent=xn + "." + fn, r=f)
        return d
    else:
        raise Exception("Expecting switch of dict, and got " + t)
