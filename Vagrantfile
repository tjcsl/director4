# -*- mode: ruby -*-
# vi: set ft=ruby :

# Based on https://github.com/tjcsl/ion/blob/4bc6fa6de88f9b0f4595093aaa25b894da5b50f1/Vagrantfile

Vagrant.require_version ">= 2.1.0"

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/bionic64"

  config.vm.boot_timeout = 1000

  # Manager HTTP port (can also run on the host)
  config.vm.network "forwarded_port", guest: 8080, host: 8080, host_ip: "127.0.0.1"
  # Redis/RabbitMQ ports for manager to run on the host
  config.vm.network "forwarded_port", guest: 6379, host: 6380, host_ip: "127.0.0.1"
  config.vm.network "forwarded_port", guest: 5672, host: 5673, host_ip: "127.0.0.1"
  # Balancer HTTP port (currently not set up)
  config.vm.network "forwarded_port", guest: 80, host: 8001, host_ip: "127.0.0.1"

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
  config.vm.synced_folder ".", "/home/vagrant/director"

  # Provision from a script
  config.vm.provision "shell", path: "vagrant-config/provision.sh"

  # Set SSH username
  config.ssh.username = "vagrant"
end
