# Docker

<details><summary>TODO Overlay</summary><u>Figure out how overlaid networks works across multiple hosts, document it.</u></details>

Docker provides images, Containers, and networks. Images enable fast and simple and reliable setup of Containers. Containers are one or more applications running a self contained Image. Networks provide a communication channel between Containers that connect to that network. A network can span hosts, providing Container communication across many hosts. A host can have many networks to provide  clusters on the same host.

Image is the means to package an operating environment. These environments are self contained, a running version of an Image is called a Container. Images and Containers reliably deploy a fully tested environment onto a machine that otherwise is not configured to support the application.

Containers use directly the underlying Operating System resources and drivers. This makes Containers a lightweight environment, without the overhead of a full virtual environment. Directly using the operating systems does tie the Linux Images to run in Containers on Linux hosts, and Windows Images to run in Containers on Windows hosts. There is no exception, consider the Linux Docker which runs on Windows and Mac hosts, the Linux Container runs in a full Linux Virtual Machine (VM) and the VM runs on the Windows/Mac host.

Containers run there own image that is separate from the image running in other containers on the same host. Separate images means a problem is a container does not affect another Container. Separate images means each Container can run a different version of an image, on the same host. For example, a development image and production image may run in two containers on the same host. Integration tools can manage product releases in Container images, deploying the image first to development, testing, and then production.

Networks are provided by Docker. Docker configures the underlining operating system to provide IP communication between Containers on different hosts and also between containers on the same host.

File system is provided by Docker. Docker  

# Installing Docker on Ubuntu

```sh
sudo apt update
sudo apt install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu bionic stable"
sudo apt update
apt-cache policy docker-ce
sudo apt install docker-ce=18.03.1~ce~3-0~ubuntu
sudo systemctl status docker
sudo usermod -aG docker asburr
<reboot>
```

# Check that docker is running

Docker "run" downloads the image from Docker Hub, run it again to see it run without the downloading. 
```sh
docker run hello-world
docker run hello-world
# Search hub
docker search hello-world
# list locally installed images
docker images
docker image rm IMAGE <image>
```

# Docker Configuration

Configuration can be provided in a JSON format. Location /etc/docker/daemon.json, or provided thru the option --config-file. "info" displays the settings.
```sh
# Display options
docker info
# Set options.
docker run -it --net=host --config-file=docker.json ubuntu /bin/bash
```

# Containers

```sh
# Start a container running image(ubuntu), interactively (-i) with a console/tty (-t), use the bash shell,
docker run -it ubuntu /bin/bash
```

What containers are running and attach?
```sh
docker ps -as
CONTAINER ID        IMAGE               COMMAND             CREATED             STATUS            PORTS               NAMES               SIZE
57d07bd4d345        ubuntu              "/bin/bash"         53 seconds ago      Up 52 seconds     boring_khorana      0B (virtual 64.2MB)

docker attach 57d07bd4d345
root@57d07bd4d345:/#
```

Restart a suspended container, remove, and start a new.
```sh
# Restart
docker start <containerId>
# remove
docker container rm <containerId>
# remove all containers
docker container rm $(docker ps –a –q)
# Start a new container
docker run [options] <image> [command] [argument]
# nicely stop a container.
docker stop --time=20 container_id
# quickly stop a container
docker kill container_id
```

# Creating an image without and with Dockerfile

## Create an image with network utils without Dockerfile

```sh
# Start with the default ubuntu image.
docker run -it --net=host ubuntu /bin/bash
apt-get update
# install the networking packages.
apt-get install iputils-ping
# ifconfig
apt-get install net-tools
apt install iftop
apt install vnstat
# ip route,
apt install iproute2
# test them
ping -c2 www.google.ca
ifconfig
ip route
exit
# Create a new image, with the network packages.
$docker commit $(docker ps -l -q) ubuntu-network
# Drop the container.
$docker rm $(docker ps -l -q)
$ docker images
REPOSITORY          TAG                 IMAGE ID            CREATED              SIZE
ubuntu-network      latest              97366df8578d        About a minute ago   97.5MB
```

