#!/usr/bin/env python3
# CLI for the sheet.
import sys
import os
import json
import re
import pandas as pd
# from sheet.input import Input
import argparse
from cmd2 import Cmd, with_argparser
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
        
    def print(self):
        if self.qn == "_filter":
            print("Filter")
        else:
            print("Query: " + self.qn)
        print("Params:")
        for k, v in self.params.items():
            print("  " + k + "=" + str(v))
        print("result count: " + str(len(self.df)))


class Ci(Cmd):
    # default_to_shell = True
    def __init__(self):
        super().__init__(use_ipython=True)
        self.context = {"debug": {"type": "bool", "value": False}}
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

    def _getParams(self, usage: dict) -> dict:
        params = usage
        for param, ptype in params.items():
            if param not in self.context:
                default = None
                prompt = "Enter " + param + ":"
                self.context[param] = {"type": usage[param], "value": None}
            else:
                default = self.context[param]["value"]
                prompt = "Enter " + param + "(" + str(default) + "):"
            if ptype == "password":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["Value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
            elif ptype == "pathi":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
                while not os.path.exists(self.context[param]["value"]):
                    print("Cannot find file " + self.context[param]["value"])
                    # self.context[param] = self.read_input(prompt=prompt)
                    self.context[param]["value"] = input(prompt)
                    if not self.context[param]["value"]:
                        self.context[param]["value"] = default
            elif ptype == "path":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
                while not os.path.exists(os.path.dirname(
                    self.context[param]["value"])
                ):
                    print("Cannot find directory " +
                          os.path.dirname(self.context[param]["value"]))
                    # self.context[param] = self.read_input(prompt=prompt)
                    self.context[param]["value"] = input(prompt)
                    if not self.context[param]["value"]:
                        self.context[param]["value"] = default
            elif ptype == "str":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
            elif ptype == "bool":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
        pl = {}
        for param in params.keys():
            pl[param] = self.context[param]["value"]
        with open(".ci_context.json", "w") as fp:
            json.dump(self.context, fp)
        return pl

    contextparser = argparse.ArgumentParser()
    contextparser.add_argument(
        '-e', '--edit', action="store_true",
        help='Edit all parameters')

    @with_argparser(contextparser)
    def do_c(self, args):
        """Context, global parameters"""
        if args.edit:
            usage = {}
            for k, v in self.context.items():
                usage[k] = v["type"]
            self._getParams(usage)
        else:
            columns = ["Parameter", "Type", "Value"]
            data = []
            for k, v in self.context.items():
                data.append([k,v["type"],v["value"]])
            df = pd.DataFrame(columns=columns, data=data)
            print(df.to_string(index=False, header=True, justify='left'))

    queryparser = argparse.ArgumentParser()
    queryparser.add_argument('query_name', nargs="?", type=str, const="",
                             help='Run the named query and generate results')

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
            params = self._getParams(q.usage()["params"])
            columns = list(q.usage()["return"].keys())
            self.q(qn=q.name(), params=params, columns=columns)
        except Exception:
            traceback.print_exc()
            return 0

    def q(self, qn: str, params: dict, columns: dict):
        if qn not in self.query:
            print("ERROR: query not found " + qn)
            return
        params["debug"] = self.context["debug"]["value"]
        q = self.query[qn]
        if columns:
            result = pd.DataFrame(columns=columns)
            for r in q.exec(params=params,
                            scratchPad=self.scratchPad):
                row = len(result)
                for k in columns:
                    result.at[row, k] = r[k]
            print(str(len(result)) + " results")
            if len(result):
                self.savedResults.append(
                    Result(df=result, qn=qn, p=params))
        else:
            q.exec(params=params, scratchPad=self.scratchPad)

    showparser = argparse.ArgumentParser()
    showparser.add_argument(
        '-R', '--remove_row', nargs="?", type=str, const="",
        help='Condition(s) to remove the row i.e. a == 1 and b == 2')
    showparser.add_argument(
        '-r', '--include_row', nargs="?", type=str, const="",
        help='Condition(s) to include the row i.e. a < 1 and b > 3')
    showparser.add_argument(
        '-C', '--remove_column', nargs="?", type=str, const="",
        help='Coma separated patterns identifying cols to remove i.e. a_*,b_*')
    showparser.add_argument(
        '-c', '--include_column', nargs="?", type=str, const="",
        help='Coma separated patterns identifying cols to include i.e. *X')
    # -g/-s removes the cols that are not grouped-by and not summed.
    showparser.add_argument(
        '-g', '--group_by_column', nargs="?", type=str, const="",
        help='Coma separate patterns identifying cols to group-by for (-s)')
    showparser.add_argument(
        '-s', '--sum_column', nargs="?", type=str, const="",
        help='Coma separate patterns identifying numeric cols to sum for (-g)')
    showparser.add_argument(
        '-n', '--count_rows', nargs="?", type=str, const="",
        help='New column name for count of rows in group by (-g)')

    @with_argparser(showparser)
    def do_s(self, args):
        """Show and/or filter recent results.
           for example,
           s -R a == 1 - removes rows where column a has the value 1
           s -r b == 2 - include rows where column nb has the value 2
           s -C a_*,b_* - exclude columns where name matched a_* or b_*
           s -c a_*,b_* - include columns where name matched a_* or b_*
           s -s b -g a - sum column b partitioned (grouped by) column a 
           s -n count -g a - count rows partitioned (grouped by) column a
           """
        filt = {
            "remove_row": args.remove_row,
            "include_row": args.include_row,
            "remove_column": args.remove_column,
            "include_column": args.include_column,
            "group_by_column": args.group_by_column,
            "sum_column": args.sum_column,
            "count_rows": args.count_rows
        }
        self.s(filt)

    def s(self, filt: dict):
        if len(self.savedResults) == 0:
            print("ERROR: no results")
            return
        result = self.savedResults[-1]
        if (not filt["remove_row"] and not filt["include_row"] and
            not filt["remove_column"] and not filt["include_column"] and
            not filt["group_by_column"] and not filt["sum_column"]
        ):
            print(result.df)
            return
        columns = result.df.columns.tolist()
        df = result.df.copy()
        if filt["remove_row"]:
            try:
                df.query(expr=filt["remove_row"], inplace=True)
                if df.equals(result.df):
                    print("ERROR: no column matching " + filt["remove_row"])
                    return
            except Exception as e:
                print("Error in " + filt["remove_row"] + " " + str(e))
                return
        if filt["include_row"]:
            try:
                df.query(expr=filt["include_row"], inplace=True)
            except Exception as e:
                print("Error in " + filt["include_row"] + " " + str(e))
                return
        if filt["remove_column"]:
            try:
                for pattern in filt["remove_column"].split(","):
                    pat = re.compile(pattern)
                    c = 0
                    for col in columns:
                        if pat.match(col):
                            c += 1
                            df.drop(columns=col, inplace=True)
                    if not c:
                        print("ERROR: no column matching " + pattern)
                        return
            except Exception as e:
                print("Error in " + filt["remove_column"] + " " + str(e))
                return
        if filt["include_column"]:
            try:
                ic = set()
                for pattern in filt["include_column"].split(","):
                    pat = re.compile(pattern, re.IGNORECASE)
                    c = 0
                    for col in columns:
                        if pat.match(col):
                            c += 1
                            ic.add(col)
                    if not c:
                        print("ERROR: no column matching " + pattern)
                        return
                for col in columns:
                    if col not in ic:
                        df.drop(columns=col, inplace=True)
            except Exception as e:
                print("Error in " + filt["include_column"] + " " + str(e))
                return
        if filt["group_by_column"] and (
            filt["sum_column"] or
            filt["count_rows"]
        ):
            try:
                gb = set()
                for pattern in filt["group_by_column"].split(","):
                    pat = re.compile(pattern)
                    for col in columns:
                        if pat.match(col):
                            gb.add(col)
                if not gb:
                    print("Error in -g " +
                          filt["group_by_column"] + " -s " +
                          " not columns selected")
                    return
                if filt["sum_column"]:
                    sc = set()
                    for pattern in filt["sum_column"].split(","):
                        pat = re.compile(pattern)
                        for col in columns:
                            if pat.match(col):
                                sc.add(col)
                    if not sc:
                        print("Error in -s " +
                              filt["sum_column"] + " -s " +
                              " not columns selected")
                        return
                    for col in columns:
                        if col in gb and col in sc:
                            print("Error in -g " +
                                  filt["group_by_column"] + " -s " +
                                  filt["sum_column"] + " " +
                                  " select the same col " + col)
                            return
                    print(df)
                    print(gb)
                    print(sc)
                    df = df.groupby(list(gb))[list(sc)].sum().reset_index()
                    print(df)
                elif filt["count_rows"]:
                    col = filt["count_rows"]
                    if col in columns:
                        print("ERROR: column " + col + " already exists")
                        return
                    df = df.groupby(list(gb)).size().reset_index(name=col)
            except Exception:
                traceback.print_exc()
                print("Error in " +
                      filt["group_by_column"] + " " +
                      str(filt["sum_column"]) + " " +
                      str(filt["count_rows"])
                      )
                return
        if df.equals(result.df):
            print("No new result")
        else:
            print(str(len(df)) + " results")
            self.savedResults.append(
                Result(df=df, qn="_filter_", p=filt))

    deleteparser = argparse.ArgumentParser()

    @with_argparser(deleteparser)
    def do_d(self, args):
        """Delete recent result"""
        if not self.savedResults:
            print("No results")
        else:
            del self.savedResults[-1]
            if self.savedResults:
                print(str(len(self.savedResults[-1].df)) + " results")
            else:
                print("No results")

    analyticparser = argparse.ArgumentParser()
    analyticparser.add_argument(
        '-r', '--read', action="store_true",
        help='Read analytic')
    analyticparser.add_argument(
        '-f', '--force', action="store_true",
        help='Replace analytic or procedures')
    analyticparser.add_argument(
        '-s', '--summary', action="store_true",
        help='Show a summary of the current analytic')

    q_usage = {
        "analytic_name": "str",
        "analytic_path": "pathi"
    }

    @with_argparser(analyticparser)
    def do_a(self, args):
        """Analytic is a list of query and/or show commands.
           Analytics are reinstated for further development.
           Analytics are replayed on different datasets.
           Note: the analytic path is context variable: analyic_path
           Example usage,
           a - write analytic.
           a -f - Replace prior written analytic.
           a -r - read analytic.
           a -r -f - Reread prior analytic
           a -m - a summary of the loaded analytic.
           """
        if args.summary:
            cnt = len(self.savedResults)
            print("Analytic has the following " + str(cnt) + " components:")
            for result in reversed(self.savedResults):
                print("--------------" + str(cnt) + "----------")
                result.print()
            return
        if args.force:
            params = self.context
        else:
            params = self._getParams(self.q_usage)
        pname = os.path.join(params["analytic_path"],params["analytics_name"])
        if args.read:
            if not os.path.exists(pname):
                print("ERROR: cannot find file " + pname)
                return
            if not args.force and self.savedResults:
                if input("Reverting, confirm (Y)") != "Y":
                    return
            with open(pname, "r") as f:
                analytic = json.load(f)
            self.savedResults = []
            for r in analytic:
                n = r["qn"]
                if n == "_filter_":
                    self.s(params=r["params"], columns=r["columns"])
                else:
                    self.q(qn=r["qn"], params=r["params"], columns=r["columns"])
        else:
            analytic = []
            for r in self.savedResults:
                analytic.append({
                    "qn": r.qn,
                    "params": r.params,
                    "columns": r.df.columns.tolist()
                })
            with open(pname, "w") as f:
                json.dump(f,analytic)

    @staticmethod
    def main():
        sys.exit(Ci().cmdloop())


if __name__ == "__main__":
    sys.exit(Ci().cmdloop())
