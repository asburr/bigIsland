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
# A quick example of a timer event being used
# to update Window's content.
import wx

class clock_example(wx.Frame):
    def __init__(self):
        wx.Frame.__init__(self, parent=None, title="clock example")
        self.panel = wx.Panel(self)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.sizer)
        self.value = 1
        self.label = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE, value=str(self.value))
        self.sizer.Add(self.label, proportion=1, flag=wx.EXPAND)
        self.stopButton = wx.Button(self.panel, label="STOP")
        self.stopButton.Bind(wx.EVT_BUTTON, self.on_stop)
        self.sizer.Add(self.stopButton, proportion=1, flag=wx.EXPAND)
        self.startButton = wx.Button(self.panel, label="START")
        self.startButton.Bind(wx.EVT_BUTTON, self.on_start)
        self.sizer.Add(self.startButton, proportion=1, flag=wx.EXPAND)
        self.cloneButton = wx.Button(self.panel, label="CLONE")
        self.cloneButton.Bind(wx.EVT_BUTTON, self.on_clone)
        self.sizer.Add(self.cloneButton, proportion=1, flag=wx.EXPAND)
        self.timer = wx.PyTimer(self.ClockTimer)
        self.timer.Start(1000)
        self.panel.Layout()
        self.Layout()
        self.Show()

    def ClockTimer(self):
        self.value += 1
        self.label.SetValue(str(self.value))

    def on_stop(self, _event):
        self.timer.Stop()

    def on_start(self, _event):
        self.timer.Start()

    def on_clone(self, _event):
        clock_example()

    @staticmethod
    def main():
        app = wx.App(0)
        clock_example()
        app.MainLoop()

if __name__ == "__main__":
    clock_example.main()
