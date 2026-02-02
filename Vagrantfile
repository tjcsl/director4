# -*- mode: ruby -*-
# vi: set ft=ruby :

# Based on https://github.com/tjcsl/ion/blob/4bc6fa6de88f9b0f4595093aaa25b894da5b50f1/Vagrantfile

Vagrant.require_version ">= 2.1.0"

Vagrant.configure("2") do |config|
  config.vm.box = "bento/ubuntu-24.04"

  config.vm.boot_timeout = 1000

  # Manager HTTP port
  config.vm.network "forwarded_port", guest: 8080, host: 8080, host_ip: "127.0.0.1"
  # Balancer HTTP port
  config.vm.network "forwarded_port", guest: 80, host: 8081, host_ip: "127.0.0.1"

  # Shell SSH port
  config.vm.network "forwarded_port", guest: 2322, host: 2322, host_ip: "127.0.0.1"

  # Define the VM and set up some things
  config.vm.hostname = "directorvm"
  config.vm.define "director4-vagrant" do |v|
  end
  config.vm.provider "virtualbox" do |vb|
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    vb.customize ["modifyvm", :id, "--natdnsproxy1", "on"]
    vb.customize ["modifyvm", :id, "--nictype1", "virtio"]
    vb.name = "director4-vagrant"
    vb.memory = 2048
  end

  # Sync this repo to /home/vagrant/director
  config.vm.synced_folder ".", "/home/vagrant/director", SharedFoldersEnableSymlinksCreate: false

  # Provision from a script
  config.vm.provision "shell", path: "vagrant-config/provision.sh"

  # Set SSH username
  config.ssh.username = "vagrant"
end
