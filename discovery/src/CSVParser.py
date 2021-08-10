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
# import xml.etree.ElementTree as ET
from discovery.src.parser import Parser
import csv


csv.register_dialect(
        'excel',
        delimiter=',',
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True
)
csv.register_dialect(
        'csv',
        delimiter=',',
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True
)
csv.register_dialect(
        'tsv',
        delimiter='\t',
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True
)


class CSVParser(Parser):
    def __init__(self, dialect: str):
        self.dialect = dialect

    def parse(self, file: str) -> list:
        j = self.toJSON({"filename": file})
        print(j)

    def toJSON(self, param: dict) -> any:
        # newline='' means blank lines are empty lines.
        with open(param["filename"], newline='') as csvfile:
            param["file"] = csvfile
            yield self.toJSON_FD(param)

    def toJSON_FD(self, param: dict) -> any:
        offset = param["offset"]
        with csv.reader(param["file"], dialect=self.dialect) as r:
            hdrs = next(r, None)
            for i, row in enumerate(r):
                if i >= offset:
                    drow = {}
                    for i, col in enumerate(row):
                        if col:
                            drow[hdrs[i]] = col
                    yield drow

    @staticmethod
    def main():
        p = CSVParser('csv')
        p.parse(file="test.csv")


if __name__ == "__main__":
    CSVParser.main()