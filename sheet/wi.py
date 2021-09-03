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
# Window interface for the sheet.
# Usage:
# export PYTHONPATH=.
# python3 sheet/wi.py
import argparse
import traceback
import copy

# noinspection PyBroadException
try:
    import wx
    import wx.grid
except Exception:
    print("Failed to import wx, install instructions:")
    print("sudo apt-get install -y libsdl2-2.0-0")
    print("sudo apt-get install libgtk-3-dev")
    print("pip3 install -U -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-18.04 wxPython")
    exit(1)

from magpie.src.mworksheets import MWorksheets


class Params:
    def __init_(self):
        self.d = {}

    def add(self, name: str, val: str, typ: str) -> None:
        self.d[name] = (val, typ)

    def val(self, name) -> any:
        return self.d[name][0]

    def typ(self, name) -> str:
        return self.d[name][1]

    def addBulk(self, other: "Params"):
        for f, v in other.d.items:
            self.d.add(f, v[0], v[1])

    def getBulk(self) -> (any, str, str):
        for k, v in sorted(self.d.items()):
            yield k, v[0], v[1]
            
    def find(self, k:str) -> bool:
        return k in self.d

class NamedButton(wx.Button):
    def __init__(self, parent, title: str, name:str):
        wx.Button.__init__(self, parent, label=title)
        self.name = name
    
