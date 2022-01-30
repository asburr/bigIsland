# kubernetes

# Node

A Node creates one or more Pods.

Nodes are temporal, can be created and destroyed by Controllers.

# Pod

A pod is an atomic unit that runs one or more containers.These containers share resources such as file volumes and network interfaces in common.

Pods are the basic unit of scheduling in Kubernetes: all containers in a pod are guaranteed to run on the same node that the pod is scheduled on. Pods are temporal, created and destroyed routinely by Controllers.

As a pod is created it is assigned a new IP address (localhost-based), UID, and port. A pod on one node should be able to access a pod on another node using the pod’s IP. Containers on a single node can communicate easily through a local interface. Communication between pods is more complicated, however, and requires a separate networking component that can transparently route traffic from a pod on one node to a pod on another.

A pod is self contained, with communication between containers in the same pod. 

# Flannel

Flannel is a virtual network that attaches IP addresses to containers

## Nodes

# Service

One or more pods is a Service.

Services are stable.

As a service is created it is assigned a virtual IP address. Users know nothing about the Pod IP addresses as the Service assigns a pod to handle user requests.

A Service manages availability and prevent bottlenecks.

# controller.

# Cronjob

Kubernetes has the idea of running periodically a container. 

```sh
$ vi application/job/cronjob.yaml
apiVersion: batch/v1beta1
kind: CronJob
metadata:
  name: hello
spec:
  schedule: "*/1 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: hello
            image: busybox
            args:
            - /bin/sh
            - -c
            - date; echo Hello from the Kubernetes cluster
          restartPolicy: OnFailure
$ kubectl create -f https://k8s.io/examples/application/job/cronjob.yaml
$ kubectl get cronjob hello
NAME    SCHEDULE      SUSPEND   ACTIVE   LAST SCHEDULE   AGE
hello   */1 * * * *   False     0        <none>          10s
$ kubectl get jobs --watch
# Replace "hello-4111706356" with the job name in your system
$ pods=$(kubectl get pods --selector=job-name=hello-4111706356 --output=jsonpath={.items[*].metadata.name})
$ kubectl logs $pods
Fri Feb 22 11:02:09 UTC 2019
Hello from the Kubernetes cluster
$ kubectl delete cronjob hello
```

## Ansible installation

```sh
$ vi ~/kube-cluster/hosts
[masters]
master ansible_host=master_ip ansible_user=root

[workers]
worker1 ansible_host=worker_1_ip ansible_user=root
worker2 ansible_host=worker_2_ip ansible_user=root

[all:vars]
ansible_python_interpreter=/usr/bin/python3
```

```sh
$ vi ~/kube-cluster/initial.yml
- hosts: all
  become: yes
  tasks:
    - name: create the 'ubuntu' user
      user: name=ubuntu append=yes state=present createhome=yes shell=/bin/bash

    - name: allow 'ubuntu' to have passwordless sudo
      lineinfile:
        dest: /etc/sudoers
        line: 'ubuntu ALL=(ALL) NOPASSWD: ALL'
        validate: 'visudo -cf %s'

    - name: set up authorized keys for the ubuntu user
      authorized_key: user=ubuntu key="{{item}}"
      with_file:
        - ~/.ssh/id_rsa.pub
$ ansible-playbook -i hosts ~/kube-cluster/initial.yml
```

```sh
$ vi ~/kube-cluster/kube-dependencies.yml
- hosts: all
  become: yes
  tasks:
   - name: install Docker
     apt:
       name: docker.io
       state: present
       update_cache: true

   - name: install APT Transport HTTPS
     apt:
       name: apt-transport-https
       state: present

   - name: add Kubernetes apt-key
     apt_key:
       url: https://packages.cloud.google.com/apt/doc/apt-key.gpg
       state: present

   - name: add Kubernetes' APT repository
     apt_repository:
      repo: deb http://apt.kubernetes.io/ kubernetes-xenial main
      state: present
      filename: 'kubernetes'

   - name: install kubelet
     apt:
       name: kubelet=1.14.0-00
       state: present
       update_cache: true

   - name: install kubeadm
     apt:
       name: kubeadm=1.14.0-00
       state: present

- hosts: master
  become: yes
  tasks:
   - name: install kubectl
     apt:
       name: kubectl=1.14.0-00
       state: present
       force: yes
$ ansible-playbook -i hosts ~/kube-cluster/kube-dependencies.yml
```
Setup the master node.

The first task initializes the cluster by running kubeadm init. Passing the argument --pod-network-cidr=10.244.0.0/16 specifies the private subnet that the pod IPs will be assigned from. Flannel uses the above subnet by default; we’re telling kubeadm to use the same subnet.

The second task creates a .kube directory at /home/ubuntu. This directory will hold configuration information such as the admin key files, which are required to connect to the cluster, and the cluster’s API address.

The third task copies the /etc/kubernetes/admin.conf file that was generated from kubeadm init to your non-root user’s home directory. This will allow you to use kubectl to access the newly-created cluster.

The last task runs kubectl apply to install Flannel. kubectl apply -f descriptor.[yml|json] is the syntax for telling kubectl to create the objects described in the descriptor.[yml|json] file. The kube-flannel.yml file contains the descriptions of objects required for setting up Flannel in the cluster.

```sh
$ vi ~/kube-cluster/master.yml
- hosts: master
  become: yes
  tasks:
    - name: initialize the cluster
      shell: kubeadm init --pod-network-cidr=10.244.0.0/16 >> cluster_initialized.txt
      args:
        chdir: $HOME
        creates: cluster_initialized.txt

    - name: create .kube directory
      become: yes
      become_user: ubuntu
      file:
        path: $HOME/.kube
        state: directory
        mode: 0755

    - name: copy admin.conf to user's kube config
      copy:
        src: /etc/kubernetes/admin.conf
        dest: /home/ubuntu/.kube/config
        remote_src: yes
        owner: ubuntu

    - name: install Pod network
      become: yes
      become_user: ubuntu
      shell: kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/a70459be0084506e4ec919aa1c114638878db11b/Documentation/kube-flannel.yml >> pod_network_setup.txt
      args:
        chdir: $HOME
        creates: pod_network_setup.txt
$ ansible-playbook -i hosts ~/kube-cluster/master.yml
```


On master get join command, run command on all workers when node not already joined.
 
```sh
$ vi ~/kube-cluster/workers.yml
- hosts: master
  become: yes
  gather_facts: false
  tasks:
    - name: get join command
      shell: kubeadm token create --print-join-command
      register: join_command_raw

    - name: set join command
      set_fact:
        join_command: "{{ join_command_raw.stdout_lines[0] }}"


- hosts: workers
  become: yes
  tasks:
    - name: join cluster
      shell: "{{ hostvars['master'].join_command }} >> node_joined.txt"
      args:
        chdir: $HOME
        creates: node_joined.txt
$ ansible-playbook -i hosts ~/kube-cluster/workers.yml
```

Test the setup,
```sh
$ ssh ubuntu@master_ip
>$ kubectl get nodes
```

```sh
# Create a deployment named "nginx" 
$ kubectl create deployment nginx --image=nginx
# Run the service, 
$ kubectl expose deploy nginx --port 80 --target-port 80 --type NodePort
$ kubectl get services

# Removal
$ kubectl delete service nginx
$ kubectl delete deployment nginx
```
