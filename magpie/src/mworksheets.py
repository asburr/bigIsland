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
from difflib import SequenceMatcher
import copy


class MWorksheets:
    def __init__(self, dir: str):
        self.verify_handlers = {
            "composite": self._verifyComposite,
            "listComposites": self._verifyListComposite,
            "choice": self._verifyChoice,
            "feed": self._verifyFeed,
            "feedRef": self._verifyFeed,
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
        self.feedRef_handlers = {
            "composite": self._feedRefComposite,
            "listComposites": self._feedRefListComposite,
            "choice": self._feedRefComposite
        }
        self.feed_handlers = {
            "composite": self._feedComposite,
            "listComposites": self._feedListComposite,
            "choice": self._feedComposite
        }
        self.params_handlers = {
            "composite": self._paramsComposite,
            "listComposites": self._paramsListComposite,
            "choice": self._paramsComposite
        }
        self.putparams_handlers = {
            "composite": self._putparamsComposite,
            "listComposites": self._putparamsListComposite,
            "choice": self._putparamsComposite
        }
        self.expand_handlers = {
            "composite": self._expandComposite,
            "listComposites": self._expandListComposite,
            "choice": self._expandComposite
        }
        self.input_handlers = {
            "composite": self._inputComposite,
            "listComposites": self._inputListComposite,
            "choice": self._inputComposite
        }
        self.update_handlers = {
            "composite": self._updateComposite,
            "listComposites": self._updateListComposite,
            "choice": self._updateComposite
        }
        self.keyfields =  ["type", "desc", "choice", "eg", "default"]
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
        self.feedNames = set()
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
        self.expandcmds()
        self.feeds = {}
        for wsn in self.ws.keys():
            for cmd in self.ws[wsn]:
                feeds = self.cmdFeedRef(cmd)
                if len(feeds) == 0:
                    cmd["state"] = "pending"
                else:
                    cmd["state"] = "blocked"
                feeds = self.cmdFeed(cmd)
                for feed in feeds:
                    if feed in self.feeds:
                        raise Exception("Duplicate feeds "+feed+" in "+wsn)
                    self.feeds[feed] = (wsn, cmd)
        for wsn in self.ws.keys():
            for cmd in self.ws[wsn]:
                feeds = self.cmdFeedRef(cmd)
                for feed in feeds:
                    if feed not in self.feeds:
                        ratio = 0.0
                        nearest = ""
                        for of in self.feeds.keys():
                            r = 0.0
                            for wof in of.split("."):
                                hr = 0.0
                                for wfeed in feed.split("."):
                                    wr = SequenceMatcher(None, wof, wfeed).ratio()
                                    if wr > hr:
                                        hr = wr
                                r += hr
                            if r > ratio:
                                nearest = of
                                ratio = r
                        if nearest:
                            raise Exception("Unknown feed "+feed+" in worksheet \""+wsn +"\" did you mean \"" + nearest + "\"?")
                        else:
                            raise Exception("Unknown feed "+feed+" in "+wsn)

    def _expandComposite(self, cmd: any, schema: any) -> None:
        for k in schema.keys():
            if k in self.keyfields:
                continue
            s = schema[k]
            if s["type"] == "feed":
                if k not in cmd:
                    cmd[k] = s["default"]
                cmd[k] = cmd[k].format(
                        root=self.expandingcmd.get("root","no-root"),
                        input=self.expandingcmd.get("input","no-input"),
                        feed=self.expandingcmd.get("feed","no-feed")
                        )
            if cmd:
                nxtcmd = cmd.get(k,None)
            else:
                nxtcmd = None
            self._expandcmd(nxtcmd, s)

    def _expandListComposite(self, cmd: any, schema: any) -> None:
        for j in cmd:
            self._expandComposite(j, schema)

    def _expandcmd(self, cmd: any, schema: any) -> None:
        if cmd is None:
            return
        t = schema["type"]
        if t in self.expand_handlers:
            return self.expand_handlers[t](cmd, schema)

    def expandcmds(self) -> None:
        for wsn in self.ws.keys():
            for self.expandingcmd in self.ws[wsn]:
                cmdname = self.cmdName(self.expandingcmd)
                self.expandingcmd = self.expandingcmd[cmdname]
                self._expandcmd(self.expandingcmd, self.schema[cmdname])
        
    def titles(self) -> list:
        return list(self.ws.keys())

    def sheet(self, title: str) -> list:
        return self.ws[title]

    def addSheet(self, title: str) -> str:
        if title in self.ws:
            return "Duplicate name"
        self.ws[title] = {}
        return ""

    def inputCmdOutput(self, title: str) -> list:
        rows=[]
        for cmd in self.ws[title]:
            inputs = "\n".join(self.cmdFeedRef(cmd))
            if len(inputs) == 0:
                rows.append([
                    "",
                    self.cmdName(cmd),
                    "\n".join(self.cmdFeed(cmd))
                    ])
        for cmd in self.ws[title]:
            inputs = "\n".join(self.cmdFeedRef(cmd))
            if len(inputs) > 0:
                rows.append([
                    inputs,
                    self.cmdName(cmd),
                    "\n".join(self.cmdFeed(cmd))
                    ])
        return rows

    def _paramsComposite(
        self, cmd: any, parent: str, schema: any, params: dict, selected: dict,
        description: dict
    ) -> None:
        for k in schema.keys():
            if k in self.keyfields:
                continue
            if cmd:
                nxtcmd = cmd.get(k,None)
            else:
                nxtcmd = None
            self._paramscmd(nxtcmd, parent+"."+k, schema[k], params, selected, description)

    def _paramsListComposite(
        self, cmd: any, parent: str, schema: any, params: dict, selected: dict,
        description: dict
    ) -> None:
        if cmd is not None:
            params[parent] = "addbutton"
            selected[parent] = True
            for i, j in enumerate(cmd):
                field = parent+"."+str(i)
                params[field] = "deletebutton"
                selected[field] = True
                self._paramsComposite(j, field, schema, params, selected, description)

    def _paramscmd(
        self, cmd: any, parent: str, schema: any, params: dict, selected: dict,
        description: dict
    ) -> None:
        t = schema["type"]
        if t in ["feed", "feedRef", "path", "field", "str", "email", "fmt",
                 "any", "regex"]:
            params[parent] = "str"
            if cmd is not None:
                selected[parent] = cmd
        elif t in ["int", "bool"]:
            params[parent] = "int"
            if cmd is not None:
                selected[parent] = str(cmd)
        elif t in self.params_handlers:
            if t == "choice":
                params[parent] = [x for x in schema.keys() if x not in self.keyfields]
                if cmd is None or len(cmd) == 0:
                    selected[parent] = ""
                else:
                    selected[parent] = list(cmd.keys())[0]
            self.params_handlers[t](cmd, parent, schema, params, selected, description)
        else:
            raise Exception("Unexpected type " + t)
        if "desc" in schema:
            description[parent] = schema["desc"]

    def paramsCmd(self, outputs: str) -> (str, dict, dict):
        cmd = self.feeds[outputs.split("\n")[0]][1]
        cmdname = self.cmdName(cmd)
        params = {}
        selected = {}
        description = {}
        self._paramscmd(
            cmd[cmdname], parent="", schema=self.schema[cmdname],
            params=params, selected=selected, description=description)
        return (cmdname, cmd, params, selected, description)

    def _updateComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> None:
        for k in schema.keys():
            if k in self.keyfields:
                continue
            field = parent+"."+k
            if cmd:
                if field not in selected:
                    if k in cmd:
                        del cmd[k]
                else:
                    cmd[k] = self._updatecmd(cmd.get(k,None), field, schema[k], selected)
            else:
                if field in selected:
                    cmd = {k: self._updatecmd(None, field, schema[k], selected)}

    def _updateListComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> None:
        if cmd is not None:
            delete = []
            for i, j in enumerate(cmd):
                field = parent+"."+str(i)
                if field not in selected:
                    delete.append(i)
                else:
                    cmd[i] = self._updateComposite(j, field, schema, selected)
            for i in reversed(delete):
                del cmd[i]

    def _updatecmd(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> None:
        t = schema["type"]
        if t in ["feed", "feedRef", "path", "field", "str", "email", "fmt",
                 "any", "regex"]:
            return selected.get(parent, None)
        elif t in ["int", "bool"]:
            return selected.get(parent, None)
        elif t in self.update_handlers:
            if t == "choice":
                k = selected.get(parent, None)
                if k is None:
                    return {}
                if k not in cmd:
                    cmd = {k: {}}
            self.update_handlers[t](cmd, parent, schema, selected)
        else:
            raise Exception("Unexpected type " + t)

    def updateCmd(self, wsn: str, cmd: dict, selected: dict) -> None:
        cmdname = self.cmdName(cmd)
        backup = copy.deepcopy(cmd[cmdname])
        self._updatecmd(
            cmd[cmdname], parent="", schema=self.schema[cmdname],
            selected=selected)
        try:
            self.verifycmds(self.ws[wsn])
        except Exception as e:
            raise e
        del cmd[cmdname]
        cmd[cmdname] = backup
        
    def _putparamsComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        newcmd = {}
        for k in schema.keys():
            if k in self.keyfields:
                continue
            if cmd:
                nxtcmd = cmd.get(k,None)
            else:
                nxtcmd = None
            j = self._putparamscmd(nxtcmd, parent+"."+k, schema[k], selected)
            if j is not None:
                newcmd[k] = j
        return newcmd

    def _putparamsListComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        if cmd is not None:
            newcmd = []
            for i, j in enumerate(cmd):
                x = self._putparamsComposite(j, parent+"."+str(i), schema, selected)
                if x is not None:
                    newcmd.append(j)
            return newcmd
        return None

    def _putparamscmd(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        t = schema["type"]
        if t in ["feed", "feedRef", "path", "field", "str", "email", "fmt",
                 "any", "regex"]:
            if parent in selected:
                return selected[parent]
            else:
                return cmd
        elif t in ["int"]:
            if parent in selected:
                try:
                    return int(selected[parent])
                except Exception:
                    raise Exception(parent + " bad int " + selected[parent])
            else:
                return cmd
        elif t in ["bool"]:
            if parent in selected:
                if selected[parent] in ["True", "true", "t", "T"]:
                    return True
                elif selected[parent] in ["False", "false", "f", "F"]:
                    return False
                else:
                    raise Exception(parent + " bad bool " + selected[parent])
            else:
                return cmd
        elif t in self.params_handlers:
            return self.putparams_handlers[t](cmd, parent, schema, selected)
        else:
            raise Exception("Unexpected type " + t)

    def putparamsCmd(self, outputs: str, selected: dict) -> None:
        cmd = self.feeds[outputs.split("\n")[0]][1]
        cmdname = self.cmdName(cmd)
        cmd[cmdname] = self._putparamscmd(
            cmd[cmdname], parent="", schema=self.schema[cmdname],
            selected=selected)

    def deleteCmd(self, outputs: str) -> None:
        cmd = self.feeds[outputs.split("\n")[0]][1]
        for feed in self.cmdFeed(cmd):
            del self.feeds[feed]
        cmdname = self.cmdName(self, cmd)
        del self.ws[cmdname]
        
    def _feedComposite(self, cmd: any, schema: any, feeds: list) -> None:
        for k in schema.keys():
            if k in self.keyfields:
                continue
            if cmd:
                nxtcmd = cmd.get(k,None)
            else:
                nxtcmd = None
            self._feedcmd(nxtcmd, schema[k], feeds)

    def _feedListComposite(self, cmd: any, schema: any, feeds: list) -> None:
        if cmd is not None:
            for j in cmd:
                self._feedComposite(j, schema, feeds)

    def _feedcmd(self, cmd: any, schema: any, feeds: list) -> None:
        t = schema["type"]
        if t == "feed":
            feeds.append(cmd)
        if t in self.feed_handlers:
            self.feed_handlers[t](cmd, schema, feeds)

    def cmdFeed(self, cmd: any) -> list:
        cmdname = self.cmdName(cmd)
        feeds = []
        self._feedcmd(cmd[cmdname], self.schema[cmdname], feeds)
        return feeds
            
    def _feedRefComposite(self, cmd: any, schema: any, feeds: list) -> None:
        for k in schema.keys():
            if k in self.keyfields:
                continue
            if cmd:
                nxtcmd = cmd.get(k,None)
            else:
                nxtcmd = None
            self._feedRefcmd(nxtcmd, schema[k], feeds)

    def _feedRefListComposite(self, cmd: any, schema: any, feeds: list) -> None:
        if cmd is not None:
            for j in cmd:
                self._feedRefComposite(j, schema, feeds)

    def _feedRefcmd(self, cmd: any, schema: any, feeds: list) -> None:
        t = schema["type"]
        if t == "feedRef" and cmd is not None:
            feeds.append(cmd)
        if t in self.feed_handlers:
            self.feedRef_handlers[t](cmd, schema, feeds)

    def cmdFeedRef(self, cmd: any) -> list:
        cmdname = self.cmdName(cmd)
        feeds = []
        self._feedRefcmd(cmd[cmdname], self.schema[cmdname], feeds)
        return feeds

    def _inputComposite(self, cmd: any, schema: any, inputs: list) -> None:
        for k in schema.keys():
            if k in self.keyfields:
                continue
            self._inputcmd(cmd.get(k,None), schema[k], inputs)

    def _inputListComposite(self, cmd: any, schema: any, inputs: list) -> None:
        for j in cmd:
            title = self._inputComposite(j, schema, inputs)
            if title:
                return title

    def _inputcmd(self, cmd: any, schema: any, inputs: list) -> None:
        if schema["type"] == "feed":
            if cmd is None:
                if "default" in schema:
                    inputs.append(schema["default"])
            else:
                inputs.append(cmd)
            return
        t = schema["type"]
        if t in self.input_handlers:
            self.input_handlers[t](cmd, schema, inputs)
        return

    def cmdinput(self, cmd: any) -> list:
        cmdname = self.cmdName(cmd)
        inputs = []
        self._inputcmd(cmd[cmdname], self.schema[cmdname], inputs)
        return inputs
            
    def cmdName(self, cmd: any) -> str:
        return list(cmd.keys())[0]

    def _Error(self, stack: list, error:str) -> str:
        cf = currentframe()
        return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error

    def _verifyComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, dict):
            return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        for k in cmd.keys():
            if k in self.keyfields:
                return self._Error(stack, "\nunexpected: " + k)
            stack.append(k)
            if k not in schema:
                l = [k for k in schema.keys() if k not in self.keyfields]
                return self._Error(stack, "\nExpecting: " + str(list(l)) + "\ngot: " + k)
            error = self._verifycmd(stack, cmd[k], schema[k])
            if error:
                return error
            stack.pop()
        for k in schema.keys():
            if k in self.keyfields:
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

    def _verifyChoice(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, dict):
            return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        if len(cmd) != 1:
            return self._Error(stack, "\nMust be one key in choice " + str(schema))
        for k in cmd.keys():
            stack.append(k)
            if k not in schema:
                l = [k for k in schema.keys() if k not in self.keyfields]
                return self._Error(stack, "\nExpecting: " + str(list(l)) + "\ngot: " + k)
            error = self._verifycmd(stack, cmd[k], schema[k])
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

    def _verifyInt(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, int):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " +
                          str(cmd) + " " + str(type(cmd)))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))

    def _verifyEmail(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, str):
             return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if cmd != "{EMAIL}":
            label, d = MIsType.isEmail(label="", json_type=type(cmd), value=cmd)
            if label != "email":
                 return self._Error(stack, "\nExpecting " + str(schema) + ", or {EMAIL}\ngot: "
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

    def blocked(self) -> list:
        return [cmd for feed,cmd in self.feeds.items() if cmd["state"] == "blocked"]

    def pending(self) -> dict:
        for feed,cmd in self.feeds.items():
            if cmd["state"] == "pending":
                return cmd
        return None

    # Returns list of newly pending commands
    def ran(self, cmd) -> list:
        feeds = self.cmdFeed(cmd)
        cmds = []
        for feed in feeds:
            cmd = self.feeds[feed]
            cmd["state"] = "ready"
            for cmd in self.feeds.values():
                if cmd["state"] == "blocked":
                    cmd["state"] = "pending"
                    for feed in self.cmdinput(cmd):
                       if self.feeds[feed]["state"] != "ready":
                           cmd["state"] == "blocked"
                           break
                    if cmd["state"] == "pending":
                        cmds.append(cmd)
        return cmds

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Worksheet")
        parser.add_argument('dir', help="worksheet dir", nargs='?', const="worksheets", type=str)
        args = parser.parse_args()
        ws = MWorksheets(args.dir)
        for title in ws.titles():
            print("Sheet:" + title)
            for cmd in ws.sheet(title):
                print("      " + ws.cmdName(cmd) + ":" + str(ws.cmdFeed(cmd)))
        print("Feeds ready to run")
        for feed in ws.feeds:
            (wsn, cmd) = ws.feeds[feed]
            if cmd["state"] == "pending":
                print("    " + feed + " " + cmd["state"])
        print("Feeds blocked")
        for feed in ws.feeds:
            (wsn, cmd) = ws.feeds[feed]
            if cmd["state"] == "blocked":
                print("    " + feed + " " + cmd["state"])


if __name__ == "__main__":
    MWorksheets.main()