class QueryParams(wx.Frame):
    def __init__(self, parent, title: str, style: int, params: dict, selected: dict, verify: any, descriptions: dict):
        wx.Dialog.__init__(self, parent=parent, title=title)
        self.verify = verify
        self.params = {}
        self.titles = {}
        self.desc = {}
        self.res = wx.OK
        self.panel = wx.Panel(self)
        self.vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        if style & wx.NO:
            self.noButton = wx.Button(self.panel, label="NO")
            self.noButton.Bind(wx.EVT_BUTTON, self.on_no)
            hbox.Add(self.noButton,proportion=1, flag=wx.EXPAND)
        if style & wx.CANCEL:
            self.deleteButton = wx.Button(self.panel, label="DELETE")
            self.deleteButton.Bind(wx.EVT_BUTTON, self.on_delete)
            hbox.Add(self.deleteButton, proportion=1, flag=wx.EXPAND)
        if style & wx.OK:
            self.okButton = wx.Button(self.panel, label="OK")
            self.okButton.Bind(wx.EVT_BUTTON, self.on_ok)
            hbox.Add(self.okButton, proportion=1, flag=wx.EXPAND)
        if style & wx.YES:
            self.yesButton = wx.Button(self.panel, label="YES")
            self.yesButton.Bind(wx.EVT_BUTTON, self.on_yes)
            hbox.Add(self.yesButton, proportion=1, flag=wx.EXPAND)
        if style & wx.CAPTION:
            self.verifyButton = wx.Button(self.panel, label="VERIFY")
            self.verifyButton.Bind(wx.EVT_BUTTON, self.on_verify)
            hbox.Add(self.verifyButton, proportion=1, flag=wx.EXPAND)
        self.vbox.Add(hbox, proportion=1, flag=wx.EXPAND)
        self.choices = {}
        self.selectedchoices = []
        for name, typ in params.items():
            value = selected.get(name, "")
            if typ == "str":
                self.params[name] = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE, value=value)
            elif typ == "addbutton":
                self.params[name] = NamedButton(self.panel, "ADD", name)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_addButton)
            elif typ == "deletebutton":
                self.params[name] = NamedButton(self.panel, "DELETE", name)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_deleteButton)
            elif typ == "int":
                self.params[name] = wx.TextCtrl(self.panel, value=value)
            elif typ == "YYYYMMDD HH:MM:SS":
                self.params[name] = wx.TextCtrl(self.panel, value=value)
            elif typ == "password":
                self.params[name] = wx.TextCtrl(self.panel, value=value)
            elif isinstance(typ, list):  # Choice
                if len(value) == 0:
                    value = typ[0]  # No selection, default to first choice.
                self.selectedchoices.append((name, name+"."+value))
                self.params[name] = wx.ComboBox(self.panel, choices=typ)
                # on_choice need the name in order to show and hide params.
                # TODO; subclass ComboBox, add name into the object.
                self.choices[self.params[name].GetId()] = name
                self.params[name].SetValue(value)
                self.params[name].Bind(event=wx.EVT_COMBOBOX, handler=self.on_choice)
            else:
                raise Exception("Exception unknown type=" + str(typ))
            hbox = wx.BoxSizer(wx.HORIZONTAL)
            self.titles[name] = wx.StaticText(self.panel, -1, name)
            hbox.Add(self.titles[name], proportion=1, flag=wx.ALIGN_LEFT | wx.ALL) 
            hbox.Add(self.params[name], proportion=1, flag=wx.EXPAND)
            if name in descriptions:
                self.desc[name] = wx.TextCtrl(self.panel, value=descriptions[name], style=wx.TE_MULTILINE|wx.TE_READONLY)
                hbox.Add(self.desc[name], proportion=1, flag=wx.EXPAND)
            self.vbox.Add(hbox, proportion=1, flag=wx.EXPAND)
            if not self.fieldShow(name):
                self.params[name].Hide()
                self.titles[name].Hide()
                self.desc[name].Hide()
        self.panel.SetSizer(self.vbox)
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()

    def getSelected(self) -> dict:
        selected = {}
        for name, e in self.params.items():
            selected[name] = e.GetValue()
        return selected

    def fieldShow(self, fieldname: str) -> bool:
        for choicename, selectedname in self.selectedchoices:
            if fieldname.startswith(choicename):
                if fieldname == choicename:
                    return True
                if not fieldname.startswith(selectedname):
                    return False
        return True

    def setChoice(self, name: str, value: str) -> None:
        l = []
        for choicename, selectedname in self.selectedchoices:
            if choicename == name:
                l.append((name, name + "." + value))
            else:
                l.append((choicename, selectedname))
        self.selectedchoices = l

    def getValue(self, name: str, typ: str) -> (any, str):
        if typ == "str":
            return self.params[name].GetValue(), typ
        elif typ == "int":
            # noinspection PyBroadException
            try:
                return int(self.params[name].GetValue()), typ
            except Exception:
                return -1
        elif typ == "YYYYMMDD HH:MM:SS":
            return self.params[name].GetValue(), typ
        elif typ == "password":
            v = self.params[name].GetValue()
            if v:
                # Cut'n'paste the password adds a return to the end.
                if v[-1] == "\n":
                    return v[0:-1], typ
            return v, typ
        else:
            raise ("Exception unknown type=" + typ)

    def on_no(self, _event):
        self.res = wx.NO
        self.Destroy()

    def on_delete(self, _event):
        self.res = wx.CANCEL
        self.Destroy()

    def on_yes(self, _event):
        self.res = wx.YES
        self.Destroy()

    def on_ok(self, _event):
        self.res = wx.OK
        self.Destroy()

    def on_verify(self, _event):
        try:
            self.verify(self)
        except Exception as e:
            wx.MessageBox(
                "Faild:"+e.__class__.__name__+":"+str(e),
                "verification",
                wx.OK, self)
            return
        wx.MessageBox("Passed", "verification", wx.OK, self)

    def on_choice(self, event):
        cb = event.GetEventObject()
        self.setChoice(self.choices[cb.GetId()], cb.GetValue())
        for n in self.params.keys():
            if self.fieldShow(n):
                self.params[n].Show()
                self.titles[n].Show()
                self.desc[n].Show()
            else:
                self.params[n].Hide()
                self.titles[n].Hide()
                self.desc[n].Hide()
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()

    def on_deleteButton(self, event) -> None:
        b = event.GetEventObject()
        for n in self.params.keys():
            if n.startswith(b.name):
                self.params[n].Hide()
                self.titles[n].Hide()
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()

    def on_addButton(self, event) -> None:
        b = event.GetEventObject()
        prev = None
        for n in self.params.keys():
            if n.startswith(b.name):
                if self.params[n].GetLabel() == "DELETE":
                   prev = n
        i = prev.rfind(".")+1
        next = prev[0:i] + str(int(prev[i:]) + 1)
        i = len(prev)
        names = []
        j = 0
        insertAt = 1
        for n in self.params.keys():
            if n.startswith(prev):
                names.append(n)
                insertAt = j
            j += 1
        # Maintain dict order as field ordering.
        newparams = {}
        insertAt += 1
        j = 0
        for nm in self.params.keys():
            if j == insertAt:
                k = insertAt
                for nx in names:
                    name = next + nx[i:]
                    if isinstance(self.params[nx], wx.TextCtrl):
                        newparams[name] = wx.TextCtrl(self.panel, value=self.params[nx].GetValue())
                    elif isinstance(self.params[nx], NamedButton):
                        newparams[name] = NamedButton(self.panel, "DELETE", name)
                        newparams[name].Bind(wx.EVT_BUTTON, self.on_deleteButton)
                    self.titles[name] = wx.StaticText(self.panel, -1, name)
                    hbox = wx.BoxSizer(wx.HORIZONTAL)
                    hbox.Add(self.titles[name], proportion=1, flag=wx.ALIGN_LEFT | wx.ALL) 
                    hbox.Add(newparams[name], proportion=1, flag=wx.EXPAND)
                    # Insert after last field.
                    self.vbox.Insert(k+1, hbox, proportion=1, flag=wx.EXPAND)
                    k += 1
            j += 1
            newparams[nm] = self.params[nm]
        self.params = newparams
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()
        

