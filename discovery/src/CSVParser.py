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
import xml.etree.ElementTree as ET
from discovery.src.parser import Parser
import csv


csv.register_dialect(
        'excel',
        delimiter=',',
        quoting=csv.QUOTE_MINIMAL,
        doublequote=True
)


class CSVParser(Parser):
    def __init__(self, dialect: str):
        self.dialect = dialect

    def parse(self, file: str) -> list:
        j = self.toJSON(file)
        print(j)

    def toJSON(self, file: str) -> any:
        import csv
        # newline='' means blank lines are empty lines.
        with open(file, newline='') as csvfile:
            r = csv.reader(csvfile, dialect=self.dialect)
            hdrs = next(r, None)
            sheet = []
            for row in r:
                drow = {}
                for i, col in enumerate(row):
                    if col:
                        drow[hdrs[i]] = col
                sheet.append(drow)
        return sheet

    @staticmethod
    def main():
        p = CSVParser('excel')
        p.parse(file="test.csv")


if __name__ == "__main__":
    CSVParser.main()