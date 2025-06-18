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
from magpie.src.mjournal import MJournal, MJournalChange, MJournalChangeFactory, MJournalRebase
import re
import argparse
import traceback
from difflib import SequenceMatcher
import copy
import shutil
from magpie.src.mzdatetime import MZdatetime
import uuid


class MWorkSheetException(Exception):
    pass

class MWorksheetsCmdChange(MJournalChange):
    """ A change to a command. Oldselected is used by the databases, to verify that the database has the same version of the command. """
    def __init__(self, wsuuid: str, cmduuid: str, cmdname: str, oldselected: dict, newselected: dict, when:MZdatetime = None):
        super().__init__(when)
        self.wsuuid = wsuuid
        self.cmduuid = cmduuid
        self.cmdname = cmdname
        self.oldselected = oldselected
        self.newselected = newselected

    def fromJson(j: dict):
        return MWorksheetsCmdChange(**j)
    
    def __str__(self):
        return self.when.strftime(short=True)+" cmd : "+self.cmdname+" "+str(self.selected)

    def msgParams(self) -> dict:
        return {
            "cmdUuid": self.cmduuid,
            "sheetUuid": self.wsuuid,
            "oldcmd": self.oldselected,
            "newcmd": self.selected,
            "routing": True
        }

    def msgType(self) -> str:
        return "_cmdReq_"
    
    def reversed(self) -> "MWorksheetsCmdChange":
        return MWorksheetsCmdChange(self.wsuuid, self.cmduuid, self.cmdname, oldselected=self.newselected, newselected=self.oldselected)


class MWorksheetsCmdDelete(MJournalChange):
    """ Delete a command.  """
    def __init__(self, wsuuid: str, cmduuid: str, cmdname: str, oldselected: dict, when:MZdatetime = None):
        super().__init__(when)
        self.wsuuid = wsuuid
        self.cmduuid = cmduuid
        self.cmdname = cmdname
        self.oldselected = oldselected

    def msgParams(self) -> dict:
        return {
            "cmdUuid": self.cmduuid,
            "sheetUuid": self.wsuuid,
            "oldcmd": self.oldselected,
            "newcmd": {},
            "routing": True
        }
        
    def msgType(self) -> str:
        return "_cmdReq_"

    def reversed(self) -> "MWorksheetsCmdAdd":
        return MWorksheetsCmdAdd(self.wsuuid, self.cmduuid, self.cmdname, newselected=self.oldselected)


class MWorksheetsCmdAdd(MJournalChange):
    """ Add a command.  """
    def __init__(self, wsuuid: str, cmduuid: str, cmdname: str,
                 newselected: dict, when:MZdatetime = None):
        super().__init__(when)
        self.wsuuid = wsuuid
        self.cmduuid = cmduuid
        self.cmdname = cmdname
        self.newselected = newselected

    def msgParams(self) -> dict:
        return {
            "cmdUuid": self.cmduuid,
            "sheetUuid": self.wsuuid,
            "oldcmd": {},
            "newcmd": self.newselected,
            "routing": True
        }

    def msgType(self) -> str:
        return "_cmdReq_"

    def reversed(self) -> "MWorksheetsCmdDelete":
        return MWorksheetsCmdDelete(self.wsuuid, self.cmduuid, self.cmdname, oldselected=self.newselected)


class MWorksheetsSheetChange(MJournalChange):
    """
    A change to a worksheet.
    """
    def __init__(self, wsuuid: str, oldname:str, worksheetname: str, when:MZdatetime = None):
        super().__init__(when)
        self.wsuuid = wsuuid
        self.oldname = oldname
        self.worksheetname = worksheetname

    def fromJson(j: dict):
        return MWorksheetsSheetChange(**j)
    
    def __str__(self):
        return self.when.strftime(short=True)+" sheet : "+self.worksheetname

    def msgParams(self) -> dict:
        return {
            "sheetUuid": self.wsuuid,
            "oldname": self.oldname,
            "newname": self.worksheetname,
            "routing": True
        }

    def msgType(self) -> str:
        return "_sheetReq_"

    def reversed(self) -> "MWorksheetsSheetChange":
        return MWorksheetsSheetChange(self.wsuuid, oldname=self.worksheetname, worksheetname=self.oldname)


