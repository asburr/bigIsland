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

# QueryParam (should be called form:->)
# Given a list of parameters (params) and current values (selected) 
# and descriptions. Creates a form to turn on param options and 
# add more to a param list and edit param values.
try:
    import wx
    import wx.lib.scrolledpanel
except Exception:
    print("Failed to import wx, install instructions:")
    print("sudo apt-get install -y libsdl2-2.0-0")
    print("sudo apt-get install libgtk-3-dev")
    print("pip3 install -U -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-18.04 wxPython")
    exit(1)


class NamedButton(wx.Button):
    def __init__(self, parent, title: str, name:str):
        wx.Button.__init__(self, parent, label=title)
        self.name = name

class NamedComboBox(wx.ComboBox):
    def __init__(self, parent, choices: list, name: str):
        wx.Button.__init__(self, parent, choices=choices)
        self.name = name

class QueryParams(wx.Frame):
#class QueryParams(wx.Dialog):
    def __init__(self, parent, title: str, style: int, params: dict, selected: dict, verify: any, sample: any, descriptions: dict, getOptions: any, on_close: any = None, data: any = None):
        wx.Frame.__init__(self, parent=parent, title=title, style=wx.RESIZE_BORDER | wx.CLOSE_BOX)
        if on_close is not None:
            self.Bind(wx.EVT_CLOSE, on_close)
        self.title = title
        self.data = data
        self.verify = verify
        self.sample = sample
        self.getOptions = getOptions
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
        self.vbox.Add(hbox, proportion=0, flag=wx.EXPAND)
        self.spanel = wx.lib.scrolledpanel.ScrolledPanel(self.panel)
        self.spanel.SetupScrolling()
        self.svbox = wx.BoxSizer(wx.VERTICAL)
        self.spanel.SetSizer(self.svbox)
        self.vbox.Add(self.spanel, proportion=1, flag=wx.EXPAND)
        self.descriptions = {}
        self.updateParams("", params, selected, descriptions)
        self.spanel.Layout()
        self.panel.SetSizer(self.vbox)
        self.panel.Layout()
        self.showFields()

    def updateParams(self, after: str, params: dict, selected: dict, descriptions: dict) -> None:
        for name in descriptions:
            if name not in self.descriptions:
                self.descriptions[name] = descriptions[name]
        pos = 0
        for i, n in enumerate(self.params.keys()):
            if n.startswith(after):
                pos = i
        beforeparams = {}
        for i, n in enumerate(self.params.keys()):
            beforeparams[n] = self.params[n]
            if i == pos:
                break
        afterparams = {}
        for i, n in enumerate(self.params.keys()):
            if i <= pos:
                continue
            afterparams[n] = self.params[n]
        self.params = {}
        for name, typ in params.items():
            if name in beforeparams or name in afterparams:
                continue  # Param already in params, only update new params.
            pos += 1
            value = str(selected.get(name, ""))
            flags = wx.ALL | wx.EXPAND
            proportion = 0
            descname = name
            if typ == "str":
                proportion = 1
                if value is None:
                    hint = selected.get("default"+name,"enter value")
                    self.params[name] = wx.TextCtrl(self.spanel, style=wx.TE_MULTILINE)
                    if hint:
                        self.params[name].SetHint(hint)
                else:
                    self.params[name] = wx.TextCtrl(self.spanel, style=wx.TE_MULTILINE, value=value)
            elif typ == "option":
                if selected[name]:
                    label = "OPTION OFF"
                else:
                    label = "OPTION ON"
                self.params[name] = NamedButton(self.spanel, label, name)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_optButton)
            elif typ == "addbutton":
                self.params[name] = NamedButton(self.spanel, "ADD", name)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_addButton)
            elif typ == "deletebutton":
                self.params[name] = NamedButton(self.spanel, "DELETE", name)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_deleteButton)
            elif typ == "samplebutton":
                self.params[name] = NamedButton(self.spanel, "SAMPLE", value)
                self.params[name].Bind(wx.EVT_BUTTON, self.on_sampleButton)
            elif typ == "int":
                proportion = 1
                self.params[name] = wx.TextCtrl(self.spanel, value=value)
            elif typ == "YYYYMMDD HH:MM:SS":
                proportion = 1
                self.params[name] = wx.TextCtrl(self.spanel, value=value)
            elif typ == "password":
                proportion = 1
                self.params[name] = wx.TextCtrl(self.spanel, value=value)
            elif isinstance(typ, list):  # Choice
                if len(value) == 0:
                    value = typ[0]  # No selection, default to first choice.
                self.params[name] = NamedComboBox(self.spanel, choices=typ,name=name)
                self.params[name].SetValue(value)
                self.params[name].Bind(event=wx.EVT_COMBOBOX, handler=self.on_choice)
                descname = value
            else:
                raise Exception("Exception unknown type=" + str(typ))
            hbox = wx.BoxSizer(wx.HORIZONTAL)
            self.titles[name] = wx.StaticText(self.spanel, -1, name)
            hbox.Add(self.titles[name], proportion=0, flag=wx.ALIGN_LEFT) 
            hbox.Add(self.params[name], proportion=proportion, flag=wx.ALL | wx.EXPAND)
            if descname in descriptions:
                self.desc[name] = wx.TextCtrl(self.spanel, value=descriptions[descname], style=wx.TE_MULTILINE|wx.TE_READONLY)
                hbox.Add(self.desc[name], proportion=1, flag=flags)
            if pos < self.svbox.GetItemCount():
                self.svbox.Insert(pos, hbox, flag=flags)
            else:
                self.svbox.Add(hbox, proportion=proportion, flag=flags)
        newparams = {}
        for n, e in beforeparams.items():
            newparams[n] = e
        for n, e in self.params.items():
            newparams[n] = e
        for n, e in afterparams.items():
            newparams[n] = e
        self.params = newparams

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
        self.panel.Layout()
        self.Layout()
        self.Show()

    def getSelected(self) -> dict:
        selected = {}
        for name, e in self.params.items():
            if e.IsShown():
                if isinstance(e,NamedButton):
                    selected[name] = e.GetLabel().endswith("OFF")
                else:
                    selected[name] = e.GetValue()
                    if e.GetHint() and not selected[name]:
                        selected[name] = None
                        selected["default"+name] = e.GetHint()
        return selected

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
        self.Close()
        self.Destroy()

    def on_delete(self, _event):
        if wx.MessageBox("", "Confirm delete of command", wx.YES | wx.NO, self) == wx.YES:
            self.res = wx.CANCEL
            self.Close()
            self.Destroy()

    def on_yes(self, _event):
        self.res = wx.YES
        self.Close()
        self.Destroy()

    def on_ok(self, _event):
        if self.verify is not None:
            error = self.verify(self)
            if error:
                wx.MessageBox(
                    "Failed:"+error,
                    "verification",
                    wx.OK, self)
                return
        self.res = wx.OK
        self.Close()
        self.Destroy()

    def on_verify(self, _event):
        if self.verify is None:
            raise Exception("No verify callback method")
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
        value = cb.GetValue()
        name = cb.name
        if name in self.desc:
            if value in self.descriptions:
                self.desc[name].SetValue(self.descriptions[value])
            else:
                self.desc[name].SetValue("")
        self.showFields()
        
    def on_sampleButton(self, event) -> None:
        if self.sample is None:
            return
        cb = event.GetEventObject()
        self.sample(cb.name)
        
    def on_deleteButton(self, event) -> None:
        b = event.GetEventObject()
        if wx.MessageBox("", "Confirm delete of parameters", wx.YES | wx.NO, self) != wx.YES:
            return
        d = []
        for i, n in enumerate(self.params.keys()):
            if n.startswith(b.name):
                d.append((i, n))
        for i, n in reversed(d):
            self.params[n].Hide()
            del self.params[n]
            self.titles[n].Hide()
            del self.titles[n]
            if n in self.desc:
                self.desc[n].Hide()
                del self.desc[n]
            self.svbox.Remove(i)
        self.showFields()

    def on_addButton(self, event) -> None:
        b = event.GetEventObject()
        (params, selected, desc) = self.getOptions(cmd=None,at=b.name)
        prev = None
        for n in self.params.keys():
            if n.startswith(b.name):
                if self.params[n].GetLabel() == "DELETE":
                   prev = n
        if prev:
            x = prev[len(b.name)+1:]  # Cut main title and first dot.
            oldname = b.name + ".0"
            newname = b.name + "." + str(int(x) + 1)
            newparams = {}
            newselected = {}
            newdesc = {}
            for n, t in params.items():
                newn = n.replace(oldname,newname)
                newparams[newn] = params[n]
                if n in selected:
                    newselected[newn] = selected[n]
                if n in desc:
                    newdesc[newn] = desc[n]
            self.updateParams(b.name, newparams, newselected, newdesc)
        else:
            self.updateParams(b.name, params, selected, desc)
        self.showFields()

    def on_optButton(self, event) -> None:
        b = event.GetEventObject()
        if b.GetLabel().endswith("ON"):
            b.SetLabel("OPTION OFF")
            n = b.name
            if n.rindex("."):
                n = n[0:n.rindex(".")]
            (params, selected, desc) = self.getOptions(cmd=None, at=n)
            self.updateParams(n, params, selected, desc)
        else:
            b.SetLabel("OPTION ON")
        self.showFields()
