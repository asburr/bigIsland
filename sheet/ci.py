#!/usr/bin/env python3
# CLI for the sheet.
import sys
import os
import json
from sheet.input import Input
from cmd2 import Cmd, Cmd2ArgumentParser, with_argparser
import traceback
# noinspection PyBroadException
try:
    import sheet.inputs
except Exception as e:
    if str(e).startswith("No module named"):
        print("No directory(inputs)...pls run Sheet from the bigIsland"
              "directory")
    elif str(e).startswith("invalid syntax"):
        print("There are syntax errors in the inputs plugins, pls debug")
    traceback.print_exc()
    sys.exit(1)


class Ci(Cmd):
    # default_to_shell = True
    def __init__(self):
        super().__init__(use_ipython=True)
        self.context = {"debug": False}
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

    def _getParams(self, q: Input) -> None:
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
        with open(".ci_context.json", "w") as fp:
            json.dump(self.context, fp)

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
            self._getParams(q)
            result = []
            for r in q.exec(params=self.context,
                            scratchPad=self.scratchPad):
                result.append(r)
            print(str(len(result)) + " results")
            if result:
                self.savedResults.append(result)
        except Exception:
            traceback.print_exc()
            return 0

    def do_s(self, args):
        """Show recent result"""
        if not self.savedResults:
            print("No results")
        else:
            print(str(len(self.savedResults)) +
                  " saved results, recent result:")
            for r in self.savedResults[-1]:
                if r["added"]:
                    print("+ " + r["field"])
                else:
                    print("- " + r["field"])

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
