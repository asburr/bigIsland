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
import json
import os
from inspect import currentframe
from magpie.src.mistype import MIsType
import re
import argparse
import traceback


class MWorksheets:
    def __init__(self, dir: str):
        self.verify_handlers = {
            "composite": self._verifyComposite,
            "listComposites": self._verifyListComposite,
            "feed": self._verifyFeed,
            "path": self._verifyPath,
            "field": self._verifyField,
            "str": self._verifyStr,
            "int": self._verifyInt,
            "email": self._verifyEmail,
            "fmt": self._verifyFmt,
            "any": self._verifyAny,
            "regex": self._verifyRegex,
            "bool": self._verifyBool
        }
        self.title_handlers = {
            "composite": self._titleComposite,
            "listComposites": self._titleListComposite,
            "feed": self._titleFeed
        }
        self.dir = dir
        if not os.path.isdir(self.dir):
            raise Exception("Failed to find worksheet dir " + self.dir)
        schema = os.path.join(self.dir, "worksheetHelp.json")
        try:
            with open(schema,"r") as f:
                try:
                    self.schema = json.load(f)
                except json.JSONDecodeError as e:
                    raise Exception("JSON error in " + schema + " " + str(e))
                except Exception as e:
                    raise Exception("Failed to parse " + schema + " " + str(e))
        except Exception as e:
            raise Exception("Failed to read " + schema + str(e))
        self.ws = {}
        for fn in os.listdir(path=self.dir):
            if fn == "worksheetHelp.json":
                continue
            if not fn.endswith(".json"):
                continue
            n = fn[:-5]
            dfn = os.path.join(self.dir,fn)
            try:
                with open(dfn, "r") as f:
                    j = json.load(f)
                error = self.verifycmds(j)
                if error:
                    raise Exception(error)
                self.ws[n]  = j
            except json.JSONDecodeError as err:
                raise Exception("Failed to parse " + dfn + " " + str(err))
            except Exception as e:
                traceback.print_exc()
                raise Exception("Failed to parse " + dfn + " " + str(e))

    def titles(self) -> list:
        return list(self.ws.keys())

    def sheet(self, title: str) -> list:
        return self.ws[title]

    def _titleComposite(self, cmd: any, schema: any) -> str:
        for k in cmd.keys():
            title = self._titlecmd(cmd[k], schema[k])
            if title:
                return title

    def _titleListComposite(self, cmd: any, schema: any) -> str:
        for j in cmd:
            title = self._titleComposite(j, schema)
            if title:
                return title

    def _titleFeed(self, stack: list, cmd: any, schema: any) -> str:
        if "key" in schema:
            return cmd
        return None

    def _titlecmd(self, cmd: any, schema: any) -> str:
        if "key" in schema:
            return cmd
        t = schema["type"]
        if t in self.title_handlers:
            return self.title_handlers[t](cmd, schema)
        return None

    def cmdTitle(self, cmd: dict) -> str:
        return self._titlecmd(cmd, self.schema[list(cmd.keys())[0]])

    def _Error(self, stack: list, error:str) -> str:
        cf = currentframe()
        return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error

    def _verifyComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, dict):
            return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        for k in cmd.keys():
            stack.append(k)
            if k not in schema:
                return self._Error(stack, "\nExpecting: " + str(list(schema.keys())) + "\ngot: " + k)
            error = self._verifycmd(stack, cmd[k], schema[k])
            if error:
                return error
            stack.pop()
        for k in schema.keys():
            if k in ["type", "desc", "choice", "eg", "default"]:
                continue
            if "default" not in schema[k]:
                # Mandatory
                if k not in cmd:
                    stack.append(k)
                    return self._Error(stack, "missing attribute " + k)
            elif schema[k]["default"] is None:
                # Optional
                pass
            else:
                # default value
                pass

    def _verifyListComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, list):
            return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        for i, j in enumerate(cmd):
            stack.append("e"+str(i))
            error = self._verifyComposite(stack, j, schema)
            if error:
                return error
            stack.pop()

    def _verifyFeed(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if not cmd.isidentifier() and "." not in cmd:
             return self._Error(stack, "\nExpecting identifier " + str(schema)
                          + "\ngot: " + str(cmd))

    def _verifyPath(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        if not cmd.isalnum() and not os.sep in cmd:
             return self._Error(stack, "\nExpecting path, alnum or " + os.sep
                          + "\ngot: " + str(cmd))

    def _verifyField(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        if not cmd.isidentifier() and "." not in cmd:
             return self._Error(stack, "\nExpecting identifier " + str(schema)
                          + "\ngot: " + str(cmd))

    def _verifyStr(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifyInt(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, int):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifyEmail(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if cmd != "${EMAIL}":
            label, d = MIsType.isEmail(label="", json_type=type(cmd), value=cmd)
            if label != "email":
                 return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: "
                              + cmd + "\ntype:" + label)
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifyFmt(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        try:
             p = ()
             for i in range(cmd.count("{")):
                 p+=(1,)
             cmd.format(*p)
        except Exception as e:
             return self._Error(stack, "\nError in format " + cmd + "\nerror: " + str(e))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifyBool(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, bool):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifyAny(self, stack: list, cmd: any, schema: any) -> str:
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        pass

    def _verifyRegex(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        try:
            re.compile(cmd)
        except Exception as e:
            return self._Error(stack, "Error in regex " + cmd + " " + str(e))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifycmd(self, stack: list, cmd: any, schema: any) -> str:
        t = schema["type"]
        if t not in self.verify_handlers:
            if t.endswith(".macro"):
                if t not in self.schema:
                    return self._Error(stack, "Unknown macro named " + t)
                return self._verifycmd(stack, cmd, self.schema[t])
            else:
                return self._Error(stack, "Unknown type " + t)
        return self.verify_handlers[t](stack, cmd, schema)

    def verifycmds(self, j: any) -> str:
        for cmd in j:
            name = list(cmd.keys())[0]
            if name not in self.schema:
                return self._Error([], "Unexpected cmd name " + name)
            error = self._verifycmd([name], cmd[name], self.schema[name])
            if error:
                return "Error in cmd " + name + " " + error

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Worksheet")
        parser.add_argument('dir', help="worksheet dir", nargs='?', const="worksheets", type=str)
        args = parser.parse_args()
        MWorksheets(args.dir)

if __name__ == "__main__":
    MWorksheets.main()