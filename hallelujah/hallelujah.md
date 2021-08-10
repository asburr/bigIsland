# Introduction

Data is distributed across Jahs. Hallelu controls the Jahs.

Users communicate directly with Hallelu.

Initially, there is one Hallelu with no jahs. This Hallelu creates others
to perform user requests.

User requests include:
* Loading of data from disk;
* The schema for the data;
* Summary stats for the data;
* Extraction of data.

Another Hallelu is created to manage the jahs that receive extracted data.

# Walk thru

* Create initial Hallelu(1);
* User requests loading of data from files in a directory;
      d = {"cmd": "", "path": <path> "depth": 1, "ageOff": 0,
           "snapshot": "^(.*)$"}
    * hallelu = execute(d)
        <options>:
        * dirdepth: 0 infinity or, 1 parent dir only;
        * readOnly: path to writable directory to track the loaded files;
        * ageOff: 0 never, N minutes to hold the data;
        * snapshot: path regex, first captured value being the source.
        * Return: existing Hallelu when already loading from <path>.
* Hallelu(1) creates Hallelu(2) to run the load cmd.

* Hallelu(2) creates one jah to start load the files.
    * jah(1) measures load time and memory used.
* Hallelu(2) receives loading reports for each file loaded by Jah(1).
    * Report contains:
        * File size
        * elapsed time for loading
        * memory used and free.
* Hallelu(2)

* Hallelu(2) counts the files that remain to be loaded.
* load data into jah(1)