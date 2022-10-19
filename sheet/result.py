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
import pandas as pd


class Result():
    def __init__(self, df: pd.DataFrame, qn: str, p: dict):
        self.df = df
        self.qn = qn
        self.params = p
        
    def print(self):
        if self.qn == "_filter":
            print("Filter")
        else:
            print("Query: " + self.qn)
        print("Params:")
        for k, v in self.params.items():
            print("  " + k + "=" + str(v))
        print("result count: " + str(len(self.df)))