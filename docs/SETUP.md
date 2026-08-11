# Vagrant setup

1. Install [VirtualBox](https://www.virtualbox.org/wiki/Downloads) and [Vagrant](http://docs.vagrantup.com/v2/installation/index.html). If you are running Windows, install [Git](https://gitforwindows.org/) and run `git config core.autocrlf input` to prevent line ending issues.
2. Clone the Director 4.0 repository onto your computer and `cd` into the new directory. If you have an SSH key, run `git clone git@github.com:tjcsl/director4.git director && cd director`. Otherwise, run `git clone https://github.com/tjcsl/director4.git director && cd director`.
3. Run `vagrant up` and then `vagrant reload`. This will download a Vagrant image and provision the resulting VM.
4. Run `vagrant ssh` to login to the VM. Once inside, run `cd director`.
5. You can now work on Director. `scripts/start-servers.sh` will open a `tmux` session with the four servers each running in a separate pane.
   - Note: If you are not familiar with `tmux`, we recommend https://www.hamvocke.com/blog/a-quick-and-easy-guide-to-tmux/ and https://tmuxcheatsheet.com/ as starting resources.
   - See [this](docs/tmux.md) for an explaination of the components of the development `tmux`
6. When you are finished, type `exit` to exit the VM and `vagrant halt` to stop it. When you want to work on Director 4.0 again, `cd` into this directory, run `vagrant up` and `vagrant ssh` to launch the VM and connect to it, and then run `exit` and `vagrant halt` to exit and shut it down.

# Helpful tips

- You can change the amount of cores and RAM you give the vm at runtime (preferred) or in the vagrantfile.
   - The vm has a default of 4 logical cpus and 4 GiB of RAM.
   - For example, to give the VM 8 CPUs and 8GB of RAM, run `DIRECTOR4_VAGRANT_CPUS=8 DIRECTOR4_VAGRANT_MEMORY=8192 vagrant up`
- If `vagrant up` or `vagrant reload` fails, try running `vagrant halt` and `vagrant destroy -f` before recreating it.