# Python

## Package, module and import

Package is a directory of modules. Module is a text file containing python code.

Directory containing modules must have a file called __init__.py. The file must exist even if it's just an empty file, it also can contain python code which is executed as the package is loaded.

Importing modules using the package name has the convention of one or more "package." followed by the module name. For example, "from fred.bloggs.module1 import Function1" imports Function1 from file fred/bloggs/module1.py

Importing a module from the same package must not specify a package name, rather just the module name, for example, from "module1 import Function1" when the module importing is also in package "fred.bloggs".

## Polymophic variables.

Python has types, for example, Int. All values have a type, for example, value 1 has the type Int. Variable are polymorphic which means they take on the type of the value they are assigned, for example, i=1 means the type of i is Int, and i="A" means the type of i has changed to Str.

Notes:
* methods and functions are polymorphic which means the parameters can be any type. Type checking is something that has to be added to a function within the body of the function when the function is designed to work with a particular type of parameter.
Cons:
* Type hints can be added to function prototypes and are used by IDEs that statically analyse the code to determine the type of a parameter passed into the function and compare with the hints in the function prototype. For example, "funk(i: int, s: str)" and funk(i="2",s=2) would generate a type error in most IDEs.