## Image automation using Dockerfile

A Dockerfile is there to captured the instructions to create the image, and to start the command that are to run in the container.
```sh
# Dockerfile_network
FROM ubuntu
RUN apt-get --assume-yes update \
 && apt-get --assume-yes install iputils-ping \
 && apt-get --assume-yes install net-tools \
 && apt install iftop \
 && apt install vnstat \
 && apt install iproute2

# target image (-t), specify the host's network (--network host) to download , 
$ docker build -t ubuntu-network -f Dockerfile_network --network host .
$ docker images
REPOSITORY          TAG                 IMAGE ID            CREATED              SIZE
ubuntu-network      latest              97366df8578d        About a minute ago   97.5MB
# test the image,
$ docker run -ti ubuntu-network bash
ping -c2 www.google.ca
root@0c17b71b16a9:/# ifconfig
root@0c17b71b16a9:/# ip route
root@0c17b71b16a9:/# exit
```

# Networking in Docker

Docker network choices are: bridge, none, and host. Default is called docker0 bridge networking; It is a bridge between the containers.

Docker commands for networking,
```sh
# List the active networks
docker network ls
# Inspect a network.
docker network inspect host
docker network inspect bridge
```

## Bridge

Bridge networks apply to containers running on the same Docker host. For communication among containers running on different Docker daemon hosts, use an overlay network. Bridge Network is setup by default, Docker creates a network that assigns an IP address to each Container and connects the containers on the same host.

The bridge is seen from the Linux prompt:
```sh
ip addr show | grep br
brctl show
```

Example Bridge, two containers (A1 and A2) can ping each other by their names or IP address.
```sh
docker network create Anet
docker network ls | grep Anet
4858e014a3a2        Anet                bridge              local
# Console 1:
docker run -it --net=Anet --name=A1 ubuntu-network /bin/bash
ping A2
# Console 2:
docker run -it --net=Anet --name=A2 ubuntu-network /bin/bash
pint A1
```

Remove network,
```sh
docker network rm Anet
```

One cannot assign an IP address to a container, this requires user-configured subnets.
```sh
docker run -it --net=Anet --name=A1 --ip=172.18.0.3 ubuntu-network /bin/bash
docker: Error response from daemon: user specified IP address is supported only when connecting to networks with user configured subnets.
```

## User-configured subnets.

Docker uses the default 172.17.0.0/16 subnet for container networking. To configure Docker to use a different subnet,
```sh
docker network create --driver=bridge --subnet=172.28.0.0/16 --ip-range=172.28.5.0/24 --gateway=172.28.5.254 Anet
```
Now we can assign IP address to the container,
```sh
docker run -it --net=Anet --name=A1 --ip=172.28.0.3 ubuntu-network /bin/bash
docker run -it --net=Anet --name=A2 --ip=172.28.0.4 ubuntu-network /bin/bash
ping 172.28.0.3
ping 172.28.0.4
```

# host

"host" is the host’s network, only available on Linux hosts. The configuration inside the container matches the configuration outside the container.

## Container's ports accessible to others.

Publish ports to make a port available to services outside of Docker, or to Docker containers which are not connected to the container's network, use the --publish or -p flag.
```sh
# Map TCP port 80 to 81 on the Docker host. 
-p 81:80/tcp
# Map UDP port 80 to 81 on the Docker host. 
-p 81:80/udp
# Map TCP port 80 to 81 on the host for connections to IP 192.168.1.100:81
-p 192.168.1.100:81:80/tcp
```

# TODO

Why would we do this? Apparently to allow external access to the bridged network (LAN), in what case would this be needed?
```sh
sudo iptables -A FORWARD -i eth0 -s  -j ACCEPT
```

## Distributed network among multiple Docker daemon hosts.