class WiGrid():
    def __init__(
        self, parent, titles: list, row_col: list, OnLabelLeftClick = None
    ) -> None:
        self.leny = len(row_col)
        self.lenx = len(titles)
        self.grid = wx.grid.Grid(parent, -1)
        self.grid.HideRowLabels()
        self.grid.AutoSize()
        self.grid.CreateGrid(self.leny, self.lenx)
        self.grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        self.OnLabelLeftClick = OnLabelLeftClick
        self.update(titles, row_col)

    def getGrid(self) -> wx.grid.Grid:
        return self.grid

    def update(self, titles: list, row_col: list) -> None:
        self.leny = len(row_col)
        self.lenx = len(titles)
        if self.lenx > self.grid.GetNumberCols():
            self.grid.AppendCols(self.lenx - self.grid.GetNumberCols())
        if self.grid.GetNumberCols() > self.lenx:
            self.grid.DeleteCols(0, self.grid.GetNumberCols() - self.lenx)
        if self.leny > self.grid.GetNumberRows():
            self.grid.AppendRows(self.leny - self.grid.GetNumberRows())
        if self.grid.GetNumberRows() > self.leny:
            self.grid.DeleteRows(0, self.grid.GetNumberRows() - self.leny)
        for x, title in enumerate(titles):
            self.grid.SetColLabelValue(x, title)
            self.grid.SetColLabelAlignment(wx.ALIGN_LEFT, wx.ALIGN_TOP)
        row = "<no row>"
        title = "<no title>"
        # noinspection PyBroadException
        try:
            for y, row in enumerate(row_col):
                for x, title in enumerate(titles):
                    self.grid.SetCellValue(y, x, str(row[x]))
                    self.grid.SetReadOnly(y, x)
        except Exception as e:
            traceback.print_exc()
            t = "Error in field \"" + title + "\", not found in row\n"
            t += "Row: " + str(row)
            wx.MessageBox(parent=self.grid, message=t, caption="Grid error", style=wx.OK)
            raise e
        if self.OnLabelLeftClick:
            self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnLabelLeftClick)
        self.grid.AutoSizeColumns(setAsMin=True)
        self.grid.AutoSizeRows(setAsMin=True)
        self.grid.SetSize(self.grid.DoGetBestSize())
        

