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


class MDigitsNode:
    
    def __init__(self):
        # <digit length>: ([<wildindex>], dict)
        self.dicts = {}

    def add(self, obj: any, digits: str, i: int):
        l = len(digits)
        if l not in self.dicts:
            self.dicts[l] = ([], {})
        wilds, d = self.dicts[l]
        i = 0
        newwild = []
        while MDigitTree.wildchar in digits[i:]:
            i = digits.index(MDigitTree.wildchar, i)
            newwild.append(i)
            i += 1
        if newwild not in wilds:
            wilds.append(newwild)
        if digits in d:
            raise Exception("Duplicate key " + digits)
        d[digits] = obj

    def find(self, digits: str, i: int) -> any:
        l = len(digits)
        d = self.dicts.get(l)
        if not d:
            return None
        wilds, d = d
        obj = d.get(digits)
        if obj:
            return obj
        for wild in wilds:
            l = list(digits)
            for idx in wild:
                l[idx] = MDigitTree.wildchar
            wilddigits = "".join(l)
            obj = d.get(wilddigits)
            if obj:
                return obj

class MDigitTree:
    wildchar = "X"
    def __init__(self):
        self.head = MDigitsNode()

    def add(self, digits: str, obj: any) -> None:
        self.head.add(obj, digits, 0)

    def find(self, digits: str) -> any:
        return self.head.find(digits, 0)
    
    # String formatting is used by print() and str().
    def __str__(self) -> str:
        return str(self.head.dicts)