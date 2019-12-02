# Director 4.0: Troubleshooting

**When I start Docker, I get a "Your kernel does not support swap memory limit" warning messsage.**

By default, the kernel shipped with Ubuntu does not have memory accounting enabled.

This is because:
> Memory and swap accounting incur an overhead of about 1% of the total available memory and a 10% overall performance degradation, even if Docker is not running.
- https://docs.docker.com/install/linux/linux-postinstall/#your-kernel-does-not-support-cgroup-swap-limit-capabilities

1. Open `/etc/default/grub` as `root` on the Director appserver.
2. Add `cgroup_enable=memory swapaccount=1` to the `GRUB_CMDLINE_LINUX` line.
3. Run `update-grub` as `root`
4. Reboot.
5. It's fixed!
