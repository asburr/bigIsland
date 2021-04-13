from sheet.input import Input
from discovery.src.jsonschemadiscovery import JSONSchemaDiscovery
import json


class Discovery(Input):
    def __init__(self, cfg: dict):
        super().__init__(cfg)

    @staticmethod
    def name() -> str:
        return "Discovery"

    sample = "path to sample file"
    discovery = "path to discovery file"

    @staticmethod
    def usage() -> dict:
        return {
            "params": {
                Discovery.sample: "pathi",
                Discovery.discovery: "path",
                "debug": "bool"
            },
            "required": [
                Discovery.sample, Discovery.discovery
            ],
            "defaults": {
                "debug": False
            },
            "return": {
                "added": "bool", "field": "str", "example": "str"
            },
            "map": {
            },
            "constraints": {
            }
        }

    @staticmethod
    def exec(params: dict, scratchPad: dict) -> dict:
        oldjs = JSONSchemaDiscovery(debug=False)
        js = JSONSchemaDiscovery(debug=params["debug"])
        if Discovery.discovery in params:
            # Read old discovery.
            try:
                with open(params[Discovery.discovery], "r") as fp:
                    oldjs.jload(fp)
                with open(params[Discovery.discovery], "r") as fp:
                    js.jload(fp)
                js.ageOff()
            except Exception:
                pass
        with open(params[Discovery.sample], "r") as fp:
            js.load(json.load(fp))
        if Discovery.discovery in params:
            # Save new discovery.
            try:
                with open(params[Discovery.discovery], "w") as fp:
                    js.jdump(fp)
            except Exception:
                print("ERROR failed to save discovery to " +
                      params[Discovery.discovery])
                pass
        for d in js.diff(oldjs):
            yield d
