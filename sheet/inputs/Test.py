from sheet.input import Input
from sheet.ci import Result
import pandas as pd


class Test(Input):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.columns = ["retstr", "retint", "retpassword", "retdatetime"]

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
            }
        }

    def constraints(self, result: Result) -> str:
        return ""

    def exec(self, result: Result, params: dict) -> pd.DataFrame:
        df = pd.DataFrame(columns=self.columns)
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
                    d[field] = "20210808 11:10:22"
                else:
                    raise Exception(typ)
            row = len(result)
            for k in self.columns:
                df.at[row, k] = d[k]
        return df
