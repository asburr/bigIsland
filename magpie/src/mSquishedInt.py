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
# mSquishedInt: encodes integer from base10 alphabet to an more condensed alphabet,
# so there are less characters to represent larger numbers.

class mSquishedInt():
    alphabet="0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ~!@#$%^&*()_+`-={}[]:;<>,.?/|"
    lenAlphabet=len(alphabet)
    alphabet_idx=[-1]*255
    for i, a in enumerate (alphabet):
        alphabet_idx[ord(a)] = i
    maxDigitLen=20
    alphabet_multi=[1]*maxDigitLen
    for i in range(1,maxDigitLen):
        alphabet_multi[i] = alphabet_multi[i-1] * lenAlphabet

    def __init__(self):
        self.rep=""

    def fromInt(self, i: int):
        self.rep=""
        d=i
        while True:
            (d,m) = divmod(d,self.lenAlphabet)
            self.rep += self.alphabet[m]
            if d == 0:
                break

    def __str__(self) -> str:
        return self.rep

    def toInt(self) -> int:
        retval = 0
        for i, a in enumerate(self.rep):
            retval += (self.alphabet_idx[ord(a)] * self.alphabet_multi[i])
        return retval

    @staticmethod
    def main():
        # Test the module.
        si = mSquishedInt()
        for i in [1,0,10,20,50,100,1728000]:
            si.fromInt(i)
            if si.toInt() != i:
                raise Exception("Error rep="+str(si)+" test="+str(i)+" val="+str(si.toInt()))

        
if __name__ == "__main__":
    mSquishedInt.main()