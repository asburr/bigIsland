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
import os
from hallelujah.cmds.files import Files
from magpie.src.musage import MUsage
import time


class TestFiles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        TestFiles.musage=MUsage()
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.teardown = [
            ["purgeDir", "test/filestesting_tmp" ],
            ["purgeDir", "test/filestesting_tmp_PF" ],
            ["purgeDir", "test/filestesting_tmp_archive" ],
        ]
        for i,x in enumerate(self.teardown):
            self._runCmd(i,x)
        setup = [
            ["mkdir", "test/filestesting_tmp" ],
            ["mkdir", "test/filestesting_tmp_PF" ],
            ["mkdir", "test/filestesting_tmp_archive" ],
        ]
        for i,x in enumerate(setup):
            self._runCmd(i,x)
        cmd = {
            "uuid": "25f30f46-cd0a-46f2-812e-2e527e78a059",
            "version": "1",
            "cmd": "files",
            "root": "test",
            "path": {
                "path": "test/filestesting_tmp",
                "order": "oldest",
                "depth": 1,
                "readonly": "test/filestesting_tmp_PF",
                "feeds": [
                    {"feed": "test.pcap", "regex": ".*\\.pcap"},
                    {"feed": "test.new", "regex": ".*"}
                ]
            }
        }
        self.files = Files(cmd)
        cmd["archive"] = {
            "path": "test/filestesting_tmp_archive",
            "dateSubDir": "day",
            "purge": 70,
            "diskUsage": 70,
            "onError": "",
        }
        self.testcases = [
            ["touch", "test/filestesting_tmp/test1.pcap" ],
            ["touch", "test/filestesting_tmp/test1.tmp" ],
            ["sleep", "0.5"],
            ["touch", "test/filestesting_tmp/test2.pcap" ],
            ["touch", "test/filestesting_tmp/test2.tmp" ],
            ["sleep", "0.5"],
            ["files", ""],
            ["disco", ""],
            ["schema", ""],
            ["touch", "test/filestesting_tmp/test3.pcap" ],
            ["touch", "test/filestesting_tmp/test3.tmp" ],
            ["sleep", "0.5"],
            ["rm", "test/filestesting_tmp/test1.pcap" ],
            ["rm", "test/filestesting_tmp/test1.tmp" ],
            ["rm", "test/filestesting_tmp/test3.pcap" ],
            ["rm", "test/filestesting_tmp/test3.tmp" ],
            ["sleep", "0.5"],
            ["rm", "test/filestesting_tmp/test2.tmp" ],
            ["rm", "test/filestesting_tmp/test2.pcap" ],
        ]

    def tearDown(self):
        for i, x in enumerate(self.teardown):
            self._runCmd(i,x)

    def _runCmd(self,i:int, tc: list) -> bool:
        (cmd, param) = tc
        print(str(i)+" "+str(tc))
        if cmd == "mkdir":
            os.mkdir(param)
        elif cmd == "rmdir":
            os.rmdir(param)
        elif cmd == "purgeDir":
            if os.path.isdir(param):
                Files.removeNest(param)
        elif cmd == "touch":
            with open(param,"w"):
                pass
        elif cmd == "sleep":
            time.sleep(float(param))
        elif cmd == "rm":
            os.remove(param)
        elif cmd == "files":
            self.files.execute(TestFiles.musage)
        elif cmd == "sample":
            for (b,d) in self.files.sample(feedName=None,n=10):
                print(str(b)+" "+str(d))
        elif cmd == "disco":
            print(f"Disco:{self.files.disco.dumps()}")
        elif cmd == "schema":
            print(f"Disco:{self.files.schema()}")
        else:
            raise Exception("Unexpected cmd #"+str(i)+" "+cmd)
        return True
    
    def test_files(self):
        for i,x in enumerate(self.testcases):
            self._runCmd(i,x)
            