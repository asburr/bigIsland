from sheet.input import Input
from sheet.result import Result
import pandas as pd
import re
import traceback


class Filter(Input):
    def __init__(self, cfg: dict):
        super().__init__(cfg)

    @staticmethod
    def name() -> str:
        return "Filter"
    
    @staticmethod
    def usage() -> dict:
        return {
            "params": {
                "remove_row": "str",
                "include_row": "str",
                "remove_column": "str",
                "include_column": "str",
                "group_by_column": "str",
                "sum_column": "str",
                "count_rows": "str",
                "debug": "bool"
            },
            "required": [
            ],
            "defaults": {
                "debug": False
            }
        }
        """ Need to include the following usage details for the user..how??
           for example,
           s -R a == 1 - removes rows where column a has the value 1
           s -r b == 2 - include rows where column nb has the value 2
           s -C a_*,b_* - exclude columns where name matched a_* or b_*
           s -c a_*,b_* - include columns where name matched a_* or b_*
           s -s b -g a - sum column b partitioned (grouped by) column a 
           s -n count -g a - count rows partitioned (grouped by) column a
           """

    def constraints(self, result: Result) -> str:
        if result == None or len(result) == 0:
            return "There are no results, need results to filter"
        return ""

    def exec(self, result: Result, params: dict) -> pd.DataFrame:
        if (not params["remove_row"] and not params["include_row"] and
            not params["remove_column"] and not params["include_column"] and
            not params["group_by_column"] and not params["sum_column"]
        ):
            print("ERROR: bad params")
            return None
        columns = result.df.columns.tolist()
        df = result.df.copy()
        if params["remove_row"]:
            try:
                df.query(expr=params["remove_row"], inplace=True)
                if df.equals(result.df):
                    print("ERROR: no column matching " + params["remove_row"])
                    return None
            except Exception as e:
                print("Error in " + params["remove_row"] + " " + str(e))
                return None
        if params["include_row"]:
            try:
                df.query(expr=params["include_row"], inplace=True)
            except Exception as e:
                print("Error in " + params["include_row"] + " " + str(e))
                return None
        if params["remove_column"]:
            try:
                for pattern in params["remove_column"].split(","):
                    pat = re.compile(pattern)
                    c = 0
                    for col in columns:
                        if pat.match(col):
                            c += 1
                            df.drop(columns=col, inplace=True)
                    if not c:
                        print("ERROR: no column matching " + pattern)
                        return None
            except Exception as e:
                print("Error in " + params["remove_column"] + " " + str(e))
                return None
        if params["include_column"]:
            try:
                ic = set()
                for pattern in params["include_column"].split(","):
                    pat = re.compile(pattern, re.IGNORECASE)
                    c = 0
                    for col in columns:
                        if pat.match(col):
                            c += 1
                            ic.add(col)
                    if not c:
                        print("ERROR: no column matching " + pattern)
                        return None
                for col in columns:
                    if col not in ic:
                        df.drop(columns=col, inplace=True)
            except Exception as e:
                print("Error in " + params["include_column"] + " " + str(e))
                return None
        if params["group_by_column"] and (
            params["sum_column"] or
            params["count_rows"]
        ):
            try:
                gb = set()
                for pattern in params["group_by_column"].split(","):
                    pat = re.compile(pattern)
                    for col in columns:
                        if pat.match(col):
                            gb.add(col)
                if not gb:
                    print("Error in -g " +
                          params["group_by_column"] + " -s " +
                          " not columns selected")
                    return None
                if params["sum_column"]:
                    sc = set()
                    for pattern in params["sum_column"].split(","):
                        pat = re.compile(pattern)
                        for col in columns:
                            if pat.match(col):
                                sc.add(col)
                    if not sc:
                        print("Error in -s " +
                              params["sum_column"] + " -s " +
                              " not columns selected")
                        return None
                    for col in columns:
                        if col in gb and col in sc:
                            print("Error in -g " +
                                  params["group_by_column"] + " -s " +
                                  params["sum_column"] + " " +
                                  " select the same col " + col)
                            return None
                    print(df)
                    print(gb)
                    print(sc)
                    df = df.groupby(list(gb))[list(sc)].sum().reset_index()
                    print(df)
                elif params["count_rows"]:
                    col = params["count_rows"]
                    if col in columns:
                        print("ERROR: column " + col + " already exists")
                        return None
                    df = df.groupby(list(gb)).size().reset_index(name=col)
            except Exception:
                traceback.print_exc()
                print("Error in " +
                      params["group_by_column"] + " " +
                      str(params["sum_column"]) + " " +
                      str(params["count_rows"])
                      )
                return None
        if df.equals(result.df):
            return None
        return df
    
        
