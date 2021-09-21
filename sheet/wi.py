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
# WI (Window interface) for sheet.
# Usage:
# export PYTHONPATH=.
# python3 sheet/wi.py
import argparse
import traceback

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
from sheet.QueryParams import QueryParams
from sheet.Grid import WiGrid


class WiFramedGrid(wx.Frame):
    def __init__(self, title: str, data: dict):
        wx.Frame.__init__(self, parent=None, title=title)
        boxSizer = wx.BoxSizer(wx.VERTICAL)
        self.panel = wx.Panel(self)
        self.grid = WiGrid(self.panel,data["titles"], data["rows"])
        boxSizer.Add(self.grid.getGrid(), proportion=1, flag=wx.EXPAND)
        self.panel.SetSizer(boxSizer)
        self.panel.Layout()
        self.Layout()
        self.Show()


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
        wsns.append("new worksheet")
        self.ws_selection = wx.ComboBox(self.panel, choices=wsns)
        self.ws_selection.SetValue("Please select worksheet")
        self.ws_selection.Bind(wx.EVT_COMBOBOX, self.ws_selected)
        boxSizer.Add(self.ws_selection, proportion=0, flag=wx.EXPAND)
        self.addButton = wx.Button(self.panel, label="ADD CMD")
        self.addButton.Bind(wx.EVT_BUTTON, self.on_addcmd)
        self.addButton.Hide()
        boxSizer.Add(self.addButton, proportion=0, flag=wx.EXPAND)
        self.titles = ["input", "cmd", "output"]
        self.grid = WiGrid(self.panel,self.titles,[], self.OnRowClick)
        boxSizer.Add(self.grid.getGrid(), proportion=1, flag=wx.EXPAND)
        self.panel.SetSizer(boxSizer)
        self.panel.Layout()
        self.Layout()
        self.Show()

    def on_addcmd(self, event):
        wsn = self.ws_selection.GetValue()
        QueryParams(parent=self, title="New command for " + wsn,
             style=wx.OK | wx.NO, params={"select command": self.ws.cmd_titles()}, selected={}, verify=None, sample=None, descriptions=self.ws.cmd_descriptions(), on_close=self.wsaddcmd_close, getOptions=self.ws.paramsCmd)

    def wsaddcmd_close(self, event):
        wsn = self.ws_selection.GetValue()
        qp = event.GetEventObject()
        if qp.res != wx.OK:
            return
        (cmdname, typ) = qp.getValue("select command", "str")
        if not cmdname:
            return
        (params, selected, desc) = self.ws.paramsCmd(cmd=None, at=cmdname)
        QueryParams(parent=self, title="New command for " + wsn,
             style=wx.OK | wx.NO, params=params, selected=selected, verify=self.wsaddedcmd_verify, sample=None, descriptions=desc, on_close=self.wsaddedcmd_close, data=cmdname, getOptions=self.ws.paramsCmd)

    def wsaddedcmd_verify(self, qp: QueryParams) -> str:
        wsn = self.ws_selection.GetValue()
        selected = qp.getSelected()
        return self.ws.updateCmd(wsn=wsn, cmd=None, selected=selected)

    def wsaddedcmd_close(self, event):
        wsn = self.ws_selection.GetValue()
        qp = event.GetEventObject()
        if qp.res != wx.OK:
            return
        # cmdname = qp.data
        selected = qp.getSelected()
        error = self.ws.updateCmd(wsn=wsn, cmd=None, selected=selected)
        if len(error) > 0:
            wx.MessageBox(
                error,
                "",
                wx.OK, self)
            return
        self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
        self.Show()

    def ws_selected(self, event):
        wsn = self.ws_selection.GetValue()
        if wsn == "new worksheet":
            self.addButton.Hide()
            QueryParams(parent=self, title="New worksheet name",
                 style=wx.OK | wx.NO, params={"Worksheet name": "str"}, selected={}, verify=None, sample=None, descriptions={}, on_close=self.wsname_close, getOptions=self.ws.paramsCmd)
        else:
            self.addButton.Show()
            self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
            self.panel.Layout()
            self.Layout()
            self.Show()

    def wsname_close(self, event) -> None:
        qp = event.GetEventObject()
        if qp.res != wx.OK:
            return
        (wsn, typ) = qp.getValue("Worksheet name", "str")
        if not wsn:
            return
        error = self.ws.addSheet(wsn)
        if error:
            wx.MessageBox(
                "Faild: "+error,
                "",
                wx.OK, self)
            return
        self.ws_selection.Clear()
        self.ws_selection.Append(self.ws.titles())
        self.ws_selection.Append("new worksheet")
        self.addButton.Show()
        self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
        event.Skip()

    def ws_verify(self, qp: QueryParams) -> str:
        wsn = self.ws_selection.GetValue()
        cmd = self.ws.getCmd(outputs=qp.data)
        return self.ws.updateCmd(wsn=wsn, cmd=cmd, selected=qp.getSelected())

    def ws_sample(self) -> None:
        WiFramedGrid(title="sample", data={"titles": ["a","b"], "rows": [[1,2]]})

    def OnRowClick(self, event):
        row = event.GetRow()
        if row == -1:
            return
        wsn = self.ws_selection.GetValue()
        outputs = self.grid.grid.GetCellValue(row, 2)
        if len(outputs) > 0:
            self.cmd=self.ws.getCmd(outputs);
        else:
            cmdname = self.grid.grid.GetCellValue(row, 1)
            for j in self.ws.sheet(wsn):
                if cmdname in j:
                    self.cmd = j
                    break
        if self.cmd is None:
            return
        cmdname = self.ws.cmdName(self.cmd)
        (params, selected, descriptions) = self.ws.paramsCmd(cmd=self.cmd, at=cmdname)
        QueryParams(parent=self, title=wsn+":"+cmdname,
             style=wx.OK | wx.CANCEL | wx.CAPTION | wx.NO, params=params,
             selected=selected, descriptions=descriptions, verify=self.ws_verify, sample=self.ws_sample, on_close=self.ws_close, data=outputs, getOptions=self.ws.paramsCmd)

    def ws_close(self, event) -> None:
        wsn = self.ws_selection.GetValue()
        qp = event.GetEventObject()
        if qp.res == wx.OK:
            errors = self.ws_verify(qp)
            if errors:
                wx.MessageBox(
                    "Faild: "+errors,
                    "",
                    wx.OK, self)
                return
            cmd = self.ws.getCmd(outputs=qp.data)
            self.ws.purgeCmd(cmd)
            self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
        elif qp.res == wx.CANCEL:
            self.ws.deleteCmd(wsn=wsn,outputs=qp.data)
            self.grid.update(self.titles, self.ws.inputCmdOutput(wsn))
        event.Skip()

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
