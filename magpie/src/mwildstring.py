#!/usr/bin/env python3
# WildString uses X or x as the wild char. Wild char matches any other
# char. For example "X" == "1".
import operator


class MWildString(str):
    
    def __new__(cls, content: str):
      return str.__new__(cls, content)
  
    def __cmp(self, other: 'MWildString') -> int:
        i1 = self.__iter__()
        i2 = other.__iter__()
        c1 = next(i1, None)
        c2 = next(i2, None)
        while c1 and (
            c1 == 'X' or c1 == 'x' or
            c2 == 'X' or c2 == 'x' or
            c1 == c2
        ):
            c1 = next(i1, None)
            c2 = next(i2, None)
        if not c1:
            if not c2:
                return 0
            return -1
        if not c2:
            return 1
        if c1 > c2:
            return 1
        if c2 > c1:
            return -1
        return 0
        
    def __eq__(self, other: 'MWildString') -> bool:
        return self.__cmp(other) == 0

    def __gt__(self, other: 'MWildString') -> bool:
        return self.__cmp(other) > 0

    def __ge__(self, other: 'MWildString') -> bool:
        return self.__cmp(other) >= 0

    def __lt__(self, other: 'MWildString') -> bool:
        return self.__cmp(other) < 0

    def __le__(self, other: 'MWildString') -> bool:
        return self.__cmp(other) <= 0

    @staticmethod
    def main():
        for s1, s2, op, e in [
            ("123", "1234", operator.eq, False),
            ("123", "123", operator.eq, True),
            ("1X3", "123", operator.eq, True),
            ("1x3", "123", operator.eq, True),
            ("123", "1234", operator.gt, False),
            ("1234", "XXXX", operator.ge, True),
            ("1234", "123", operator.lt, False),
            ("1234", "123X", operator.le, True)
        ]:
            if op(MWildString(s1),MWildString(s2)) != e:
                print("FAIL " + s1 + " " + s2 + " " + str(op))


if __name__ == "__main__":
    MWildString.main()


