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


class MWorkSheetException(Exception):
    pass


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
        self.keyfields =  ["__edit__", "__state__", "type", "desc", "choice", "eg", "default"]
        self.keydatafields =  ["__edit__", "__state__"]
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
                    cmd["__state__"] = "pending"
                else:
                    cmd["__state__"] = "blocked"
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
                old = cmd.get(k,None)
                if k not in cmd:
                    cmd[k] = s["default"]
                cmd[k] = cmd[k].format(
                        root=self.expandingcmd.get("root","no-root"),
                        input=self.expandingcmd.get("input","no-input"),
                        feed=self.expandingcmd.get("feed","no-feed")
                        )
                if old != cmd[k]:
                    if "__edit__" not in cmd:
                        cmd["__edit__"] = {}
                    cmd["__edit__"][k] = old
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

    def expandcmd(self, cmd: any, cmdname: str) -> None:
        self.expandingcmd = cmd
        self._expandcmd(cmd, self.schema[cmdname])
        
    def expandcmds(self) -> None:
        for wsn in self.ws.keys():
            for self.expandingcmd in self.ws[wsn]:
                cmdname = self.cmdName(self.expandingcmd)
                self.expandingcmd = self.expandingcmd[cmdname]
                self._expandcmd(self.expandingcmd, self.schema[cmdname])

    def cmd_titles(self) -> list:
        return [x for x in self.schema.keys() if x not in self.keyfields and not x.endswith(".macro")]

    def cmd_descriptions(self) -> list:
        return {name: self.schema[name]["desc"] for name in self.schema.keys() if name not in self.keyfields and not name.endswith(".macro")}

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
        self, at: str, cmd: any, parent: str, schema: any,
        params: dict, selected: dict, description: dict
    ) -> bool:
        retval = False
        for k in schema.keys():
            if k in self.keyfields or k in self.keydatafields:
                continue
            nxtcmd = None
            if cmd is not None:
                nxtcmd = cmd.get(k,None)
                # if nxtcmd is None:
                #     continue
            field = parent+"."+k
            if len(parent) == 0:
                field = k
            if self._paramscmd(at, nxtcmd, field, schema[k], params, selected, description):
                retval = True
        if cmd is not None and "__edit__" in cmd:
            for k in cmd["__edit__"].keys():
                selected[parent+"."+k] = cmd["__edit__"][k]
                selected["default"+parent+"."+k] = cmd[k]
        return retval

    def _paramsListComposite(
        self, at: str, cmd: any, parent: str, schema: any,
        params: dict, selected: dict, description: dict
    ) -> bool:
        retval = False
        if cmd is not None:
            for i, j in enumerate(cmd):
                field = parent+"."+str(i)
                params[field] = "deletebutton"
                selected[field] = True
                if self._paramsComposite(at, j, field, schema, params, selected, description):
                    retval = True
        else:
            field = parent+".0"
            params[field] = "deletebutton"
            selected[field] = True
            self._paramsComposite(at, None, field, schema, params, selected, description)
        return retval

    # Return True when cmd has at least one field in the substructure, this
    # is used by parent option to determine if the command has activated this
    # substructure as an option.
    def _paramscmd(
        self, at: str, cmd: any, parent: str, schema: any,
        params: dict, selected: dict, description: dict
    ) -> bool:
        nxtat = at
        # print("paramscmd " + str(at) + " " + str(parent))
        if at is not None:  # Searching for a subtree.
            if not at.startswith(parent):
                return False
            if at in parent:  # Found subtree.
                nxtat = None
        retval = False
        if "default" in schema:
            if schema["default"] is None:   # Optional param, add the option.
                opt = parent+".option"
                params[opt] = "option"
                selected[parent] = False  # Option is OFF.
            else:  # Default value
                selected["default"+parent] = str(schema["default"])
        t = schema["type"]
        if t == "feed":
            p = parent[:parent.rindex(".")+1]
            if p not in params:
                params[p] = "samplebutton"
            else:
                params[p] += ",samplebutton"
            selected[p] = cmd
        if t in ["feed", "feedRef", "path", "field", "str", "email", "fmt", "any", "regex"]:
            if cmd is not None:
                params[parent] = "str"
                selected[parent] = cmd
                retval = True
            else:
                params[parent] = "str"
        elif t in ["int", "bool"]:
            params[parent] = "int"
            if cmd is not None:
                selected[parent] = str(cmd)
                retval = True
        elif t in self.params_handlers:
            if t == "choice":
                params[parent] = [x for x in schema.keys() if x not in self.keyfields]
                if cmd is None or len(cmd) == 0:
                    pass
                else:
                    retval = True
                    selected[parent] = list(cmd.keys())[0]
            opt = parent+".option"
            if "default" in schema and schema["default"] is None:
                params[opt] = "option"
                selected[opt] = False
                if cmd is not None or at is not None:
                    if t == "listComposites":
                        params[parent] = "addbutton"
                        selected[parent] = True
                    if self.params_handlers[t](nxtat, cmd, parent, schema, params, selected, description):
                        retval = True
                        selected[opt] = True
            else:
                if t == "listComposites":
                    params[parent] = "addbutton"
                    selected[parent] = True
                    if cmd is not None or at is not None:
                        if self.params_handlers[t](nxtat, cmd, parent, schema, params, selected, description):
                            retval = True
                else:
                    if self.params_handlers[t](nxtat, cmd, parent, schema, params, selected, description):
                        retval = True
        else:
            raise Exception("Unexpected type " + t)
        if "desc" in schema:
            description[parent] = schema["desc"]
        if "default" in schema and schema["default"] is None:
            # Option is true when there is a value in cmd in the sub-tree.
            opt = parent+".option"
            selected[opt] = retval
        return retval

    # Get cmd param name and type into "params". Put value from cmd into
    # "selected", or any default value when there is no value in cmd.
    # "at" is used to get a subset of the params from the schema, the
    # subset is used to when an option is first turned on, and when add
    # a entry to a list of params.
    # Usage:
    """
from magpie.src.mworksheets import MWorksheets
ws = MWorksheets("worksheets")
cmd = ws.getCmd("directory.files.pbx")
(params, selected, desc) = ws.paramsCmd(cmd, at="files")
print(params)
** Missing files.archive.option
(params, selected, desc) = ws.paramsCmd(None, at="files")
print(params)
print(selected)
print(desc)
    """
    def paramsCmd(self, cmd: dict, at: str) -> (dict, dict, dict):
        params = {}
        selected = {}
        description = {}
        if at == "":
            at = None
        self._paramscmd(
            at=at, cmd=cmd, parent="", schema=self.schema,
            params=params, selected=selected, description=description)
        return (params, selected, description)

    def getCmd(self, outputs: str) -> dict:
        return self.feeds[outputs.split("\n")[0]][1]
        
    def fieldInSelected(self, field: str, selected: dict) -> bool:
        if field in selected:
            return True
        for key in selected.keys():
            if key.startswith(field):
                return True
        return False

    def _updateComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        for k in schema.keys():
            field = parent+"."+k
            t = ""
            try:
                if k in self.keyfields:
                    continue
                if cmd is not None:
                    if not self.fieldInSelected(field,selected):
                        if k in cmd:
                            del cmd[k]
                    else:
                        t = self._updatecmd(cmd.get(k,None), field, schema[k], selected)
                        if t is None:
                            t = selected.get("default"+field, None)
                        if t is not None:
                            cmd[k] = t
                else:
                    if field in selected:
                        t = self._updatecmd(None, field, schema[k], selected)
                        if t is None:
                            t = selected.get("default"+field, None)
                        if t is not None:
                            cmd = {k: t}
            except MWorkSheetException as e:
                raise e;
            except Exception:
                raise MWorkSheetException("field \""+field+"\" bad value \""+str(t)+"\"")
        return cmd

    def _updateListComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        fields = []
        for k in selected.keys():
            if k.startswith(parent):
                if k[k.rindex(".")+1:].isdigit():
                    fields.append(k)
        if cmd is not None:
            for i, j in enumerate(cmd):
                field = parent+"."+str(i)
                if field in fields:
                    fields.remove(field)
                if field not in selected:
                    # When saved back to disk at this time the deleted
                    # items are removed.
                    cmd[i]["__state__"] = "deleted"
                else:
                    # Re-added
                    if "__state__" in cmd[i]:
                        del cmd[i]["__state__"]
                    cmd[i] = self._updateComposite(j, field, schema, selected)
                    if cmd[i] is None:
                        cmd[i] = selected.get("default"+field, None)
        for field in fields:
            i = int(field[field.rindex(".")+1:])
            if i != len(cmd):
                raise Exception("Adding " + field + " expecting field " + str(len(cmd)))
            cmd.append(self._updateComposite(None, field, schema, selected))
        return cmd

    def _updatecmd(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        t = schema["type"]
        if t in ["feed", "feedRef", "path", "field", "str", "email", "fmt",
                 "any", "regex"]:
            return selected.get(parent, None)
        elif t in ["int"]:
            i = selected.get(parent, None)
            if i is None:
                return None
            return int(i)
        elif t in ["bool"]:
            b = selected.get(parent, None)
            if b == "True":
                return True
            if b == "False":
                return False
            return None
        elif t in self.update_handlers:
            if t == "choice":
                k = selected.get(parent, None)
                if k is None:
                    return {}
                if k not in cmd:
                    cmd = {k: {}}
            return self.update_handlers[t](cmd, parent, schema, selected)
        else:
            raise Exception("Unexpected type " + t)

    # Update values in command from selected values.
    def updateCmd(self, wsn: str, cmd: dict, selected: dict) -> str:
        if cmd is not None:
            cmdname = self.cmdName(cmd)
            backup = copy.deepcopy(cmd)
            # Remove command from all the feeds.
            for feed in self.cmdFeed(cmd):
                del self.feeds[feed]
        else:
            backup = None
            cmdname = list(selected.keys())[0]
            cmdname = cmdname[0:cmdname.index(".")]
            cmd = {cmdname: None}
        # print(json.dumps(selected, indent=4, sort_keys=True))
        error = ""
        undofeeds = []
        try:
            cmd[cmdname] = self._updatecmd(
                cmd[cmdname], parent=cmdname, schema=self.schema[cmdname],
                selected=selected)
            if backup is None:
                for j in self.sheet(wsn):
                    if cmdname in j:
                        return "More than one cmd \"" + cmdname + "\""
                self.ws[wsn].append(cmd)
            try:
                # Update feed.
                feeds = self.cmdFeed(cmd)
            except KeyError as e:
                error = "Bad feed name variable: " + str(e)
            except Exception as e:
                error = "Bad feed name " + type(e).__name__ + " " + str(e)
        except Exception as e:
            error = str(e)
        # print(json.dumps(self.ws[wsn], indent=4, sort_keys=True))
        if not error:
            try:
                for feed in feeds:
                    if feed in self.feeds:
                        raise Exception("duplicate feed name " + feed)
                    undofeeds.append(feed)
                    self.feeds[feed] = (wsn, cmd)
                error = self.verifycmds(self.ws[wsn])
                self.expandingcmd = cmd[cmdname]
                self._expandcmd(self.expandingcmd, self.schema[cmdname])
            except Exception as e:
                traceback.print_exc()
                error = str(e)
        if error:
            # Restore command
            for feed in undofeeds:
                del self.feeds[feed]
            if backup is not None:
                for feed in self.cmdFeed(backup):
                    self.feeds[feed] = (wsn, backup)
                del cmd[cmdname]
                cmd[cmdname] = backup[cmdname]
            else:
                del self.ws[wsn][-1]
        return error

    def _purgeCmd(self, cmd: any, schema: any) -> None:
        if cmd is None:
            return
        t = schema["type"]
        if t == "composite":
            for k in cmd.keys():
                if k in self.keyfields:
                    continue
                self._purgeCmd(cmd[k], schema[k])
        elif t == "listComposites":
            delete = []
            for i, j in enumerate(cmd):
                if "__state__" in j:
                    if j["__state__"] == "deleted":
                        delete.append(i)
                for k in j.keys():
                    if k in self.keyfields:
                        continue
                    self._purgeCmd(j[k], schema[k])
            for i in reversed(delete):
                del cmd[i]

    # Remove for list all deleted entries (__state__ == deleted)
    def purgeCmd(self, cmd: dict) -> None:
        cmdname = self.cmdName(cmd)
        self._purgeCmd(cmd[cmdname], self.schema[cmdname])

    def deleteCmd(self, wsn: str, outputs: str) -> None:
        cmd = self.getCmd(outputs)
        for feed in self.cmdFeed(cmd):
            del self.feeds[feed]
        self.ws[wsn].remove(cmd)
        
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
            cmd = cmd.format(
                root=self.expandingcmd.get("root","no-root"),
                input=self.expandingcmd.get("input","no-input"),
                feed=self.expandingcmd.get("feed","no-feed")
                )
            feeds.append(cmd)
        if t in self.feed_handlers:
            self.feed_handlers[t](cmd, schema, feeds)

    def cmdFeed(self, cmd: any) -> list:
        cmdname = self.cmdName(cmd)
        feeds = []
        self.expandingcmd = cmd[cmdname]
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

    @staticmethod
    def cmdName(cmd: any) -> str:
        for k in cmd.keys():
            if k not in ["__state__"]:
                return k
        raise Exception("cmdName no name")

    def _Error(self, stack: list, error:str) -> str:
        cf = currentframe()
        return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error

    def _verifyComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, dict):
            return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        for k in cmd.keys():
            if k in self.keydatafields:
                continue
            if k in self.keyfields:
                return self._Error(stack, "\ntemplate field name is also a data field name: " + k)
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
             return self._Error(stack, "\nExpecting path"
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

    def verifycmd(self, cmd: dict) -> str:
        name = list(cmd.keys())[0]
        if name not in self.schema:
            return self._Error([], "Unexpected cmd name " + name)
        error = self._verifycmd([name], cmd[name], self.schema[name])
        if error:
            return "Error in cmd " + name + " " + error

    def verifycmds(self, j: list) -> str:
        for cmd in j:
            error = self.verifycmd(cmd)
            if error:
                return error

    def blocked(self) -> list:
        return [cmd for feed,cmd in self.feeds.items() if cmd["__state__"] == "blocked"]

    def pending(self) -> dict:
        for feed,cmd in self.feeds.items():
            if cmd["__state__"] == "pending":
                return cmd
        return None

    # Returns list of newly pending commands
    def ran(self, cmd) -> list:
        feeds = self.cmdFeed(cmd)
        cmds = []
        for feed in feeds:
            cmd = self.feeds[feed]
            cmd["__state__"] = "ready"
            for cmd in self.feeds.values():
                if cmd["__state__"] == "blocked":
                    cmd["__state__"] = "pending"
                    for feed in self.cmdinput(cmd):
                       if self.feeds[feed]["__state__"] != "ready":
                           cmd["__state__"] == "blocked"
                           break
                    if cmd["__state__"] == "pending":
                        cmds.append(cmd)
        return cmds

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Worksheet")
        parser.add_argument('dir', help="worksheet dir", nargs='?', const="worksheets", type=str)
        args = parser.parse_args()
        ws = MWorksheets(args.dir)
        at="files"
        print(at)
        (d_params, d_defaults, d_desc) = ws.paramsCmd(None,at)
        outputs = "directory.files.pbx"
        cmd = ws.getCmd(outputs)
        (params, selected, description) = ws.paramsCmd(cmd,at)
        print("params")
        print(d_params)
        print(params)
        print("selected")
        print(d_defaults)
        print(selected)
        for title in ws.titles():
            print("Sheet:" + title)
            for cmd in ws.sheet(title):
                print("      " + ws.cmdName(cmd) + ":" + str(ws.cmdFeed(cmd)))
        print("Feeds ready to run")
        for feed in ws.feeds:
            (wsn, cmd) = ws.feeds[feed]
            if cmd["__state__"] == "pending":
                print("    " + feed + " " + cmd["__state__"])
        print("Feeds blocked")
        for feed in ws.feeds:
            (wsn, cmd) = ws.feeds[feed]
            if cmd["__state__"] == "blocked":
                print("    " + feed + " " + cmd["__state__"])


if __name__ == "__main__":
    MWorksheets.main()