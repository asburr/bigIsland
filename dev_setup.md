
# setting up ubuntu env.

vi ~/.bashrc

    # PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;35m\]\w\[\033[00m\]\$ '

LS_COLORS=$LS_COLORS:'di=0;35:' ; export LS_COLORS

git config --global user.email "asburr@hotmail.com"
git config --global user.name "Andrew Burr"
export EDITOR=vi

# installing LAMP 

sudo apt-get update

available applications:
  Apache
  Apache Full
  Apache Secure

sudo ufw app info "Apache Full"
Profile: Apache Full
Title: Web Server (HTTP,HTTPS)
Description: Apache v2 is the next generation....

Ports:
  80,443/tcp

Get host's IP address from Ubuntu Settings: Network, Wired, IPv4 Address.
Browse to the IP address or localhost, should see the apache2 default page.

sudo apt-get install mysql-server
sudo mysql_secure_installation

# Python

sudo apt-get install git-all
sudo apt install python3-pip
sudo apt-get install spyder3

note: start spyder thru the start menu: bottom box, search spyder, click icon to start it

# wireshark

sudo apt install tshark
sudo tcpdump -i ens33 -w test.pcap
tshark -T json -f test.pcap

# GIT

Generate SSH keys
```sh
sh-keygen -t ed25519 -c "asburr@hotmail.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

Add to git hub

```sh
login to github
under profile is settings
select ssh keys
select add key, for the name use the machine or project.
copy public key on linux, view ~/.ssh/id_ed22519.pub
Paste into github
Add it.
```

# Python module and package

* Module is a .py file.
* Package is a directory with a __init__.py file that may be empty.
* Do not reference the package when importing a module from the same package.
  I.e. from module import function.
* Do refer to the package when importing the module from another package.
  I.e. from package.module import function
* Ensure the shell variable $PYTHONPATH, or the spyder Run config per
  file called "working directory setting", is set to the root directory where
  the package is installed. I.e. export PYTHONPATH=$PWD:$PYHTONPATH