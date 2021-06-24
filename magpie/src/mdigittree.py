#!/usr/bin/env python3


class MDigitNode:
    
    def __init__(self):
        self.next = {}
        self.obj = None

    def add(self, obj: any, digits: str, i: int):
        if i == len(digits):
            self.obj = obj
            return
        c = digits[i]
        if c in self.next:
            self.next[c].add(obj, digits, i+1)
        else:
            n = MDigitNode()
            n.add(obj, digits, i+1)
            self.next[c] = n

    def find(self, digits: str, i: int) -> any:
        if i == len(digits):
            return self.obj
        c = digits[i]
        if c in self.next:
            obj = self.next[c].find(digits, i+1)
            if obj:
                return obj
        if MDigitTree.wildchar in self.next:
            return self.next[MDigitTree.wildchar].find(digits, i+1)


class MDigitTree:
    wildchar = "X"
    def __init__(self):
        self.head = MDigitNode()

    def add(self, digits: str, obj: any) -> None:
        self.head.add(obj, digits, 0)

    def find(self, digits: str) -> any:
        return self.head.find(digits, 0)