class MWorksheetsChangeFactory(MJournalChangeFactory):
    def make(j: dict):
        if not j:
          return None
        t = j["type"]
        if t == "MWorksheetsCmdChange":
            return MWorksheetsCmdChange(**MJournalChangeFactory.jsonToDict(j))
        if t == "MWorksheetsCmdAdd":
            return MWorksheetsCmdAdd(**MJournalChangeFactory.jsonToDict(j))
        if t == "MWorksheetsCmdDelete":
            return MWorksheetsCmdDelete(**MJournalChangeFactory.jsonToDict(j))
        if t == "MWorksheetsSheetChange":
            return MWorksheetsSheetChange(**MJournalChangeFactory.jsonToDict(j))
        if t == "MJournalRebase":
            return MJournalRebase(**MJournalChangeFactory.jsonToDict(j))
        return super(j)


class MCmd:
    """
    Wrapper for command dictionary, to access dictionary using methods.
    """
    @staticmethod
    def name(cmd: dict):
        """ Get the type/name of the command """
        return cmd["cmd"]

    @staticmethod
    def uuid(cmd: dict):
        """ Get the unique name for the command """
        return cmd["uuid"]


class MWorksheets:
    """
  MWorksheets: a language of data grooming.
  Data is groomed as it flow through commands and a worksheet is a collection
  of commands. Commands are uniquely identified by a uuid. Users connect
  to a database and the commands in the database are synchronized with the
  local copy of the commands. The local commands are what the user thinks are
  in the database which may be different due to other users changes.
    """
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
        self.keyfields =  ["type", "desc", "choice", "eg", "default"]
        self.dir = dir
        if not os.path.isdir(self.dir):
            raise Exception("Failed to find worksheet dir " + self.dir)
        # Read schema.
        self.schemaPath = os.path.join(self.dir, "worksheetHelp.json")
        if not os.path.exists(self.dir):
            os.mkdir(self.dir)
        if not os.path.exists(self.schemaPath):
            self.changeSchema({})
        else:
            with open(self.schemaPath,"r") as f:
                try:
                    self.schema = json.load(f)
                except json.JSONDecodeError as e:
                    raise Exception("JSON error in " + self.schemaPath + " " + str(e))
                except Exception as e:
                    raise Exception("Failed to parse " + self.schemaPath + " " + str(e))
        self.wsl = []
        self.ws = {}
        self.wsname = {}
        self.feedNames = set()
        self.changesPath = os.path.join(self.dir,".changes")
        self.changes = MJournal(self.changesPath,MWorksheetsChangeFactory)
        if self.changes.isempty():
            self.__readWorksheets(self.dir)
        else:
            self.__readWorksheets(self.changes.currentPath())

    def changeSchema(self, schema: dict):
        """ Replace schema without any validation of current commands against the new schema. """
        with open(self.schemaPath,"w") as f:
            json.dump(schema,f)
        self.schema = schema

    def copySchema(self, dir:str):
        """ Copy the worksheets schema to another directory.
        """
        shutil.copy(self.schemaPath,dir)

    def empty(self):
        """
        Empties the worksheet that's in memory,
        then call save() to erase the disk copy.
        """
        self.changes.trash()
        self.__readWorksheets(dir=self.dir)

    def isEmpty(self) -> bool:
        """
        Return True when there are no worksheets in memory.
        """
        if self.ws:
            return False
        return True
        
    def __readWorksheets(self, dir:str):
        """ Builds worksheets from directory. """
        self.wsl = []
        self.ws = {}
        self.wsname = {}
        self.feedNames = set()
        self.feeds = {}
        if not dir:
            return
        for fn in os.listdir(path=dir):
            if fn == "worksheetHelp.json":
                continue
            if not fn.endswith(".json"):
                continue
            name=fn[:-5]
            dfn = os.path.join(dir,fn)
            try:
                with open(dfn, "r") as f:
                    j = json.load(f)
                j["filename"] = fn
                if j["name"] != name:
                    raise Exception("Failed : worksheet name "+j["name"]+" not matching filename "+name)
                self.ws[j["uuid"]]  = j
                self.wsname[name] = j
                self.wsl.append(j)
                j["uuidcmds"] = {}
                for cmdj in j["cmds"]:
                    j["uuidcmds"][cmdj["uuid"]] = cmdj
                error = self.verifycmds(j["cmds"])
                if error:
                    raise Exception(error)
            except json.JSONDecodeError as err:
                raise Exception("Failed to parse " + dfn + " " + str(err))
            except Exception as e:
                traceback.print_exc()
                raise Exception("Failed to parse " + dfn + " " + str(e))
        self.expandcmds()
        for ws in self:
            for cmdj in ws["cmds"]:
                feeds = self.cmdFeedRef(cmdj)
                if len(feeds) == 0:
                    cmdj["__state__"] = "pending"
                else:
                    cmdj["__state__"] = "blocked"
                feeds = self.cmdFeed(cmdj)
                for feed in feeds:
                    if feed in self.feeds:
                        raise Exception("Duplicate feeds "+feed+" in "+ws["uuid"])
                    self.feeds[feed] = (ws["uuid"], cmdj["uuid"])
        self.cmdUuidToCmd = {}
        for ws in self:
            for cmdj in ws["cmds"]:
                self.cmdUuidToCmd[cmdj["uuid"]] = cmdj
                feeds = self.cmdFeedRef(cmdj)
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
                            raise Exception("Unknown feed "+feed+" in worksheet \""+ws["uuid"] +"\" did you mean \"" + nearest + "\"?")
                        else:
                            raise Exception("Unknown feed "+feed+" in "+ws["uuid"])

    def findCmd(self, sheetuuid: str, cmduuid: str, feed:str) -> dict:
        """
        Return the cmd that matches the constraints of sheetuuid
        and/or cmduuid and/or feed name.
        """
        if cmduuid:
            cmd = self.getCmdUuid(cmduuid)
            if not cmd:
                return None
            if sheetuuid and sheetuuid != self.getWorkSheetUuid(cmduuid):
                return None
            if feed:
                if cmd != self.getCmd(feed):
                    return None
            return cmd
        elif feed:
            cmd = self.getCmd(feed)
            if not cmd:
                return None
            if sheetuuid and sheetuuid != self.getWorkSheetUuid(cmduuid):
                return None
            return cmd
        elif sheetuuid: # If there is one cmd in the sheet.
            sheet = self.ws.get(sheetuuid,None)
            if not sheet:
                return None
            cmds = sheet["cmds"]
            if len(cmds) == 1:
                return cmds[0]
        return None

    def getWorkSheetCmds(self, sheetuuid: str) -> dict:
        sheet = self.ws[sheetuuid]
        for cmd in sheet["cmds"]:
            yield cmd

    def getWorkSheetUuid(self, cmduuid: str) -> str:
        for ws in self:
            for cmd in ws["cmds"]:
                if cmd["uuid"] == cmduuid:
                    return ws["uuid"]
        return None

    def __str__(self) -> str:
        s = "List of Sheets and their commands and the feed(s) they consume and output\n"
        if self.isEmpty():
            s += "No worksheets\n"
        for ws in self:
            s += "Sheet(" + ws["name"]+":"+ws["uuid"]+")\n"
            for cmd in ws["cmds"]:
                s += cmd["uuid"]+" "+str(self.cmdFeedRef(cmd))+">"+ cmd["cmd"] + ">" + str(self.cmdFeed(cmd)) + "\n"
        s += "--++Change log++--\n"
        s += str(self.changes)
        return s

    def __iter__(self):
        return iter(self.wsl)
        
    def status(self, ready: bool = True) -> str:
        s = ""
        if ready:
            for feed in self.feeds:
                cmd = self.getCmd(feed)
                if cmd["__state__"] == "pending":
                    s += "    " + feed + " " + cmd["__state__"] + "\n"
        else:
            for feed in self.feeds:
                cmd = self.getCmd(feed)
                if cmd["__state__"] == "blocked":
                    s += "    " + feed + " " + cmd["__state__"] + "\n"
        return s
    
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

    def expandcmd(self, cmd: any, cmdname: str) -> None:
        self.expandingcmd = cmd
        self._expandcmd(cmd, self.schema[cmdname])
        
    def expandcmds(self) -> None:
        for ws in self:
            for cmdj in ws["cmds"]:
                cmdname = cmdj["cmd"]
                self.expandingcmd = cmdj[cmdname]
                self._expandcmd(self.expandingcmd, self.schema[cmdname])

    def cmd_titles(self) -> list:
        return [x for x in self.schema.keys() if x not in self.keyfields and not x.endswith(".macro") and not x.startswith("_")]

    def cmd_descriptions(self) -> list:
        return {name: self.schema[name]["desc"] for name in self.schema.keys() if name not in self.keyfields and not name.endswith(".macro")}

    def getSheetName(self,uuid:str) -> str:
        """ get Worksheet from uuid. """
        return self.ws.get(uuid,{}).get("name",None)

    def titles(self) -> list:
        """ Worksheet titles. """
        return [self.ws[uuid]["name"] for uuid in self.ws.keys()]

    def title(self,uuid:str) -> str:
        """ Worksheet title. """
        return self.ws.get(uuid,{"name":""})["name"]

    def uuidAtIdx(self, idx: int) -> str:
        """ Return worksheet at uuid index, see titles() """
        return list(self.ws.keys())[idx]

    def sheet(self, title: str) -> dict:
        return self.ws[title]

    def sheetCmds(self, title: str) -> dict:
        return self.ws[title]["cmds"]

    def updateSheet(self, uuid:str, oldtitle:str, title: str, changelog: bool=True) -> str:
        """ Create a worksheet, or change the title for an existing worksheet. """
        if uuid in self.ws:
            if oldtitle != self.ws[uuid]["name"]:
                return "wrong version"
            if title == self.ws[uuid]["name"]:
                return "no change"
            if title:
                self.ws[uuid]["name"] = title
            else:
                self.wsl.remove(self.ws[uuid])
                del self.ws[uuid]
        else:
            if oldtitle is not None:
                return "redirect" # Redirect towards the congregation with the sheet.
            # TODO; why should the new sheet be added here?????
            self.ws[uuid] = {"name":title, "uuid": uuid, "cmds":[]}
            self.wsl.append(self.ws[uuid])
        if changelog:
            self.save(self.changes.add(MWorksheetsSheetChange(uuid,oldtitle,title)))
        if not oldtitle:
            return "created"
        if not title:
            return "deleted"
        return "updated"

    def inputCmdOutput(self, title: str) -> list:
        rows=[]
        for cmd in self.ws[title]["cmds"]:
            inputs = "\n".join(self.cmdFeedRef(cmd))
            rows.append([
                inputs,
                cmd["cmd"],
                "\n".join(self.cmdFeed(cmd))
                ])
        return rows

    def _paramsComposite(
        self, at: str, cmd: any, parent: str, schema: any,
        params: dict, selected: dict, description: dict
    ) -> bool:
        retval = False
        for k in schema.keys():
            if k in self.keyfields:
                continue
            nxtcmd = None
            if cmd is not None:
                nxtcmd = cmd.get(k,None)
                # if nxtcmd is None:
                #     continue
            if nxtcmd is not None:
                field = parent+"."+k
                if len(parent) == 0:
                    field = k
                if self._paramscmd(at, nxtcmd, field, schema[k], params, selected, description):
                    retval = True
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

    def _paramscmd(
        self, at: str, cmd: any, parent: str, schema: any,
        params: dict, selected: dict, description: dict
    ) -> bool:
        """
 Return True when cmd has at least one field in the substructure, this
 is used by parent option to determine if the command has activated this
 substructure as an option.
        """
        if not cmd:
            return False
        nxtat = at
        # print("paramscmd at=" + str(at) + " parent=" + str(parent)+" cmd="+str(cmd))
        if at is not None and parent:  # Searching for a subtree.
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
            selected[p] = cmd
        if t == "str" and "choice" in schema:
            params[parent] = schema["choice"]
            if cmd is not None:
                selected[parent] = cmd
            elif "default" in schema:
                selected[parent] = schema["default"]
        elif t in ["feed", "feedRef", "path", "field", "str", "email", "fmt", "any", "regex"]:
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
        elif t.endswith(".macro"):
            if cmd is not None:
                return self._paramscmd(at, cmd, parent, self.schema[t], params, selected, description)
        else:
            print(cmd)
            print(schema)
            raise Exception("Unexpected type " + t)
        if "desc" in schema:
            description[parent] = schema["desc"]
        if "default" in schema and schema["default"] is None:
            # Option is true when there is a value in cmd in the sub-tree.
            opt = parent+".option"
            selected[opt] = retval
        return retval

    
    def paramsCmd(self, cmd: dict, at: str) -> (dict, dict, dict):
        """
 paramsCmd: Get params from schema for the field "at".
 "at" is the type/name of the command, for example, "file".
 1st returned dict, params, is the field name and type.
 2nd returned dict, selected, is the values from cmd, or the default value when there is no
 value in cmd.
 3rd returned dict, desc, is the description of the field.
 Usage:
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
        """ Get command by feed names in outputs separated by return. """
        (wsuuid, cmduuid) = self.feeds[outputs.split("\n")[0]]
        return self.ws[wsuuid]["uuidcmds"][cmduuid]
    
    def getCmdUuid(self, uuid: str) -> dict:
        """ Get command by UUID. """
        return self.cmdUuidToCmd.get(uuid)

    def getCmdUuidWS(self, cmduuid: str) -> str:
        """ Get command worksheet UUID. """
        for ws in self:
            for cmdj in ws["cmds"]:
                if cmdj["uuid"] == cmduuid:
                    return ws["uuid"]
        return None

    def deleteCmdUuidWS(self, cmduuid: str) -> None:
        """ Deleted command and get worksheet by command UUID. """
        for ws in self:
            cmdidx = 0
            for cmdj in ws["cmds"]:
                if cmdj["uuid"] == cmduuid:
                    break
                cmdidx += 1
            if cmdj["uuid"] == cmduuid:
                del ws["cmds"][cmdidx]
                return

    def nextCmdUuid(self, cmduuid: str) -> str:
        """ Return the next cmd UUID after the previous cmd UUID. """
        found = False
        for ws in self:
            for cmd in ws["cmds"]:
                if not cmduuid or found:
                    return cmd["uuid"]
                found = (cmd["uuid"] == cmduuid)
        return None

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
        if cmd is None:
            cmd = {}
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
                traceback.print_exc()
                raise MWorkSheetException("field \""+field+"\" bad value \""+str(t)+"\" ")
        return cmd

    def _updateListComposite(
        self, cmd: any, parent: str, schema: any, selected: dict
    ) -> any:
        fields = []
        for k in selected.keys():
            if k.startswith(parent):
                if k[k.rindex(".")+1:].isdigit():
                    fields.append(k)
        if cmd is None:
            cmd = []
        for i, j in enumerate(cmd):
            field = parent+"."+str(i)
            if field in fields:
                fields.remove(field)
            if field not in selected:
                # Delete.
                del cmd[i]
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
                if not cmd or k not in cmd:
                    cmd = {k: {}}
            cmd = self.update_handlers[t](cmd, parent, schema, selected)
            return cmd
        elif t.endswith(".macro"):
            if t not in self.schema:
                raise Exception("Unknown macro named " + t)
            cmd = self._updatecmd(cmd, parent, self.schema[t], selected)
            return cmd
        else:
            raise Exception("Unexpected type " + t)

    def updateCmd(self, wsn: str, cmdUuid: str, cmdname: str,
                  oldselected: dict, selected: dict, changelog:bool=True) -> str:
        """ Update values in command from selected values.
            Inserts the selected values into the change log at the current
            position. Saves the version of the worksheet such that a call
            to undo() will go back to the prior version (the version before
            the change).
        """
        cmd = self.getCmdUuid(uuid=cmdUuid)
        if cmd:
            if changelog:
                if selected:
                    self.save(self.changes.add(MWorksheetsCmdChange(wsn,cmdUuid,cmdname,oldselected,selected)))
        else:
            cmd = {}
            if changelog:
                self.save(self.changes.add(MWorksheetsCmdAdd(wsn,cmdUuid,cmdname,selected)))
        if cmd:
            backup = copy.deepcopy(cmd)
            (params, cmdselected, description) = self.paramsCmd(cmd,at=None)
            if oldselected != cmdselected:
                return "wrong version"
            # Remove command from all the feeds.
            for feed in self.cmdFeed(cmd):
                del self.feeds[feed]
            if not selected:
                error = self.deleteCmd(cmdUuid,changelog)
                changelog = False
            else:
                cmd[cmdname] = self._updatecmd(
                    cmd[cmdname], parent=cmdname, schema=self.schema[cmdname],
                    selected=selected)
        else:
            backup = None
            cmd[cmdname] = self._updatecmd(
                None, parent=cmdname, schema=self.schema[cmdname],
                selected=selected)
            cmd["uuid"] = str(uuid.uuid4())
            cmd["cmd"] = cmdname
            self.cmdUuidToCmd[cmd["uuid"]] = cmd
        error = ""
        if not backup:
            self.ws[wsn]["cmds"].append(cmd)
        try:
            feeds = self.cmdFeed(cmd)
        except KeyError as e:
            error = "Bad feed name variable: " + str(e)
        except Exception as e:
            error = "Bad feed name " + type(e).__name__ + " " + str(e)
        undofeeds = []
        if not error:
            try:
                for feed in feeds:
                    if feed in self.feeds:
                        error = "duplicate feed name " + feed
                        break
                    undofeeds.append(feed)
                    self.feeds[feed] = (wsn, cmd)
                if not error:
                    error = self.verifycmds(self.ws[wsn]["cmds"])
                    self.expandingcmd = cmd[cmdname]
                    self._expandcmd(self.expandingcmd, self.schema[cmdname])
            except Exception as e:
                # traceback.print_exc()
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
                del self.ws[wsn]["cmds"][-1]
        elif changelog:
            self.save(self.changes.add(MWorksheetsCmdChange(wsn,cmd["uuid"],cmdname,oldselected,selected)))
        return error

    def save(self, dir:str):
        """ Save worksheets to disk """
        for ws in self:
          with open(os.path.join(dir,f'{ws["name"]}.json'), "w") as f:
              f.write(json.dumps(ws, indent=4))
        with open(os.path.join(dir,"worksheetHelp.json"), "w") as f:
          f.write(json.dumps(self.schema, indent=4))

    def deleteCmd(self, cmduuid: str, changelog:bool=True) -> str:
        cmd = self.getCmdUuid(cmduuid)
        if not cmd:
            return f"Cannot find command {cmduuid}"
        if changelog: # Save sheet before the change.
            wsuuid = self.getCmdUuidWS(cmduuid)
            self.save(self.changes.add(MWorksheetsCmdDelete(wsuuid,cmduuid,cmd["cmd"],selected={})))
        self.deleteCmdUuidWS(cmduuid)
        for feed in self.cmdFeed(cmd):
            if feed in self.feeds:
                del self.feeds[feed]
        return None

    def deleteCmdByOutputs(self, wsn: str, outputs: str) -> None:
        cmd = self.getCmd(outputs)
        self.deleteCmd(cmd["uuid"])

    def addChanges(self, other: "MWorksheets") -> bool:
        """
        Adds changes to self, for each different sheet and cmd detected in other.
        """
        changes = 0
        for ows in other: # Thru other's sheet.
            sws = self.ws.get(ows["uuid"],None)
            if not sws: # New worksheet.
                #print(f"NEW WORKSHEET {ows}")
                changes += 1
                self.changes.add(MWorksheetsSheetChange(ows["uuid"],None,ows["name"]))
            else:
                if sws["name"] != ows["name"]: # Sheet has a new name.
                    #print(f'NEW WORKSHEET NAME {sws["uuid"]} {sws["name"]} {ows["name"]}')
                    changes += 1
                    self.changes.add(MWorksheetsSheetChange(sws["uuid"],sws["name"],ows["name"]))
            for ocmd in ows["cmds"]: # Thru other's cmds
                (params, oselected, description) = other.paramsCmd(ocmd,at=None)
                scmd = self.getCmdUuid(ocmd["uuid"])
                if scmd: # self has other's cmd.
                    (params, sselected, description) = self.paramsCmd(scmd,at=None)
                    if oselected == sselected: # No change to the command.
                        continue
                    #print(f"NEW UPDATED CMD {ocmd} {scmd}")
                    #print(f"{oselected} {sselected}")
                    self.changes.add(MWorksheetsCmdChange(ows["uuid"],ocmd["uuid"],ocmd["cmd"],sselected,oselected))
                else:
                    #print(f"NEW CMD {ocmd}")
                    self.changes.add(MWorksheetsCmdAdd(ows["uuid"],ocmd["uuid"],ocmd["cmd"],oselected))
                changes += 1
        return changes > 0

    def pull(self, worksheetdir:str):
        """
        Put the worksheets into the root of the change log.
        Walk thru each command, creating new changes for any difference.
        Version is not relevant. DB is the master. The local copy is the
        changes that need to be deployed to upgrade the DB.
        TODO; with local changes, current is forgotten, and moved to the empty head when there are changes.
        """
        # Delete all change prior to current root.
        oldcurrent = self.changes.current()
        oldcurrentPath = self.changes.currentPath()
        self.changes.prune()
        oldroot = MWorksheets(self.dir)
        #oldroot = MWorksheets(oldcurrentPath)
        # Add worksheets as the new root.
        newroot = self.changes.insertRoot(MJournalRebase(worksheetdir))
        # Save DB as the new root
        ws = MWorksheets(worksheetdir)
        ws.__readWorksheets(worksheetdir)
        ws.save(newroot)
        self.__readWorksheets(newroot)
        if oldroot:
            # Add local changes for difference between new Root and old root
            if not self.addChanges(oldroot):
                # Delete the above MJournalRebase
                self.changes.rewind()
                self.changes.delete()
                while self.changes.current() != oldcurrent:
                    self.changes.up()
            else:
                # Rewind to the oldest change, which is back to the new root.
                self.changes.rewind()

    def getCurrentChange(self) -> (str,dict):
        """ Return the wsuuid and cmd for the first change .
        """
        current = self.changes.current()
        self.changes.rewind()
        if self.changes.current() == current:
            return ()
        change = self.changes.currentChange()
        while self.changes.current() != current:
            self.changes.up()
        return (change.ws,change.cmd)
    
    def listChanges(self) -> list:
        """ Return a list of changes. """
        return self.changes.getChanges()

    def push(self) -> None:
        """ Push first change as the root of the chain.
        """
        current = self.changes.current()
        self.changes.rewind()
        if self.changes.current() == current:
            raise Exception("Trying to push beyond current")
        self.changes.delete()
        while self.changes.current() != current:
            self.changes.up()

    def undo(self) -> bool:
        """ Undo the current change.
        """
        if not self.changes.current():
            return False
        self.__readWorksheets(self.changes.currentPath())
        self.changes.down()
        return True

    def redo(self) -> str:
        """ Redo the next change. """
        wsc = self.changes.nextChange()
        if type(wsc) in [MWorksheetsCmdChange,MWorksheetsCmdDelete,MWorksheetsCmdAdd]:
            cmd = self.getCmdUuid(wsc.cmduuid)
            oldselected = {}
            if cmd:
                (params, oldselected, description) = self.paramsCmd(cmd,at=None)
            error = self.updateCmd(wsc.wsuuid,wsc.cmduuid,wsc.cmdname,oldselected,wsc.newselected,changelog=False)
            if error:
                return error
        elif type(wsc) == MWorksheetsSheetChange:
            self.updateSheet(wsc.wsuuid, wsc.oldname, wsc.worksheetname,changelog=False)
        elif type(wsc) == MJournalRebase:
            return "Cannot redo a rebase which is the base for subsequent changes"
        self.changes.up()
        self.save(self.changes.currentPath())
        return ""

    def wsnCurrentChange(self) -> str:
        """ Return the worksheet uuid if the current change created the worksheet. """
        c = self.changes.currentChange()
        if type(c) == MWorksheetsSheetChange:
            return c.wsuuid
        return None
    
    def deleteNextChange(self) -> None:
        """ Deletes the next change. """
        self.changes.delete()

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
        if cmd is None:
            return
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

    def cmdFeed(self, cmd: dict) -> list:
        """ Return a list of names of feeds that the command outputs. """
        cmdname = cmd["cmd"]
        feeds = []
        self.expandingcmd = cmd[cmdname]
        self._feedcmd(self.expandingcmd, self.schema[cmdname], feeds)
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
        # print("_feedRefcmd "+str(cmd)+" "+str(schema))
        t = schema["type"]
        if t == "feedRef" and cmd is not None:
            feeds.append(cmd)
        if t in self.feed_handlers:
            self.feedRef_handlers[t](cmd, schema, feeds)

    def cmdFeedRef(self, cmd: any) -> list:
        """ Return a list of names of feed references that the command inputs. """
        feeds = []
        cmdname = cmd["cmd"]
        self._feedRefcmd(cmd[cmdname], self.schema[cmd["cmd"]], feeds)
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

    def _Error(self, stack: list, error:str) -> str:
        cf = currentframe()
        traceback.print_stack()
        return "Error"+str(cf.f_back.f_lineno)+" at "+".".join(stack)+" "+error

    def _verifyComposite(self, stack: list, cmd: any, schema: any) -> str:
        if not isinstance(cmd, dict):
            return self._Error(stack, "\nExpecting " + str(schema) + "\ngot: " + str(cmd))
        if "key" in schema:
            return self._Error(stack, "\nUnexpected key in " + str(schema))
        for k in cmd.keys():
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
        """ Verify command against the Schema. """
        name = cmd["cmd"]
        if name not in self.schema:
            return self._Error([], "Unexpected cmd name " + name)
        error = self._verifycmd([name], cmd[name], self.schema[name])
        if error:
            return "Error in cmd " + name + " " + error
        else:
            return ""

    def verifycmds(self, j: list) -> str:
        """ Verify commands against the Schema. """
        for cmd in j:
            error = self.verifycmd(cmd)
            if error:
                return error
        return ""

    def blocked(self) -> list:
        """ Return a list of cmds that are blocked. """
        return [cmd for feed,cmd in self.feeds.items() if cmd["__state__"] == "blocked"]

    def pending(self) -> dict:
        """ Return a list of cmds that are pending. """
        for feed,cmd in self.feeds.items():
            if cmd["__state__"] == "pending":
                return cmd
        return None

    def ran(self, cmd) -> list:
        """ Returns list of newly pending commands """
        feeds = self.cmdFeed(cmd)
        cmds = []
        for feed in feeds:
            cmd = self.feeds[feed]
            cmd["__state__"] = "ready"
            for cmd in self.feeds.values():
                if cmd["__state__"] == "blocked":
                    cmd["__state__"] = "pending"
                    for feed in self.cmdFeedRef(cmd):
                       if self.feeds[feed]["__state__"] != "ready":
                           cmd["__state__"] == "blocked"
                           break
                    if cmd["__state__"] == "pending":
                        cmds.append(cmd)
        return cmds

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Worksheet")
        parser.add_argument('dir', help="worksheet dir")
        parser.add_argument('backup', help="worksheet backup dir")
        parser.add_argument('master', help="worksheet master copies")
        args = parser.parse_args()
        try:
            print(args.dir)
            ws = MWorksheets(args.dir)
            print("Worksheet before pull")
            ws.expandcmds()
            print(ws)
            ws.pull(args.master)
            print(f"Pulled {args.master}, worksheet after pull")
            print(ws)
        except Exception:
            traceback.print_exc()
            return
        at="files"
        outputs = "directory.files.pbx"
        (d_params, d_defaults, d_desc) = ws.paramsCmd(None,at)
        cmd = ws.getCmd(outputs)
        (params, selected, description) = ws.paramsCmd(cmd,at)
        print("selected:")
        print(selected)
        print("params")
        print(d_params)
        print(params)
        print("d_defaults:")
        print(d_defaults)
        for idx, title in enumerate(ws.titles()):
            print("Sheet:" + title)
            for cmd in ws.sheet(ws.uuidAtIdx(idx))["cmds"]:
                print("      " + cmd["cmd"] + ":" + str(ws.cmdFeed(cmd)))
        print("Feeds ready to run")
        for feed in ws.feeds:
            cmd = ws.getCmd(feed)
            if cmd["__state__"] == "pending":
                print("    " + feed + " " + cmd["__state__"])
        print("Feeds blocked")
        for feed in ws.feeds:
            cmd = ws.getCmd(feed)
            if cmd["__state__"] == "blocked":
                print("    " + feed + " " + cmd["__state__"])
        ws.save(args.backup)
        print("Save to dir named:"+args.backup)
        # add cmd
        (params, oldselected, description) = ws.paramsCmd(cmd,at=None)
        selected  = {}
        print(ws)
        print(f"Deleting cmd {cmd}")
        print(f"oldselected {oldselected}")
        print("Update cmd:"+ws.updateCmd(ws.getWorkSheetUuid(cmd["uuid"]), cmd["uuid"],cmd["cmd"], oldselected,selected))
        print(ws)
        print("UNDO the delete")
        ws.undo()
        print(ws)
        print("REDO the delete")
        ws.redo()
        print(ws)


if __name__ == "__main__":
    MWorksheets.main()