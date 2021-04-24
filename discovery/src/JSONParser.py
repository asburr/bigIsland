#!/usr/bin/env python3
import json
from discovery.src.parser import Parser


class JSONParser(Parser):
    def parse(self, file: str) -> list:
        with open(file, "r") as f:
            j = json.load(f)
            j = self._wireshark(j)
            print(j)

    def _wireshark(self, obj: any) -> any:
        """Example of wireshark field names that contain values.
           "Queries": {
            "bolt.dropbox.com: type A": {
              "dns.qry.name": "bolt.dropbox.com",
              "dns.qry.type": "1"
            },
            "bolt.dropbox.com: type B": {
              "dns.qry.name": "bolt.dropbox.com",
              "dns.qry.type": "2"
            }
          }
           The work around is to collapse the field into the dictionary,
           like so:
           "Queries": [
               {
                  "__ws_summary": "bolt.dropbox.com: type A",
                  "dns.qry.name": "bolt.dropbox.com",
                  "dns.qry.type": "1"
                }, {
                "__ws_summary": "bolt.dropbox.com: type B":
                  "dns.qry.name": "bolt.dropbox.com",
                  "dns.qry.type": "2"
                }
            ]
          }
               
        """
        if isinstance(obj, dict):
            lst = list(obj.keys())
            wiresharkSummaryFields = True
            for field in lst:
                # Wireshark values in field names have ": " in
                # the field name that is a dictionary. This is true
                # for all fields.
                if ": " not in field or not isinstance(obj[field], dict):
                    wiresharkSummaryFields = False
            if wiresharkSummaryFields:
                l = []
                for field in lst:
                    v = obj[field]
                    v["__ws_summary"] = field
                    l.append(self._wireshark(v))
                return l
            else:
                for field in lst:
                    obj[field] = self._wireshark(obj[field])
                return obj
        elif isinstance(obj, list):
            lst = []
            for v in obj:
                lst.append(self._wireshark(v))
            return lst
        else:
            return obj

    @staticmethod
    def main():
        p = JSONParser()
        p.parse(file="test.json")


if __name__ == "__main__":
    JSONParser.main()