class WiWS(wx.Frame):
    def __init__(self, cfg):
        wx.Frame.__init__(self, parent=None, title="Worksheet")
        try:
            self.ws = MWorksheets(cfg["wsdir"])
        except Exception as e:
            traceback.print_exc()
            wx.MessageBox(e.__class__.__name__+":"+str(e), "Error in worksheet", wx.OK, self)
            self.Layout()
            self.Show()
            raise e
        boxSizer = wx.BoxSizer(wx.VERTICAL)
        self.panel = wx.Panel(self)
        self.cmd = None
        wsns = self.ws.titles()
        wsns.append("new")
        self.ws_selection = wx.ComboBox(self.panel, choices=wsns)
        self.ws_selection.SetValue("Please select worksheet")
        boxSizer.Add(self.ws_selection, proportion=1, flag=wx.EXPAND)
        self.ws_selection.Bind(wx.EVT_COMBOBOX, self.ws_selected)
        self.titles = ["input", "cmd", "output"]
        self.grid = WiGrid(self.panel,self.titles,[], self.OnRowClick)
        boxSizer.Add(self.grid.getGrid(), proportion=1, flag=wx.EXPAND)
        # self.panel.SetMinSize(wx.Size(40,30))
        self.panel.SetSizer(boxSizer)
        self.panel.Layout()
        # self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()

    def ws_selected(self, event):
        wsn = self.ws_selection.GetValue()
        if wsn == "new":
            qp = QueryParams(parent=self, title="New worksheet name",
                 style=wx.OK | wx.NO, params={"Worksheet name": "str"}, selected={})
            qp.ShowModal()
            if qp.res != wx.OK:
                return
            wsn = qp.getValue("Worksheet name", "str")
            self.ws.addSheet(wsn)
        self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
        self.panel.Layout()
        self.Layout()
        self.Show()

    def OnRowClick(self, event):
        row = event.GetRow()
        if row == -1:
            return
        wsn = self.ws_selection.GetValue()
        outputs = self.grid.grid.GetCellValue(row, 2)
        if len(outputs) == 0:
            return
        (cmdname, self.cmd, params, selected, descriptions) = self.ws.paramsCmd(outputs)
        qp = QueryParams(parent=self, title=wsn+":"+cmdname,
             style=wx.OK | wx.CANCEL | wx.CAPTION, params=params,
             selected=selected, descriptions=descriptions, verify=self.ws_verify)
        if qp.res == wx.OK:
            self.ws.putparamsCmd(outputs, selected)
        elif qp.res == wx.CANCEL:
            self.wx.deleteCmd(outputs)
        
    def ws_verify(self, qp: QueryParams) -> None:
        wsn = self.ws_selection.GetValue()
        self.ws.updateCmd(wsn, self.cmd, qp.getSelected())
    

