# Spyder
## install
Using miniconda to install spyder. Download miniconda which comes in a shell script, verify the checksum, then run it to install miniconda.

shasum -a 256 Miniconda3-latest-Linux-x86_64.sh
chmod a+rx Miniconda3-latest-Linux-x86_64.sh
./Miniconda3-latest-Linux-x86_64.sh
conda install -c anaconda git
conda install spyder=5

## config
spyder --conf-dir $PWD/spyder-py3
or, spyder.sh

## Config files
Spyder5 saves run options per file in spyder-py3/config/transient.ini. This config file is added to git, so it can be shared with other developers who wish to run the programs too.

