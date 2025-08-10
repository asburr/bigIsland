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
import unittest
from hallelujah.cmds.cmd import Feed, Feeds, Cmd
from magpie.src.musage import MUsage


class Tcmd(Cmd):
    def data(self, feedName: str, n:int) -> list:
        return ["a","b"]
    def process(self) -> object:
        return "a"
    
class TestCmd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_cmd(self):
        """
        Add one Feed called "test".
        Add one Tcmd and execute it on Feed "test".
        """
        feed = Feed("test")
        feeds=Feeds()
        try:
            feeds.sanity()
        except Exception as e:
            assert str(e) == "No feeds!"
        feeds.add(feed)
        feeds.sanity()
        assert feeds.get("test") == feed
        for x in feeds.yields():
            assert x.name == "test"
        cmd=Tcmd()
        cmd.execute(MUsage())
        assert cmd.schema() != {}
        assert cmd.data("test",2) == ["a","b"]