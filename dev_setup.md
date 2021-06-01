
# setting up ubuntu env.

vi ~/.bashrc

    # PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
    PS1='${debian_chroot:+($debian_chroot)}\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;35m\]\w\[\033[00m\]\$ '

LS_COLORS=$LS_COLORS:'di=0;35:' ; export LS_COLORS


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