The overlay network driver creates a distributed network among multiple Docker daemon hosts. Can not having more than 256 IPs in a single overlay network. Omit the --gateway flag and the Engine selects one for you.
```sh
docker network create --help
# if supports multi subnet,
docker network create -d overlay --subnet=192.168.10.0/25 --subnet=192.168.20.0/25 --gateway=192.168.10.100 --gateway=192.168.20.100 --aux-address="my-router=192.168.10.5" --aux-address="my-switch=192.168.10.6" --aux-address="my-printer=192.168.20.5" --aux-address="my-nas=192.168.20.6" my-multihost-network
```

## When and why docker needs Network Address Translation (NAT)?

```sh
# IP Nating.
iptables -t nat -L -n
```

## none

"None" is a local loopback interface (i.e., no external network interface).

# Volume

## Temporary file system

If you’re running Docker on Linux, tmpfs mounts is an option. When you create a container with a tmpfs mount, the container can create files outside the container’s writable layer.

```sh
docker run -d -it --name tmptest --mount type=tmpfs,destination=/app bash
docker container stop tmptest
docker container rm tmptest
```

## Disk file system

```sh
# Create directory on host,
mkdir -p /data
# Create docker volume over directory,
docker volume create --driver local --opt type=none --opt device=/data --opt o=bind --name=test
# Mount /data to /mymount in Container
docker run -it --mount source=test,target=/mymount bash
```
# Docker footprint

30 to 40 M of memory is reserved when starting a basic Ubuntu container.

# Container processes.

Each container spawns two processes on Unix. These processes are called the containerd-shim and the docker run command that is we used to start the container. The containerd-shim runs as root.

```sh
# Run the container,
$ docker run -ti ubuntu-network bash

# In another window, use the ps command to find that docker creates two
# processes for the above container.
$ ps -ef | grep docker
asburr   18732  5510  0 21:25 pts/2    00:00:00 docker run -ti ubuntu-network bash
root     18771  1549  0 21:25 ?        00:00:00 containerd-shim -namespace moby -workdir /var/lib/containerd/io.containerd.runtime.v1.linux/moby/88ee2c1e2b5a291cc943a005ddf2f29a513ffca0a3d5cebb4887d2b7218ebaab -address /run/containerd/containerd.sock -containerd-binary /usr/bin/containerd -runtime-root /var/run/docker/runtime-runc

# There is the docker daemon itself,
root      2203     1  0 16:18 ?        00:00:06 /usr/bin/dockerd -H fd:// --containerd=/run/containerd/containerd.sock
```

```sh
# Start a second container,
$ docker run -ti ubuntu-network bash

# Here's threads.
$ ps -ef | grep docker
asburr   19200  8675  0 21:34 pts/3    00:00:00 docker run -ti ubuntu-network bash
root     19236  1549  0 21:34 ?        00:00:00 containerd-shim -namespace moby -workdir /var/lib/containerd/io.containerd.runtime.v1.linux/moby/01f099f45def1b97630ff4699eed7868256c94980f059ca6f5723dec67814838 -address /run/containerd/containerd.sock -containerd-binary /usr/bin/containerd -runtime-root /var/run/docker/runtime-runc
```

# Footprints

```sh
# Before starting the containers,
$ free
              total        used        free      shared  buff/cache   available
Mem:        7721960     2049172     3587424      477152     2085364     4926792
Swap:      15871996           0    15871996
# After one container, +32644kb (32mb)
$ free
              total        used        free      shared  buff/cache   available
Mem:        7721960     2081816     3480972      478752     2159172     4892108
Swap:      15871996           0    15871996
# After second container, +39380kb (39mb)
$ free
              total        used        free      shared  buff/cache   available
Mem:        7721960     2121196     3432808      486632     2167956     4844592
Swap:      15871996           0    15871996
# After shutdown of second container, −31000kb (31mb)
$ free
              total        used        free      shared  buff/cache   available
Mem:        7721960     2090196     3462372      488144     2169392     4874220
Swap:      15871996           0    15871996
# After shutdown of all containers, −30248kb (30mb)
$ free
              total        used        free      shared  buff/cache   available
Mem:        7721960     2059948     3490548      490344     2171464     4902372
Swap:      15871996           0    15871996
```
