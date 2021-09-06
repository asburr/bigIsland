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
            elif typ == "option":
                if selected[name]:
                    label = "OPTION OFF"
                else:
                    label = "OPTION ON"
                self.params[name] = NamedButton(self.panel, label, name)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_optButton)
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
        self.showFields()
        self.panel.SetSizer(self.vbox)
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()

    def showFields(self) -> None:
        show = [True]  # Whether to show or hide the next field.
        nested = []  # name to match to pop the stack.
        choice = []  # name to match to start the choice selection
        for name in self.params.keys():
            e = self.params[name]
            # Pop end of field group
            while len(nested) > 0 and not name.startswith(nested[-1]):
                del show[-1]
                del nested[-1]
            # Look out for the start of chosen fields.
            if (len(choice) > 0 and
                (len(nested) == 0 or nested[-1] != choice[-1]) and
                name.startswith(choice[-1])):
                nested.append(name)
                show.append(True)
            showfield = show[-1]
            if isinstance(e, NamedButton) and e.GetLabel().startswith("OPTION"):
                nested.append(name[:name.rfind(".")])
                # OFF means turn it off, and it is currently ON!
                if self.params[name].GetLabel() == "OPTION OFF":
                    show.append(show[-1])
                else:
                    show.append(False)
            elif isinstance(e, wx.ComboBox):  # Choice
                if showfield:
                    nested.append(name)
                    show.append(False)
                    choice.append(name+"."+self.params[name].GetValue())
            if showfield:
                self.params[name].Show()
                self.titles[name].Show()
                if name in self.desc:
                    self.desc[name].Show()
            else:
                self.params[name].Hide()
                self.titles[name].Hide()
                if name in self.desc:
                    self.desc[name].Hide()
        self.Show()

    def getSelected(self) -> dict:
        selected = {}
        for name, e in self.params.items():
            if e.IsShown():
                if isinstance(e,NamedButton):
                    selected[name] = e.GetLabel().endswith("OFF")
                else:
                    selected[name] = e.GetValue()
        return selected

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
        error = self.verify(self)
        if error:
            wx.MessageBox(
                "Faild:"+error,
                "verification",
                wx.OK, self)
            return
        wx.MessageBox("Passed", "verification", wx.OK, self)

    def on_choice(self, event):
        cb = event.GetEventObject()
        self.setChoice(self.choices[cb.GetId()], cb.GetValue())
        self.showFields()
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()

    def on_deleteButton(self, event) -> None:
        b = event.GetEventObject()
        d = []
        for n in self.params.keys():
            if n.startswith(b.name):
                d.append(n)
        for n in d:
            del self.params[n]
            del self.titles[n]
            if n in self.desc:
                del self.desc[n]
        self.showFields()
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
        self.showFields()
        self.panel.Layout()
        self.SetSize(self.panel.DoGetBestSize())
        self.Layout()
        self.Show()
        
    def on_optButton(self, event) -> None:
        b = event.GetEventObject()
        if b.GetLabel().endswith("ON"):
            b.SetLabel("OPTION OFF")
        else:
            b.SetLabel("OPTION ON")
        self.showFields()
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
                 style=wx.OK | wx.NO, params={"Worksheet name": "str"}, selected={}, verify=self.sw_verify)
            qp.ShowModal()
            if qp.res != wx.OK:
                return
            wsn = qp.getValue("Worksheet name", "str")
            self.ws.addSheet(wsn)
        self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
        self.panel.Layout()
        self.Layout()
        self.Show()

    def ws_verify(self, qp: QueryParams) -> str:
        wsn = self.ws_selection.GetValue()
        return self.ws.updateCmd(wsn, self.cmd, qp.getSelected())

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
    WiWS.main()
