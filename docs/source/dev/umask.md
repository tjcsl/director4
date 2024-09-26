# Umask settings

```{warning}

ALL OF THE INFORMATION ON THIS PAGE IS OUT OF DATE

Director 4.0 now does something completely different for PHP sites. Changing the umask to something like `022`, `027`, or `077` would not be a big deal anymore.

This page is nevertheless preserved for legacy reasons, in case you want to understand the reasoning behind Director 4.0's special handling of umasks.


```

**TL;DR**: Director sets umasks to `007` by default to fix weird permission issues.

*First, if you are not familiar with umasks, read up on them (one source is [here](https://www.cyberciti.biz/tips/understanding-linux-unix-umask-value-usage.html)). Basically, it specifies permissions to remove when creating files/directories, so a umask of `022` results in files being created with mode `644` and directories with mode `755`.*

PHP sites on Director 4.0 have issues. Basically, we run them with the `apache` variant of the `php` image, which has PHP support set up by default. However, Apache requires that it not run as `root` for security reasons.

Normally, running as `root` is bad, but in our context it's not an issue. The site is running as `root` inside the container, but that maps to an unprivileged user outside the container. In addition, `/` on the container is read-only. There isn't much harm you can do as `root`.

Unfortunately, Apache's check is hardcoded, so we can't disable it without changing a compile-time parameter. Trying to do that would require us to build our own custom Docker image, which would just be a mess.

What we can do is make Apache run with *group* `root` -- it doesn't complain about that. However, this creates permissions issues with the default `022` umask -- the owning group does not have write permissions. As a result, any writes attempted by PHP programs will fail.

So we set the umask to `007` everywhere (in the site process, in the terminal, in the files helper, and when creating the site directory). This giving the owning group write access to all files created (and removes access by other users for good measure). As a result, as long as Apache/PHP runs with group `root`, everything will be fine.
