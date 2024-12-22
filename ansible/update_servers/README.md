# Update systems of the backend servers

## Install ansible on Linux Ubuntu

```sh
sudo apt-get update
sudo apt-get install ansible -y
```

## Update all packages of Ubuntu servers

```sh
ansible-playbook update_ubuntu.yml
```
