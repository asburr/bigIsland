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
import json
import uuid
try:
    import wx
    import wx.grid
except Exception:
    print("Failed to import wx, install instructions:")
    print("sudo apt-get install -y libsdl2-2.0-0")
    print("sudo apt-get install libgtk-3-dev")
    print("pip3 install -U -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-18.04 wxPython")
    exit(1)
from magpie.src.musage import MUsage
from magpie.src.mudp import MUDP, MUDPBuildMsg
from magpie.src.mworksheets import MCmd
from sheet.QueryParams import QueryParams
from sheet.Grid import WiGrid
from hallelujah.hallelujah import Hallelujah


class WiSampleGrid(wx.Frame):
    def __init__(self, title: str, remoteAddr: (str,int), mudp: MUDP):
        wx.Frame.__init__(self, parent=None, title=title)
        boxSizer = wx.BoxSizer(wx.VERTICAL)
        self.mudp = mudp
        self.panel = wx.Panel(self)
        self.label = wx.TextCtrl(self.panel, style=wx.TE_READONLY, value="0 rows (waiting for database to respond)")
        boxSizer.Add(self.label, proportion=0, flag=wx.EXPAND)
        self.headers=[]
        self.rows=[]
        self.grid = WiGrid(self.panel, titles=self.headers, row_col=self.rows)
        boxSizer.Add(self.grid.getGrid(), proportion=1, flag=wx.EXPAND)
        self.panel.SetSizer(boxSizer)
        self.panel.Layout()
        self.Layout()
        self.Show()
        self.requestId = self.mudp.send(
            content=json.dumps({"_sample_":{"feed":title, "N":100}}),
            eom=True,
            msg=MUDPBuildMsg(remoteAddr=remoteAddr,
                             requestId=MUDPBuildMsg.nextId())
        )
        self.timer = wx.PyTimer(self.timerTick)
        self.timer.Start(100)
        self.Bind(wx.EVT_CLOSE, self.onClose)

    def onClose(self, event):
        self.timer.Stop()
        self.mudp.cancelRequestId(self.requestId)
        self.Destroy()

    def timerTick(self):
        eom = False
        updates = False
        timeout = False
        for ret in self.mudp.recvRequestId(self.requestId):
            content, eom = ret
            if content is not None:
                j = json.loads(content)
                if len(self.headers) == 0:
                    updates = True
                    self.headers = j["_sample_response_"]["schema"]
                else:
                    updates = True
                    row = []
                    for header in self.headers:
                        row.append(j[header])
                    self.rows.append(row)
            if eom:
                timeout = not content  # None content when timeout.                                               
                self.timer.Stop()
            else:
                ret = next(self.mudp.recvRequestId(self.requestId))
        if updates:
            self.label.SetValue("%d rows (loading)"%len(self.rows))
            self.grid.update(titles=self.headers, row_col=self.rows)
        if eom:
            if len(self.headers) == 0:
                self.label.SetValue("0 rows (no response; is database up?)")
            elif timeout:
                self.label.SetValue("%d rows (partial response that timed out; is database overloaded?)"%len(self.rows))
            else:
                self.label.SetValue("%d rows (complete response)"%len(self.rows))
    
