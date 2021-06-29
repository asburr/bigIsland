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
# CLI for the sheet.
import sys
import os
import json
import pandas as pd
# from sheet.input import Input
import argparse
from cmd2 import Cmd, with_argparser
from sheet.result import Result
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
                print("Error in module \"" + inp.name() + "\":\n" + error)
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
                if not self.context[param]["value"]:
                    return
            elif ptype == "pathi":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
                while True:
                    try:
                        if os.path.exists(self.context[param]["value"]):
                            break
                    except Exception:
                        pass
                    print("Cannot find file " + self.context[param]["value"])
                    # self.context[param] = self.read_input(prompt=prompt)
                    self.context[param]["value"] = input(prompt)
                    if not self.context[param]["value"]:
                        self.context[param]["value"] = default
                    if not self.context[param]["value"]:
                        return
            elif ptype == "path":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
                while True:
                    try:
                        if os.path.exists(os.path.dirname(
                                self.context[param]["value"])
                        ):
                            break
                    except Exception:
                        pass
                    print("Cannot find directory " +
                          os.path.dirname(self.context[param]["value"]))
                    # self.context[param] = self.read_input(prompt=prompt)
                    self.context[param]["value"] = input(prompt)
                    if not self.context[param]["value"]:
                        self.context[param]["value"] = default
                    if not self.context[param]["value"]:
                        return
            elif ptype == "str":
                # self.context[param] = self.read_input(prompt=prompt)
                self.context[param]["value"] = input(prompt)
                if not self.context[param]["value"]:
                    self.context[param]["value"] = default
                if not self.context[param]["value"]:
                    return
            elif ptype == "bool":
                while True:
                    try:
                        self.context[param]["value"] = bool(input(prompt))
                        break
                    except Exception:
                        pass
                    if not self.context[param]["value"]:
                        self.context[param]["value"] = default
                    if not self.context[param]["value"]:
                        return
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
    queryparser.add_argument(
        '-t', '--test', action="store_true",
        help="Test query without saving results")

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
            msg = q.constraints()
            if msg:
                print(msg)
                return
            params = self._getParams(q.usage()["params"])
            self.q(qn=q.name(), params=params, save=not args.test)
        except Exception:
            traceback.print_exc()
            return 0

    def q(self, qn: str, params: dict, save: bool):
        if qn not in self.query:
            print("ERROR: query not found " + qn)
            return
        params["debug"] = self.context["debug"]["value"]
        q = self.query[qn]
        if len(self.savedResults) == 0:
            savedResult = None
        else:
            savedResult = self.savedResults[-1]
        df = q.exec(result=savedResult,
                    params=params,
                    scratchPad=self.scratchPad)
        if df:
            if save:
                print(str(len(df)) + " results")
                self.savedResults.append(Result(df=df, qn=qn, p=params))
            else:
                print(df)
        else:
            print("No results, nothing saved!")

    showparser = argparse.ArgumentParser()
    showparser.add_argument(
        '-c', '--columns', action="store_true",
        help="Show column names without showing the rows of data.")

    @with_argparser(showparser)
    def do_s(self, args):
        """Show recent result."""
        if len(self.savedResults) == 0:
            print("No saved results")
            return
        result = self.savedResults[-1]
        if args.cols:
            print(str(len(result.df.columns)) + " titles:")
            for i, col in enumerate(result.df.columns):
                print(str(i) + " " + col)
        else:
            print(result.df)

    deleteparser = argparse.ArgumentParser()
    deleteparser.add_argument(
        '-a', '--all', action="store_true",
        help='Delete all results')

    @with_argparser(deleteparser)
    def do_d(self, args):
        """Delete recent result"""
        if args.all:
            while self.saveResults:
                del self.savedResult[-1]
            print("No results")
        else:
            if self.savedResults:
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
                self.q(qn=r["qn"], params=r["params"])
        else:
            analytic = []
            for r in self.savedResults:
                analytic.append({
                    "qn": r.qn,
                    "params": r.params
                })
            with open(pname, "w") as f:
                json.dump(f,analytic)

    @staticmethod
    def main():
        sys.exit(Ci().cmdloop())


if __name__ == "__main__":
    sys.exit(Ci().cmdloop())
