packer {
  required_version = ">= 1.10.0"

  required_plugins {
    vagrant = {
      source  = "github.com/hashicorp/vagrant"
      version = "~> 1.1"
    }
  }
}

variable "source_box" {
  type        = string
  default     = "bento/ubuntu-24.04"
  description = "Vagrant Cloud box used to build the refreshed Director base."
}

variable "source_box_version" {
  type        = string
  default     = "202510.26.0"
  description = "Pinned source box version for reproducible base builds."
}

source "vagrant" "director4_base" {
  communicator   = "ssh"
  source_path    = var.source_box
  box_version    = var.source_box_version
  provider       = "virtualbox"
  add_force      = true
  teardown_method = "destroy"
  output_dir     = "${path.root}/../output-director4-base"
}

build {
  name    = "director4-base"
  sources = ["source.vagrant.director4_base"]

  provisioner "shell" {
    script           = "${path.root}/../base-provision.sh"
    environment_vars = ["DIRECTOR4_BASE_BOX_BUILD=1"]
    execute_command  = "chmod +x {{ .Path }}; sudo -E {{ .Vars }} {{ .Path }}"
  }
}
