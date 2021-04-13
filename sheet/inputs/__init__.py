#!/usr/bin/env python3
ALL = []

if __name__ != "__main__":
    from os import path
    from glob import glob
    module_names = path.join(path.dirname(__file__), "*.py")
    for module_path in glob(module_names):
        if path.basename(module_path).startswith("__"):
            continue
        module_name = path.basename(module_path)[:-3]
        try:
            # same as: from module_name import input.module_name
            module = __import__(name="sheet.inputs.%s" % module_name, fromlist=[module_name])
        except ImportError as x:
            print("Disabling module \"" + module_name + "\" error: " + str(x.msg))
            continue
        ALL.append(getattr(module, module_name))
