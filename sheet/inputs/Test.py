from typing import Iterable
from sheet.input import Input


class Test(Input):
    def __init__(self, cfg: dict):
        super().__init__(cfg)

    @staticmethod
    def name() -> str:
        return "TestInput"

    @staticmethod
    def usage() -> dict:
        return {
            "params": {
                "str": "str",
                "count": "int",
                "password": "password",
                "datetime": "YYYYMMDD HH:MM:SS"
            },
            # Query is active when there are values for all of the required params.
            "required": [
                "str", "count", "password", "datetime"
            ],
            "defaults": {
                "str": "helloworld",
                "count": "123",
                "password": "should not be a default password",
                "datetime": "20210210 10:10:10"
            },
            "return": {
                "retstr": "str", "retint": "int", "retpassword": "password", "retdatetime": "datetime"
            },
            # Map parameter names to the return names.
            "map": {
                "str": "retstr", "int": "retint", "password": "retpassword", "datetime": "retdatetime"
            },
            # Query is active when the following constraints are met.
            "constraints": {
                "str": "helloworld"
            }
        }

    @staticmethod
    def exec(params: dict, scratchPad: dict) -> Iterable[dict]:
        for i in range(params["count"]):
            d = {}
            for field, typ in Test.usage()["return"].items():
                if typ == "str":
                    d[field] = "helloworld"
                elif typ == "int":
                    d[field] = "123"
                elif typ == "password":
                    d[field] = "pass1"
                elif typ == "datetime":
                    d[field] = "20211001 11:10:22"
                else:
                    raise Exception(typ)
            yield d
