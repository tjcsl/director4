# Vagrant setup

1. Install [VirtualBox](https://www.virtualbox.org/wiki/Downloads) and [Vagrant](http://docs.vagrantup.com/v2/installation/index.html). If you are running Windows, install [Git](https://gitforwindows.org/) and run `git config core.autocrlf input` to prevent line ending issues.
2. Clone the Director 4.0 repository onto your computer and `cd` into the new directory. If you have an SSH key, run `git clone git@github.com:tjresearch/research-theo_john.git director && cd director`. Otherwise, run `git clone https://github.com/tjresearch/research-theo_john.git director && cd director`.
3. Run `vagrant plugin install vagrant-vbguest`.
4. Run `vagrant up && vagrant reload`. This will download a Vagrant image and provision the resulting VM.
5. Run `vagrant ssh` to login to the VM. Once inside, run `cd director` to change into the repo and `./scripts/install_dependencies.sh` to install Director's Python dependencies using Pipenv.
6. You can now work on Director. `scripts/start-servers.sh` will open a `tmux` session with the four servers each running in a separate pane.
   - Note: If you are not familiar with `tmux`, we recommend https://www.hamvocke.com/blog/a-quick-and-easy-guide-to-tmux/ and https://tmuxcheatsheet.com/ as starting resources.
7. When you are finished, type `exit` to exit the VM and `vagrant halt` to stop it. When you want to work on Director 4.0 again, `cd` into this directory, run `vagrant up` and `vagrant ssh` to launch the VM and connect to it, and then run `exit` and `vagrant halt` to exit and shut it down.
   - Note: You may need to run `vagrant halt -f` instead of `vagrant halt`. This is due to a strange bug that we have been unable to diagnose.