class Wi(wx.Frame):
    def __init__(self, parent, query, cfg, title: str):
        wx.Frame.__init__(self, parent=parent, title=title)
        self.title = title
        self.cfg = cfg
        self.pnl = None
        self.grid = None
        self.lenx = 0
        self.leny = 0
        self.selected = Params()
        if self.cfg["inherited_selected"]:
            self.selected.addBulk(self.cfg["inherited_selected"])
        self.parent = parent
        p = parent
        self.parentsQueries = set()
        while p:
            self.parentsQueries.add(p.lastQuery.name())
            p = p.parent
        self.lastQuery = query
        menuBar = wx.MenuBar()
        fileMenu = wx.Menu()
        fileMenu.Append(wx.ID_EXIT)
        mid = 0
        fileMenu.Append(id=mid, item="&Refresh results", kind=wx.ITEM_NORMAL)
        self.Bind(wx.EVT_MENU, self.OnRefreshQuery, id=mid)
        mid += 1
        menuBar.Append(fileMenu, "&File")
        self.queryMenu = wx.Menu()
        mid += 1
        self.cfg["selected"]["queryOffset"] = mid
        self.cfg["selected"]["query"] = 0
        self.cfg["midQuery"] = {}
        self.cfg["midUsage"] = {}
        for qName in self.cfg["nameQuery"].keys():
            self.queryMenu.Append(id=mid, item="&" + qName, helpString=qName, kind=wx.ITEM_NORMAL)
            self.cfg["midQuery"][mid] = self.cfg["nameQuery"][qName]
            self.cfg["midUsage"][mid] = self.cfg["nameUsage"][qName]
            self.Bind(wx.EVT_MENU, self.OnNewQuery, id=mid)
            mid += 1
        # TODO;
        # self.enableQueries()
        menuBar.Append(self.queryMenu, "&Query")
        self.filterMenu = wx.Menu()
        menuBar.Append(self.filterMenu, "&Filter")
        self.cfg["selected"]["filterOffset"] = mid
        self.cfg["selected"]["filter"] = 0
        self.cfg["midFilter"] = {}
        self.cfg["midFilterUsage"] = {}
        for fName in self.cfg["nameFilter"].keys():
            self.filterMenu.Append(id=mid, item="&" + fName, helpString=fName, kind=wx.ITEM_NORMAL)
            self.cfg["midFilter"][mid] = self.cfg["nameFilter"][fName]
            self.cfg["midFilterUsage"][mid] = self.cfg["nameFilterUsage"][fName]
            self.Bind(wx.EVT_MENU, self.OnNewQuery, id=mid)
            mid += 1
        self.inheritMenu = wx.Menu()
        # TODO;
        """
        for k, v, t in cfg["inherited_selected"].getBulk():
            self.inheritMenu.Append(id=mid, item="&" + k + "=" + str(v), helpString="inherited value",
                                    kind=wx.ITEM_NORMAL)
        """
        menuBar.Append(self.inheritMenu, "&Inherited")
        # qp = QueryParams(parent=self, title="Selected values",
        #                 style=wx.YES_NO | wx.CANCEL, params={"1": "int"}, selected={"1": "1"})
        # menuBar.Append(qp, "&elected")
        self.SetMenuBar(menuBar)
        if self.cfg["titles"]:
            self.gridIt()
        else:
            self.Layout()
            self.Show()

    def getSelected(self) -> Params:
        selected = Params()
        if self.cfg["inherited_selected"]:
            selected.addBulk(self.cfg["inherited_selected"])
        if self.grid:
            selected.addBulk(self.selected)
        return selected

    def doQuery(self) -> None:
        if self.cfg["selected"]["query"] == -1:
            return
        mid = self.cfg["selected"]["query"]
        q = self.cfg["midQuery"][mid](self.cfg)
        u = self.cfg["midUsage"][mid]
        selected = self.getSelected()
        for p, v in u["defaults"].items():
            if p not in selected:
                selected[p] = (v, u["params"][p])
        if "constraints" in u:
            error = ""
            for f, v in u["constraints"].items():
                if f not in selected:
                    error += "Select row with column called \"" + f + "\"\n"
                elif v != selected[f][0]:
                    error += "Select row where column \"" + f + "\"=\"" + v + "\"\n"
            if error:
                wx.MessageBox(prent=self, message=error, caption="Cannot run " + q.name(), style=wx.OK)
                return
        error = ""
        for f in u["required"]:
            if f not in selected:
                error += "Select row with column called \"" + f + "\"\n"
        if error:
            wx.MessageBox(prent=self, message=error, caption="Cannot run query on selected fields", style=wx.OK)
            return
        t = q.name()
        for p in u["params"]:
            t += "\n" + p + "=" + str(selected.get(p, ("", ""))[0])
        if u["return"] and self.cfg["titles"]:
            qp = QueryParams(parent=self, title="Run query in a new window?",
                             style=wx.YES_NO | wx.CANCEL, params=u["params"], selected=selected)
        else:
            qp = QueryParams(parent=self, title="Run query?",
                             style=wx.OK | wx.CANCEL, params=u["params"], selected=selected)
        qp.ShowModal()
        for name, field in qp.params.items():
            selected[name] = qp.getValue(name, u["params"][name])
        ans = qp.res
        if ans == wx.CANCEL:
            return
        self.cfg["map"] = u["map"]
        self.lastQuery = q
        if ans != wx.YES:
            self.cfg["titles"] = u["return"]
            res = q.exec(params=selected, scratchPad=self.cfg["scratchPad"])
            newResults = []
            for x in res:
                newResults.append(x)
            label = q.name() + " (" + q.query + ")"
            if not newResults:
                if not u["return"]:
                    return
                wx.MessageBox(prent=self, message=label, caption="Query no results, check for logs in the console",
                              style=wx.OK)
                return
            else:
                self.cfg["results"] = newResults
                self.SetTitle(label)
                self.gridIt()
        else:
            self.cfg["child_selected"] = selected
            cfg = self.copyCfg()
            cfg["titles"] = u["return"]
            res = q.exec(params=selected, scratchPad=self.cfg["scratchPad"])
            newResults = []
            for x in res:
                newResults.append(x)
            if not newResults:
                if not u["return"]:
                    return
                wx.MessageBox(prent=self, message=q.query, caption="Query no results",
                              style=wx.OK)
                return
            else:
                cfg["results"] = newResults
                label = q.name() + " (" + q.query + ")"
                Wi(self, q, cfg, label)
        self.enableQueries()

    def doFilter(self) -> None:
        if self.cfg["selected"]["filter"] == -1:
            return
        mid = self.cfg["selected"]["filter"]
        f = self.cfg["midFilter"][mid](self.cfg)
        u = self.cfg["midFilterUsage"][mid]
        print(self.cfg["results"])
        for row in self.cfg["results"]:
            for col in row:
                pass
                # u["ColType"]
        # qp = QueryParams(parent=self, title="Run filter in a new window?",
        #                 style=wx.YES_NO | wx.CANCEL, params=u["params"], selected=selected)

    def OnRefreshQuery(self, _event):
        if self.cfg["selected"]["query"] != -1:
            self.doQuery()
        if self.cfg["selected"]["filter"] != -1:
            self.doFilter()

    def OnNewQuery(self, event):
        self.cfg["selected"]["query"] = -1
        self.cfg["selected"]["filter"] = -1
        mid = event.GetId()
        if mid < self.cfg["selected"]["filterOffset"]:
            self.cfg["selected"]["query"] = mid
            self.doQuery()
        else:
            self.cfg["selected"]["filter"] = mid
            self.doFilter()

    def enableQueries(self):
        mFields = set()  # Required fields that are not selected and there's no default.
        for mid, u in self.cfg["midUsage"].items():
            name = self.cfg["midQuery"][mid].name()
            if name in self.parentsQueries or (self.lastQuery and name == self.lastQuery.name()):
                self.queryMenu.SetLabel(mid, name + "<ran>")
                self.queryMenu.Enable(id=mid, enable=False)
                continue
            self.queryMenu.Enable(id=mid, enable=True)
            for field in u["required"]:
                if not self.selected.find(field) and field not in u["defaults"]:
                    mFields.add(field)
        for mid, u in self.cfg["midUsage"].items():
            if not self.queryMenu.IsEnabled(id=mid):
                continue
            name = self.cfg["midQuery"][mid].name()
            # find fields that the query needs and are missing,
            # find field that the query returns that other queries need.
            missingFields = set()
            for field in mFields:
                if field in u["required"]:
                    missingFields.add(field)
            returnsFields = set()
            for field in mFields:
                if field in u["return"]:
                    returnsFields.add(field)
            if returnsFields:
                returnsFields = "\n[" + (", ".join(sorted(returnsFields))) + "]"
            else:
                returnsFields = ""
            if missingFields:
                self.queryMenu.Enable(id=mid, enable=False)
                missingFields = " (" + (", ".join(sorted(missingFields))) + ")"
            else:
                self.queryMenu.Enable(id=mid, enable=True)
                missingFields = ""
            self.queryMenu.SetLabel(mid, name + missingFields + returnsFields)

    # User selects a row, update selected with new values.
    def OnLabelLeftClick(self, event):
        row = event.GetRow()
        if row == -1:
            return
        newSelected = Params()
        if self.cfg["inherited_selected"]:
            newSelected.addBulk(self.cfg["inherited_selected"])
        if row != -1:
            for x in range(self.lenx):
                key = self.grid.GetColLabelValue(x)
                val = self.grid.GetCellValue(row, x)
                typ = self.selected.typ(key)
                newSelected.add(key, val, typ)
        self.selected = newSelected
        self.enableQueries()

    def gridIt(self):
        self.leny = len(self.cfg["results"])
        self.lenx = 0
        if self.cfg["results"]:
            self.lenx = len(self.cfg["results"][0].keys())
        if not self.grid:
            self.grid = wx.grid.Grid(self, -1)
            self.grid.CreateGrid(self.leny, self.lenx)
            self.grid.SetSelectionMode(wx.grid.Grid.SelectRows)
        else:
            if self.lenx > wx.grid.GetNumberCols():
                self.grid.AppendCols(self.lenx - self.grid.GetNumberCols())
            if self.grid.GetNumberCols() > self.lenx:
                self.grid.DeleteCols(0, self.grid.GetNumberCols() - self.lenx)
            if self.leny > self.grid.GetNumberRows():
                self.grid.AppendRows(self.leny - self.grid.GetNumberRows())
            if self.grid.GetNumberRows() > self.leny:
                self.grid.DeleteRows(0, self.grid.GetNumberRows() - self.leny)
        titles = []
        for x, title in enumerate(self.cfg["titles"]):
            titles.append(title)
            self.grid.SetColLabelValue(x, title)
            self.grid.SetColLabelAlignment(wx.ALIGN_LEFT, wx.ALIGN_TOP)
        row = "<no row>"
        title = "<no title>"
        # noinspection PyBroadException
        try:
            for y, row in enumerate(self.cfg["results"]):
                for x, title in enumerate(titles):
                    self.grid.SetCellValue(y, x, str(row[title]))
                    if self.lastQuery.usage()["return"][title] == "password":
                        self.grid.SetCellTextColour(y, x, self.grid.GetCellBackgroundColour(y, x))
                    self.grid.SetReadOnly(y, x)
        except Exception:
            traceback.print_exc()
            t = "Error in plugin for the query (" + self.lastQuery.name() + ")\n"
            t += "field " + title + "Not found in row\n"
            t += "Row: " + str(row)
            t += "\n\nHINT: is it calling the correct api?"
            wx.MessageBox(parent=self, message=t, caption="New window", style=wx.OK)
        self.grid.Bind(wx.grid.EVT_GRID_SELECT_CELL, self.OnLabelLeftClick)
        self.grid.AutoSizeRows(setAsMin=True)
        self.grid.SetSize(self.grid.DoGetBestSize())
        self.Layout()
        self.Show()

    @staticmethod
    def getCfg() -> dict:
        cfg = {
            "selected": {"row": -1}, "inherited_selected": {}, "child_selected": {}, "results": [],
            "titles": {}, "columns": {},
            "nameQuery": {}, "midUsage": {}, "nameUsage": {}, "midQuery": {},
            "nameFilter": {}, "nameFilterUsage": {}, "midFilter": {},
            "scratchPad": {}
        }
        for inp in inputs.ALL:
            error = inp.checkUsage(inp.usage())
            if error:
                print(inp.name() + " " + error)
                exit(1)
            if inp.name():
                cfg["nameQuery"][inp.name()] = inp
                cfg["nameUsage"][inp.name()] = inp.usage()
        """
        for filt in filters.ALL:
            if filt.name():
                cfg["nameFilter"][filt.name()] = filt
                cfg["nameFilterUsage"][filt.name()] = filt.usage()"""
        return cfg

    def reloadCfg(self) -> dict:
        for inp in inputs.ALL:
            pass
            # TODO Reload module.
        for filt in filters.ALL:
            pass
            # TODO Reload module.

    def copyCfg(self) -> dict:
        d = {
            "selected": {},
            "inherited_selected": {},
            "child_selected": {},
            "results": [],
            "titles": {},
            "columns": {},
            "nameQuery": self.cfg["nameQuery"],
            "midUsage": {},
            "nameUsage": self.cfg["nameUsage"],
            "midQuery": {},
            "nameFilter": self.cfg["nameFilter"],
            "midUsage": {},
            "nameFilterUsage": self.cfg["nameFilterUsage"],
            "midFilter": {},
            "scratchPad": {}
        }
        for k, v in self.cfg["scratchPad"].items():
            d["scratchPad"][k] = v
        for k, v in self.cfg["child_selected"].items():
            d["inherited_selected"][k] = v
        for k, v in self.cfg["selected"].items():
            d["selected"][k] = v
        d["selected"]["row"] = -1
        return d

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Wi")
        parser.add_argument('--dir', help="worksheet dir")
        parser.add_argument('-d', '--debug', help="activate debugging", action="store_true")
        args = parser.parse_args()
        if args.dir is None:
            args.dir = "worksheets"
        app = wx.App(0)
        cfg = {"debug": args.debug, "wsdir": args.dir }
        try:
            WiWS(cfg)
        except Exception:
            pass
        app.MainLoop()


if __name__ == "__main__":
    Wi.main()
