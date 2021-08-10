from sheet.input import Input
from sheet.result import Result
from discovery.src.discovery import SchemaDiscovery
from discovery.src.JSONParser import JSONParser
import json
import pandas as pd


class Load(Input):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.discovery_columns = ["added", "field", "example"]

    @staticmethod
    def name() -> str:
        return "Load"

    sample = "path to sample file"
    discovery = "path to Discovery file"

    @staticmethod
    def usage() -> dict:
        return {
            "params": {
                Load.sample: "pathi",
                Load.discovery: "path",
                "training": "bool",
                "debug": "bool"
            },
            "required": [
                Load.sample, Load.discovery
            ],
            "defaults": {
                "debug": False, "training": False
            }
        }

    def constraints(self, result: Result) -> str:
        return ""

    def exec(self, result: Result, params: dict) -> pd.DataFrame:
        if params["training"]:
            return self.discovery(result, params)
        return self.load(result, params)
        
    def discovery(self, result: Result, params: dict) -> pd.DataFrame:
        oldjs = SchemaDiscovery(debug=params["debug"])
        js = SchemaDiscovery(debug=params["debug"])
        try:  # try to read any existing discovery.
            JSONParser(oldjs).parser(params[Load.discovery])
            JSONParser(js).parser(params[Load.discovery])
            js.ageOff()
        except Exception:
            # drop thru to create the new discovery.
            pass
        with open(params[Load.sample], "r") as fp:
            js.load(json.load(fp))
            # Save new Load.
            try:
                with open(params[Load.discovery], "w") as fp:
                    js.jdump(fp)
            except Exception:
                print("ERROR failed to save Load to " +
                      params[Load.discovery])
                pass
        df = pd.DataFrame(columns=self.discovery_columns)
        for d in js.diff(oldjs):
            row = len(result)
            for k in self.discovery_columns:
                df.at[row, k] = d[k]
        return df

    def load(self, result: Result, params: dict) -> pd.DataFrame:
        oldjs = JSONSchemaLoad(debug=False)
        js = JSONSchemaLoad(debug=params["debug"])
        try:  # Read discovery.
            with open(params[Load.discovery], "r") as fp:
                oldjs.jload(fp)
            with open(params[Load.discovery], "r") as fp:
                js.jload(fp)
        except Exception:
            print("ERROR: failed to open discovery file " +
                  params[Load.discovery])
            return None
        with open(params[Load.sample], "r") as fp:
            js.load(json.load(fp))
            try:  # Save new Load.
                with open(params[Load.discovery], "w") as fp:
                    js.jdump(fp)
            except Exception:
                print("ERROR failed to save Load to " +
                      params[Load.discovery])
                pass
        df = pd.DataFrame(columns=self.columns)
        yield df
        df = pd.DataFrame(columns=self.columns)
        for d in js.diff(oldjs):
            row = len(result)
            for k in self.columns:
                df.at[row, k] = d[k]
        yield df