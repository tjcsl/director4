# Vagrant setup

1. Install [VirtualBox](https://www.virtualbox.org/wiki/Downloads) and [Vagrant](http://docs.vagrantup.com/v2/installation/index.html). If you are running Windows, install [Git](https://gitforwindows.org/) and run `git config core.autocrlf input` to prevent line ending issues.
2. Clone the Director 4.0 repository onto your computer and `cd` into the new directory. If you have an SSH key, run `git clone git@github.com:tjcsl/director4.git director && cd director`. Otherwise, run `git clone https://github.com/tjcsl/director4.git director && cd director`.
3. If you regularly recreate the VM, install [Packer](https://developer.hashicorp.com/packer/install) and build a refreshed local base box. The generated box contains current OS updates and stable system dependencies, and the Vagrantfile selects it automatically:
   ```shell
   packer init vagrant-config/packer
   packer build -force vagrant-config/packer
   ```
   Rebuild this box periodically and whenever `vagrant-config/base-provision.sh` changes. For a single VM creation, this step is optional; `vagrant up` performs the same system setup directly from Bento.
4. Run `vagrant up` and then `vagrant reload`. This will download or select a Vagrant image and provision the resulting VM.
5. Run `vagrant ssh` to login to the VM. Once inside, run `cd director`.
6. You can now work on Director. `scripts/start-servers.sh` will open a `tmux` session with the four servers each running in a separate pane.
   - Note: If you are not familiar with `tmux`, we recommend https://www.hamvocke.com/blog/a-quick-and-easy-guide-to-tmux/ and https://tmuxcheatsheet.com/ as starting resources.
   - See [this](docs/tmux.md) for an explaination of the components of the development `tmux`
7. When you are finished, type `exit` to exit the VM and `vagrant halt` to stop it. When you want to work on Director 4.0 again, `cd` into this directory, run `vagrant up` and `vagrant ssh` to launch the VM and connect to it, and then run `exit` and `vagrant halt` to exit and shut it down.

# Helpful tips

- You can change the amount of cores and RAM you give the vm at runtime (preferred) or in the vagrantfile.
   - The vm has a default of 4 logical cpus and 4 GiB of RAM.
   - For example, to give the VM 8 CPUs and 8GB of RAM, run `DIRECTOR4_VAGRANT_CPUS=8 DIRECTOR4_VAGRANT_MEMORY=8192 vagrant up`
- Python environments are installed concurrently and cached by their `Pipfile` and `Pipfile.lock` contents. Set `DIRECTOR4_DEPENDENCY_JOBS` to a positive integer to limit concurrency.
- A shared refreshed box can be selected with `DIRECTOR4_VAGRANT_BOX`. `DIRECTOR4_VAGRANT_BOX_URL` and `DIRECTOR4_VAGRANT_BOX_VERSION` optionally identify its download URL and version. These override the automatically detected local box and the Bento fallback.
- Re-running `vagrant provision` keeps unchanged Docker services and Python environments rather than recreating them. Configuration or lockfile changes invalidate only the affected cached work.
- If `vagrant up` or `vagrant reload` fails, try running `vagrant halt` and `vagrant destroy -f` before recreating it.
