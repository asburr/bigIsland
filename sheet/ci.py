#!/usr/bin/env python3
# CLI for the sheet.
import sys
import os
import json
import re
import pandas as pd
from sheet.input import Input
from cmd2 import Cmd, Cmd2ArgumentParser, with_argparser
import traceback
try:
    import sheet.inputs
except ModuleNotFoundError:
    print("No directory(inputs)...pls run Sheet from the bigIsland"
          "directory")
    sys.exit(1)
except NameError or SyntaxError:
    print("There are syntax errors in the inputs plugins, pls debug")
    traceback.print_exc()
    sys.exit(1)


class Result():
    def __init__(self, df: pd.DataFrame, qn: str, p: dict):
        self.df = df
        self.qn = qn
        self.params = p


class Ci(Cmd):
    # default_to_shell = True
    def __init__(self):
        super().__init__(use_ipython=True)
        self.context = {"debug": False}
        # noinspection PyBroadException
        try:
            with open(".ci_context.json", "r") as fp:
                self.context = json.load(fp)
        except Exception:
            pass
        self.scratchPad = {}
        self.savedResults = []
        self.query = {}
        for inp in sheet.inputs.ALL:
            error = inp.checkUsage(inp.usage())
            if error:
                print("Error in module " + inp.name() + ":\n" + error)
                exit(1)
            if inp.name():
                self.query[inp.name()] = inp
        self.shortQuery = {}
        self.shortMapping = {}
        for n in self.query.keys():
            for i in range(len(n)):
                shortname = n[0:i]
                if shortname not in self.shortQuery:
                    self.shortMapping[n] = shortname
                    self.shortQuery[shortname] = self.query[n]
                    break

    queryparser = Cmd2ArgumentParser()
    queryparser.add_argument('query_name', nargs="?", type=str, const="",
                             help='Run the named query and generate results')

    def _getParams(self, q: Input) -> dict:
        params = q.usage()["params"]
        for param, ptype in params.items():
            if param not in self.context:
                default = None
                prompt = "Enter " + param + ":"
            else:
                default = self.context[param]
                prompt = "Enter " + param + "(" + str(default) + "):"
            if ptype == "password":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param] = input(prompt)
                if not self.context[param]:
                    self.context[param] = default
            elif ptype == "pathi":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param] = input(prompt)
                if not self.context[param]:
                    self.context[param] = default
                while not os.path.exists(self.context[param]):
                    print("Cannot find file " + self.context[param])
                    # self.context[param] = self.read_input(prompt=prompt)
                    self.context[param] = input(prompt)
                    if not self.context[param]:
                        self.context[param] = default
            elif ptype == "path":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param] = input(prompt)
                if not self.context[param]:
                    self.context[param] = default
                while not os.path.exists(os.path.dirname(self.context[param])):
                    print("Cannot find directory " +
                          os.path.dirname(self.context[param]))
                    # self.context[param] = self.read_input(prompt=prompt)
                    self.context[param] = input(prompt)
                    if not self.context[param]:
                        self.context[param] = default
            elif ptype == "str":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param] = input(prompt)
                if not self.context[param]:
                    self.context[param] = default
            elif ptype == "bool":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param] = input(prompt)
                if not self.context[param]:
                    self.context[param] = default
        pl = {}
        for param in params.keys():
            pl[param] = self.context[param]
        with open(".ci_context.json", "w") as fp:
            json.dump(self.context, fp)
        return param

    @with_argparser(queryparser)
    def do_q(self, args):
        """Query"""
        try:
            if args.query_name in self.query:
                q = self.query[args.query_name]
            elif args.query_name in self.shortQuery:
                q = self.shortQuery[args.query_name]
            else:
                if args.query_name:
                    print("The following queries match " +
                          args.query_name + ":")
                    pn = args.query_name.lower()
                    for n in self.query.keys():
                        if pn in n.lower():
                            print(n + "(" + self.shortMapping[n] + ")")
                else:
                    print("The following queries are supported:")
                    for n in self.query.keys():
                        print(n + "(" + self.shortMapping[n] + ")")
                return
            params = self._getParams(q)
            columns = list(q.usage()["return"].keys())
            if columns:
                result = pd.DataFrame(columns=columns)
                for r in q.exec(params=self.context,
                                scratchPad=self.scratchPad):
                    row = len(result)
                    for k in columns:
                        result.at[row, k] = r[k]
                print(str(len(result)) + " results")
                if len(result):
                    self.savedResults.append(
                        Result(df=result, qn=q.name(), p=params))
            else:
                q.exec(params=self.context, scratchPad=self.scratchPad)
        except Exception:
            traceback.print_exc()
            return 0

    showparser = Cmd2ArgumentParser()
    showparser.add_argument(
        '-R' '--remove_row', type=str, default="",
        help='Condition(s) to remove the row i.e. a == 1 and b == 2')
    showparser.add_argument(
        '-r' '--include_row', type=str, default="",
        help='Condition(s) to include the row i.e. a < 1 and b > 3')
    showparser.add_argument(
        '-C' '--remove_column', type=str, default="",
        help='Coma separated patterns identifying cols to remove i.e. a_*,b_*')
    showparser.add_argument(
        '-c' '--include_column', type=str, default="",
        help='Coma separated patterns identifying cols to include i.e. *X')
    # -g/-s removes the cols that are not grouped-by and not summed.
    showparser.add_argument(
        '-g' '--group_by_column', type=str, default="",
        help='Coma separate patterns identifying cols to group-by for (-s)')
    showparser.add_argument(
        '-s' '--sum_column', type=str, default="",
        help='Coma separate patterns identifying cols to sum for (-g)')

    def do_s(self, args):
        """Show recent result"""
        if not self.savedResults:
            print("No results")
        else:
            result = self.savedResults[-1]
            columns = result.df.columns.tolist()
            df = result.df.copy()
            if args.remove_row:
                try:
                    df.query(expr=args.remove_row, inplace=True)
                except Exception as e:
                    print("Error in " + args.remove_row + " " + str(e))
                    return
            if args.include_row:
                try:
                    df.query(expr=args.include_row, inplace=True)
                except Exception as e:
                    print("Error in " + args.include_row + " " + str(e))
                    return
            if args.remove_column:
                try:
                    for pattern in args.remove_column.split(","):
                        pat = re.compile(pattern)
                        for col in columns:
                            if pat.match(col):
                                df.drop(columns=col, inplace=True)
                except Exception as e:
                    print("Error in " + args.remove_column + " " + str(e))
                    return
            if args.include_column:
                try:
                    ic = set()
                    for pattern in args.include_column.split(","):
                        pat = re.compile(pattern)
                        for col in columns:
                            if pat.match(col):
                                ic.add(col)
                    for col in columns:
                        if col not in ic:
                            df.drop(columns=col, inplace=True)
                except Exception as e:
                    print("Error in " + args.include_column + " " + str(e))
                    return
            if args.group_by_column and args.sum_column:
                try:
                    gb = set()
                    for pattern in args.group_by_column.split(","):
                        pat = re.compile(pattern)
                        for col in columns:
                            if pat.match(col):
                                gb.add(col)
                    if not gb:
                        print("Error in -g " +
                              args.group_by_column + " -s " +
                              " not columns selected")
                        return
                    sc = set()
                    for pattern in args.sum_column.split(","):
                        pat = re.compile(pattern)
                        for col in columns:
                            if pat.match(col):
                                sc.add(col)
                    if not sc:
                        print("Error in -s " +
                              args.sum_column + " -s " +
                              " not columns selected")
                        return
                    for col in columns:
                        if col in gb and col in sc:
                            print("Error in -g " +
                                  args.group_by_column + " -s " +
                                  args.sum_column + " " +
                                  " select the same col " + col)
                            return
                except Exception as e:
                    print("Error in " +
                          args.group_by_column + " " +
                          args.sum_column + " " +
                          str(e))
                    return
            
            filt = {"remove_row": args.remove_row,
                    "include_row": args.include_row,
                    "remove_column": args.remove_column,
                    "include_column": args.include_column,
                    "group_by_column": args.group_by_column,
                    "sum_column": args.sum_column}
            self.savedResults.append(
                Result(df=result, qn="_filter_", p=filt))
            print()

    def do_d(self, args):
        """Delete recent result"""
        if not self.savedResults:
            print("No results")
        else:
            del self.savedResults[-1]

    @staticmethod
    def main():
        sys.exit(Ci().cmdloop())


if __name__ == "__main__":
    sys.exit(Ci().cmdloop())
