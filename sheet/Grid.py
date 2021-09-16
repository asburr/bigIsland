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

# WiGrid
# Given a list o titles and a grid (row col) of values, Grid displays
# a grid. The Titles and row_col may be updated, at any time.
# A callback when left click on a row is supported.
#

import traceback

try:
    import wx.grid
except Exception:
    print("Failed to import wx, install instructions:")
    print("sudo apt-get install -y libsdl2-2.0-0")
    print("sudo apt-get install libgtk-3-dev")
    print("pip3 install -U -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-18.04 wxPython")
    exit(1)

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
        # self.grid.SetSize(self.grid.DoGetBestSize())
        