# Ansible

```sh
$ sudo apt-add-repository ppa:ansible/ansible
$ sudo apt-get update
$ sudo apt-get install ansible
# Check each host is accessible from ansible server, without password.
$ ssh root@192.0.2.1
$ ssh root@192.0.2.2
$ ssh root@192.0.2.3
$ sudo vi /etc/ansible/hosts
host1 ansible_ssh_host=192.0.2.1
host2 ansible_ssh_host=192.0.2.2
host3 ansible_ssh_host=192.0.2.3
[servers]
$ sudo mkdir /etc/ansible/group_vars
$ sudo vi /etc/ansible/group_vars/servers
---
ansible_ssh_user: root
# test it
$ ansible -m ping all
host1 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}

host3 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}

host2 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

# Ansible playbooks

A playbook is a YAML file containing a series of procedures that should be automated.

Hosts can be aliased in Ansible/hosts file.
```sh
[webservers]
foo.example.com
bar.example.com
```

Playbooks are written in YAML which is a JSON like structure comprising of lists and dictionaries. YAML documents optionally start and end with the YAML start document, "---". Generally, YAML documents start with a list. A list is lines beginning at the same indentation level starting with a "- ". The abbreviated form is ['item1','item2']. A dictionary entry is, key: value, abbreviated to, {'key': 'value'}. Space indicates nesting, list and dictionary is not to be mixed at the same indentation. ['item1', 'key': 'value'], should be, ['item1', {'key':'value'}].

Here's an example that start with a list containing a dictionary with keys: name; host; and, tasks. Tasks is a list containing a dictionary with keys: name; and, copy. copy is a dictionary with keys: content; and, dest. The multi lines at the same indent after a bar(|) in name:, the indentation is ignored but no the carriage returns. The multi lines at the same indent after a greater than (>), all but the last carriage return is ignored.
```sh
$ vi HelloWorld.yml
---
- name: |
    This is a
    hello-world example
  hosts: localhost
  tasks:
    - name: Create a file called '/tmp/testfile.txt' with the content 'hello world'.
      copy:
        content: hello worldn
        dest: /tmp/testfile.txt
$ ansible-playbook HelloWorld.yml
[WARNING]: provided hosts list is empty, only localhost is available. Note that the implicit
localhost does not match 'all'
PLAY [This is a
hello-world example] *********************************************************
TASK [Gathering Facts] ***********************************************************************
ok: [localhost]
TASK [Create a file called /tmp/testfile.txt with the content hello world.] ******************
changed: [localhost]
PLAY RECAP ***********************************************************************************
localhost                  : ok=2    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0   
$ cat /tmp/testfile.txt
hello world
```
YAML is supported in Python.
```sh
$ vi helloworld.py
import yaml
import pprint
if __name__ == '__main__':
    pprint.pprint(yaml.load(open("HelloWorld.yaml", 'r')))
$ python helloworld.py
[{'desc': 'This is a hello-world example\n',
  'hosts': 'all',
  'name': 'This is a\nhello-world example\n',
  'tasks': [{'copy': {'content': 'hello worldn', 'dest': '/tmp/testfile.txt'},
             'name': 'Create a file called /tmp/testfile.txt with the content '
                     'hello world.'}]}]
```