class WiWS(wx.Frame):
    def __init__(self, debug: bool, wsdir: str, congregation: (str,int)):
        """
        Connects to the DB and reads (hj) the worksheets, local differences are
        "new" changes and the database version of the worksheet is the current
        version.
        """
        self.wsn = None
        self.hj = Hallelujah(
                congregationHost=congregation[0],
                congregationPort=congregation[1],
                worksheetdir=wsdir
            )
        self.ws = self.hj.worksheets
        wx.Frame.__init__(self, parent=None, title="Worksheet")
        self.congregation = congregation
        boxSizer = wx.BoxSizer(wx.VERTICAL)
        self.panel = wx.Panel(self)
        self.cmd = None
        self.currentChange = wx.StaticText(self.panel,label="")
        boxSizer.Add(self.currentChange, proportion=0, flag=wx.EXPAND)
        self.ws_selectionDEL = wx.ComboBox(self.panel, choices=[])
        self.ws_selectionDEL.Bind(wx.EVT_COMBOBOX, self.ws_selectedDEL)
        boxSizer.Add(self.ws_selectionDEL, proportion=0, flag=wx.EXPAND)
        self.ws_selectionREDO = wx.ComboBox(self.panel, choices=[])
        self.ws_selectionREDO.Bind(wx.EVT_COMBOBOX, self.ws_selectedREDO)
        boxSizer.Add(self.ws_selectionREDO, proportion=0, flag=wx.EXPAND)
        self.ws_selectionUNDO = wx.ComboBox(self.panel, choices=[])
        self.ws_selectionUNDO.Bind(wx.EVT_COMBOBOX, self.ws_selectedUNDO)
        boxSizer.Add(self.ws_selectionUNDO, proportion=0, flag=wx.EXPAND)
        self.ws_selection = wx.ComboBox(self.panel, choices=[])
        # Changing choices:
        #   self.ws_selection.SetItems(wsns)
        #   self.ws_selection.SetValue(current_value)
        self.ws_selection.Bind(wx.EVT_COMBOBOX, self.ws_selectedNEW)
        boxSizer.Add(self.ws_selection, proportion=0, flag=wx.EXPAND)
        self.refreshSelection()
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
        self.usage = MUsage()

    def refreshSelection(self):
        print("refreshSelection")
        change = self.ws.changes.currentChange()
        self.currentChange.SetLabel(str(change))
        if change:
            changes=[str(change)]
        else:
            changes=[]
        self.ws_selectionUNDO.SetItems(changes)
        self.ws_selectionUNDO.SetValue("UNDO")
        print("refreshSelection A")
        change = self.ws.changes.nextChange()
        if change:
            changes=[str(change)]
        else:
            changes=[]
        self.ws_selectionDEL.SetItems(changes)
        self.ws_selectionDEL.SetValue("DEL")
        self.ws_selectionREDO.SetItems(changes)
        self.ws_selectionREDO.SetValue("REDO")
        print("refreshSelection B")
        wsns = self.ws.titles()
        wsns.append("new worksheet")
        self.ws_selection.SetItems(wsns)
        self.ws_selection.SetValue("NEW")
        if self.wsn:
            self.addButton.Show()
            self.grid.update(self.titles, self.ws.inputCmdOutput(self.wsn))
            self.panel.Layout()
            self.Layout()
            self.Show()
        print("refreshSelection X")

    def on_addcmd(self, event):
        wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        QueryParams(parent=self, title="New command for " + wsn,
             style=wx.OK | wx.NO, params={"select command": self.ws.cmd_titles()}, selected={}, verify=None, sample=None, descriptions=self.ws.cmd_descriptions(), on_close=self.wsaddcmd_close, getOptions=self.ws.paramsCmd)
        event.Skip(False)

    def wsaddcmd_close(self, event):
        wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        qp = event.GetEventObject()
        if qp.res != wx.OK:
            event.Skip(False)
            return
        (cmdname, typ) = qp.getValue("select command", "str")
        if not cmdname:
            event.Skip(False)
            return
        (params, selected, desc) = self.ws.paramsCmd(cmd=None, at=cmdname)
        QueryParams(parent=self, title="New command for " + wsn,
             style=wx.OK | wx.NO, params=params, selected=selected, verify=self.wsaddedcmd_verify, sample=None, descriptions=desc, on_close=self.wsaddedcmd_close, data=cmdname, getOptions=self.ws.paramsCmd)
        event.Skip(False)

    def wsaddedcmd_verify(self, qp: QueryParams) -> str:
        wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        selected = qp.getSelected()
        return self.ws.updateCmd(wsn=wsn, selected=selected)

    def wsaddedcmd_close(self, event):
        self.wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        qp = event.GetEventObject()
        if qp.res != wx.OK:
            event.Skip(False)
            return
        # cmdname = qp.data
        selected = qp.getSelected()
        error = self.ws.updateCmd(wsn=self.wsn, selected=selected)
        if len(error) > 0:
            wx.MessageBox(
                error,
                "",
                wx.OK, self)
            event.Skip(False)
            return
        self.grid.update(self.titles, self.ws.inputCmdOutput(self.wsn))
        self.Show()
        event.Skip(False)

    def ws_selectedDEL(self, event):
        error = self.hj.worksheets.redo()
        if len(error) > 0:
            wx.MessageBox(error,"",wx.OK, self)
            event.Skip(False)
            return
        self.refreshSelection()
        event.Skip(False)

    def ws_selectedREDO(self, event):
        change = self.hj.worksheets.changes.nextChange()
        error = self.hj.worksheets.redo()
        if error:
            wx.MessageBox(error,"",wx.OK, self)
            event.Skip(False)
            return
        if self.hj.dbworksheets_state:
            print(self.hj.dbworksheets_state)
        error = self.hj.push(change)
        if error:
            print("Error"+error+"*")
            wx.MessageBox(error,"",wx.OK, self)
            if not self.hj.worksheets.undo():
                wx.MessageBox("Failed to undo","",wx.OK, self)
            event.Skip(False)
        wsn = self.hj.worksheets.wsnCurrentChange()
        if wsn:
            self.wsn = wsn
        self.refreshSelection()
        event.Skip(False)

    def ws_selectedUNDO(self, event):
        if not self.hj.worksheets.undo():
            wx.MessageBox("Nothing to undo","",wx.OK, self)
            event.Skip(False)
            return
        self.refreshSelection()
        event.Skip(False)

    def ws_selectedNEW(self, event):
        if self.ws_selection.GetValue() == "new worksheet":
            self.addButton.Hide()
            QueryParams(parent=self, title="New worksheet name",
                 style=wx.OK | wx.NO, params={"Worksheet name": "str"}, selected={}, verify=None, sample=None, descriptions={}, on_close=self.wsname_close, getOptions=self.ws.paramsCmd)
        else:
            self.wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
            self.addButton.Show()
            self.grid.update(self.titles, self.ws.inputCmdOutput(self.wsn))
            self.refreshSelection()
        event.Skip(False)

    def wsname_close(self, event) -> None:
        qp = event.GetEventObject()
        if qp.res != wx.OK:
            event.Skip()
            return
        (self.wsn, typ) = qp.getValue("Worksheet name", "str")
        if not self.wsn:
            event.Skip()
            return
        error = self.ws.addSheet(uuid.uuid4(),self.wsn)
        if error:
            wx.MessageBox(
                "Faild: "+error,
                "",
                wx.OK, self)
            event.Skip()
            return
        self.ws_selection.Clear()
        self.ws_selection.Append(self.ws.titles())
        self.ws_selection.Append("new worksheet")
        self.addButton.Show()
        self.grid.update(self.titles, self.ws.inputCmdOutput(self.wsn))
        event.Skip()

    def ws_verify(self, qp: QueryParams) -> str:
        self.wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        uuid = qp.data
        cmd = self.ws.getCmdUuid(uuid)
        if cmd:
            oldselected=self.ws.paramsCmd(cmd,at=None)
        else:
            oldselected={}
        selected = qp.getSelected()
        cmdname = list(selected.keys())[0]
        cmdname=cmdname[0:cmdname.find(".")]
        return self.ws.updateCmd(wsn=self.wsn, cmdUuid=uuid, cmdname=cmdname, oldselected=oldselected, selected=selected)

    def ws_sample(self, title:str) -> None:
        WiSampleGrid(title=title, remoteAddr=self.congregation, mudp=self.mudp)

    def OnRowClick(self, event):
        row = event.GetRow()
        if row == -1:
            event.Skip(False)
            return
        # outputs = self.grid.grid.GetCellValue(row, 2)
        self.wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        self.cmd = self.ws.sheetCmds(self.wsn)[row]
        cmdname = MCmd.name(self.cmd)
        uuid = MCmd.uuid(self.cmd)
        (params, selected, descriptions) = self.ws.paramsCmd(cmd=self.cmd, at=cmdname)
        QueryParams(parent=self, title=self.wsn+":"+uuid,
             style=wx.OK | wx.CANCEL | wx.CAPTION | wx.NO, params=params,
             selected=selected, descriptions=descriptions, verify=self.ws_verify, sample=self.ws_sample, on_close=self.ws_close, data=uuid, getOptions=self.ws.paramsCmd)
        event.Skip(False)

    def ws_close(self, event) -> None:
        """ Close edit command window. """
        self.wsn = self.ws.uuidAtIdx(self.ws_selection.GetSelection())
        qp = event.GetEventObject()
        if qp.res == wx.OK:
            errors = self.ws_verify(qp)
            if errors:
                wx.MessageBox(
                    "Faild: "+errors,
                    "",
                    wx.OK, self)
                event.Skip()
                return
            # cmd = self.ws.getCmdUuid(uuid=qp.data)
            # self.ws.purgeCmd(cmd)
            self.grid.update(self.titles, self.ws.inputCmdOutput(self.wsn))
        elif qp.res == wx.CANCEL:
            self.ws.deleteCmdByOutputs(wsn=self.wsn,outputs=qp.data)
            self.grid.update(self.titles, self.ws.inputCmdOutput(self.wsn))
        event.Skip()

    @staticmethod
    def main():
        parser = argparse.ArgumentParser(description="Wi")
        parser.add_argument('--dir', help="worksheet dir")
        parser.add_argument('--ip', help="Congregation IP address, default is the loop around")
        parser.add_argument('--port', help="Congregation Port number, default is 1234")
        parser.add_argument('-d', '--debug', help="activate debugging", action="store_true")
        args = parser.parse_args()
        if args.dir is None:
            args.dir = "worksheets"
        if args.ip is None:
            args.ip = ""
        if args.port is None:
            args.port = "59990"
        app = wx.App(0)
        # TODO; change the iconized image.
        # import Tkinter
        # from Tkinter import Tk
        # root = Tk()
        # img = Tkinter.Image("photo", file="appicon.gif")
        # root.tk.call('wm','iconphoto',root._w,img)
        try:
            WiWS(debug=args.debug, wsdir=args.dir, congregation=(args.ip, int(args.port)))
        except Exception:
            traceback.print_exc()
            return
        app.MainLoop()


if __name__ == "__main__":
    WiWS.main()
