# -*- mode: ruby -*-
# vi: set ft=ruby :

# Based on https://github.com/tjcsl/ion/blob/4bc6fa6de88f9b0f4595093aaa25b894da5b50f1/Vagrantfile

Vagrant.require_version ">= 2.1.0"

Vagrant.configure("2") do |config|
  local_base_box = File.expand_path("vagrant-config/output-director4-base/package.box", __dir__)
  configured_box = ENV["DIRECTOR4_VAGRANT_BOX"]

  if configured_box
    config.vm.box = configured_box
    config.vm.box_url = ENV["DIRECTOR4_VAGRANT_BOX_URL"] if ENV["DIRECTOR4_VAGRANT_BOX_URL"]
    config.vm.box_version = ENV["DIRECTOR4_VAGRANT_BOX_VERSION"] if ENV["DIRECTOR4_VAGRANT_BOX_VERSION"]
  elsif File.file?(local_base_box)
    # A locally refreshed base box avoids repeating the OS upgrade and system
    # dependency installation every time the VM is recreated.
    config.vm.box = "director4/ubuntu-24.04-local"
    normalized_box_path = local_base_box.tr("\\", "/")
    config.vm.box_url = Gem.win_platform? ? "file:///#{normalized_box_path}" : "file://#{normalized_box_path}"
  else
    config.vm.box = "bento/ubuntu-24.04"
  end

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

    # You can change these settings by setting the environment variables DIRECTOR4_VAGRANT_CPUS and DIRECTOR4_VAGRANT_MEMORY when running vagrant up. For example, to give the VM 4 CPUs and 8GB of RAM, run:
    # DIRECTOR4_VAGRANT_CPUS=4 DIRECTOR4_VAGRANT_MEMORY=8192 vagrant up
    vb.cpus = Integer(ENV.fetch("DIRECTOR4_VAGRANT_CPUS", 4))
    vb.memory = Integer(ENV.fetch("DIRECTOR4_VAGRANT_MEMORY", 4096))
  end

  # Sync this repo to /home/vagrant/director
  config.vm.synced_folder ".", "/home/vagrant/director", SharedFoldersEnableSymlinksCreate: false

  # Install the stable system layer first. Refreshed Director base boxes carry
  # the matching content marker, so this returns immediately for those boxes.
  config.vm.provision "shell", path: "vagrant-config/base-provision.sh"

  # Configure project-specific services and application state.
  config.vm.provision "shell", path: "vagrant-config/provision.sh"

  # Set SSH username
  config.ssh.username = "vagrant"
end
