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

from difflib import SequenceMatcher
import csv
import argparse


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a=a.lower(), b=b.lower()).ratio()


def getCSVReader(args, f:str):
        if args.QuoteSequence:
            return csv.reader(f, delimiter=args.delimiter,
                              quotechar=args.SequenceChar,
                              quoting=csv.QUOTE_MINIMAL)
        else:
            return csv.reader(f, delimiter=args.delimiter,
                              escapechar=args.EscapeChar)


def main():
    parser = argparse.ArgumentParser(description="Wi")
    parser.add_argument('master', help="Master csv has the desired titles")
    parser.add_argument('files', help="list of file names, coma separated")
    parser.add_argument('-m', '--mapping', help="Manual override of title mapping")
    parser.add_argument('-d', '--delimiter', help="Delimiter", default=",")
    parser.add_argument('-e', '--EscapeChar', default='\\')
    parser.add_argument('-s', '--SequenceChar', default='"')
    parser.add_argument('-q', '--QuoteSequence', action="store_true")
    parser.add_argument('-c', '--ShowScores', action="store_true")
    try:
        args = parser.parse_args()
    except:
        return
    with open(args.master, newline='') as f:
        masterTitles = next(getCSVReader(args, f))
    if args.mapping:
        with open(args.mapping, newline='') as f:
            mapping = {}
            mapped = set()
            try:
                for row in csv.reader(f, delimiter=","):
                    if len(row) != 3:
                        print("WARNING: " + args.mapping + " bad row in"
                              " mapping " + str(row))
                        print("Expecting: title, masterTitle, comment")
                        continue
                    newTitle, title, comment = row
                    if not title:  # Dont map this title
                        mapping[newTitle] = -1
                        continue
                    if newTitle in masterTitles:
                        print("WARNING: " + args.mapping + " title \"" +
                              newTitle + "\" is master title")
                        continue
                    if title not in masterTitles:
                        print("WARNING: " + args.mapping + " mapping using"
                              " title \"" + title +
                              "\" which is not a master title. " +
                              " hint: do you have the right master or mapping file?"
                              )
                        continue
                    if newTitle in mapping:
                        print("WARNING: " + args.mapping + " mapping has two"
                              " titles called \"" + newTitle + "\"")
                        continue
                    if title in mapped:
                        print("WARNING: mapping has already used title called \"" +
                              title + "\"")
                        continue
                    mapped.add(title)
                    i = masterTitles.index(title)
                    mapping[newTitle] = i  # newTitle = master idx
            except Exception as e:
                print("WARNING: bad mapping file " + e)
    for fn in args.files.split(","):
        with open(fn, newline='') as f:
            headings = next(getCSVReader(args, f))
            rowMap = []
            scores = []  # debugging.
            for newI, newTitle in enumerate(headings):
                if newTitle in mapping:
                    rowMap.append(mapping[newTitle])
                    scores.append(-2)
                else:
                    bestScore = 0.0
                    bestIndex = -1
                    for i, title in enumerate(masterTitles):
                        score = similar(newTitle, title)
                        if score > 0.75 and score > bestScore:
                            bestScore = score
                            bestIndex = i
                    rowMap.append(bestIndex)
                    scores.append(bestScore)
            mapped = ""
            for i, mi in enumerate(rowMap):
                mapped += headings[i]
                if mi != -1:
                    mapped += "=>" + masterTitles[mi]
                    if args.ShowScores:
                        mapped += " (" + str(int(scores[i]*100)) + "%)"
                else:
                    mapped += "=>?"
                mapped += ", "
            print(mapped)
               

if __name__ == "__main__":
    main()