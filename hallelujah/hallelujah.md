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

## The Summit Hallelu

The summits are not created by the Hallelujah database, the Summit Hallelu
is created on each host by an external component.

Summits have the same port number. File halleu_dir/hosts.json is a list of all
of the hosts, and port number
    file: hall_summit.json
    contains: port, ip

## Worksheets

Worksheet is a list of commands, in creation order. It is stored on
disk to provide persistancy after the failure of the host. The
worksheet is replayed when the host recovers. Replay is by the summit Hallelu.

The worksheet is maintained by the Summit Hallelu. Commands are added and
deleted by the Summit Hallelu.

A Hallelu is created for each command. The command is stored on disk in
a file called "hall_<id>.json" this is in addition to being stored in the
worksheet. Hallelu reads its command from the "hall_<id>.json" file.

Summit runs a command when the input(s) are ready. Some commands have no
inputs, these commands can run right away.

## Commands

Command is identified by the name of the feed it outputs.

Users send commands to a Summit. The command wont run when the feed name is
in-use by another command.

Some commands are handled by Summit, such commands are:
* lookups of feed or worksheet;
* delete of feed or worksheet.

Other commands are forwarded to the Hallelu that outputs the feed that the
command inputs.

## Deleting.

Summit is locked for the duration of a delete. Deleted commands are logically
deleted in the worksheet, they are marked as deleted but remain in the
worksheet. The deleted feed's Hallelu is shutdown, the port is closed, and the
feed is erased. The feed name(s) are changed to <name>_del_<date> in the
worksheet. It is possible to reinstate a deleted command, as long as the
<name>(s) have not been reused.
