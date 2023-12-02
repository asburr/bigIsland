# Spyder
## install
Using miniconda to install spyder. Download miniconda which comes in a shell
script, verify the checksum, then run it to install miniconda.

shasum -a 256 Miniconda3-latest-Linux-x86_64.sh
chmod a+rx Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh
conda install -c anaconda git
conda install spyder=5

## config
spyder --conf-dir $PWD/spyder-py3
or, spyder.sh

## Config files
Spyder5 saves run options per file in spyder-py3/config/transient.ini. This
config file is added to git, so it can be shared with other developers who
wish to run the programs too.

TODO; transient.ini options are absolute paths. For another developer to resuse
the options requires relative paths due to the root path of /home/<user>/ being
different for each user. Tried $HOME and $PWD and "./", but so far only the
absolute path works.

## miniconda X11

Miniconda references X11 at ~/miniconda3/share/X11, but that does not exist. Have to link it to /usr/share/X11.
$ cd /home/andrew/miniconda3/share
$ ln -s /usr/share/X11 X11
