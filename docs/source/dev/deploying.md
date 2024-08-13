# Deployment

```{important}
Running Director 4.0 is only supported on Linux-based systems.
You may be able to get it working on other operating systems, but this is
not supported and we may make changes breaking compatibility without warning.
```

Each section here corresponds to a component of Director 4.0.

## Manager

### Dependencies

The manager uses Redis as the channel layer for Channels, RabbitMQ as the broker for Celery,
and Nginx to serve static files.

#### Redis

Install [Redis](https://redis.io/). The default configuration should be sufficient.

#### RabbitMQ

[RabbitMQ](https://www.rabbitmq.com/) will also work out of the box. However, for security you should
configure it to only listen on `localhost`. This can be done by editing RabbitMQ's
configuration file (usually located at `/etc/rabbitmq/rabbitmq.config`) to the following:
`[{rabbit, [{tcp_listeners, [{"127.0.0.1", 5672}]}]}].`

#### Nginx

For [Nginx](https://nginx.org). this configuration *should* work, though it has not been tested
(the current production environment uses a more complex configuration). It should be placed in
`/etc/nginx/sites-available/director.conf`, and a symbolic link should be created at
`/etc/nginx/sites-enabled/director.conf` pointing to this file.

```nginx
server {
        listen       80 default_server;
        listen       [::]:80 default_server;
        server_name  <SERVER NAME>;
	# Optional; see the notes in manager/README.md
	#location /static/vendor {
        #    alias /usr/local/www/director/manager/director/serve/vendor;
        #    expires 7d;
        #}
	location /static {
            alias /usr/local/www/director/manager/director/serve;
            expires 1d;
        }
	location / {
            proxy_pass           http://127.0.0.1:9000;
            proxy_redirect       off;
            proxy_set_header     Host             $host;
            proxy_set_header     X-Real-IP        $remote_addr;
            proxy_set_header     X-Forwarded-For  $remote_addr;
            proxy_set_header     X-Forwarded-Host $host;
            proxy_set_header     X-Forwarded-Proto https;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_http_version 1.1;
        }

        error_page 403 /error/static/403.html;
        error_page 404 /error/static/404.html;
        error_page 502 /error/static/502.html;
        error_page 503 /error/static/unavailable.html;
}
```

Note that this will listen on port 80 (HTTP), so traffic will be sent unencrypted. If you wish to encrypt traffic using HTTPS,
that will require additional setup beyond the scope of this document.

#### Celery and Daphne

First, you will need to create a new user, clone this GitHub repository somewhere as that user, and run `pipenv install`.
You will also need to give the `www-data` user access to the repository so it can serve static files.

If you have root access to the server with `git`, `pipenv`, and `sudo` installed, all of this can be done with the
following (currently untested):

```bash
groupadd director
useradd -g director director
usermod -a -G director www-data
mkdir /var/www/director
cd /var/www/director
chown director:director /var/www/director
chmod 750 /var/www/director
sudo -u director git clone 'https://github.com/tjresearch/research-theo_john.git'
sudo -u director pipenv install
```

After this, you will need to restart Nginx.

Now you can start Celery with `pipenv run celery worker -A director --pool solo`, and Daphne with
`pipenv run daphne -b 127.0.0.1 -p 9000 director.asgi:application`. Both should be run as the user you created in the previous step
(if you ran the commands immediately above, this is the `director` user). You may wish to launch them using
[supervisor](http://supervisord.org/) or your distribution's init system.

Note that you can run multiple Daphne workers. See [Nginx HTTP Load Balancing](https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/) for more information on how to set up Nginx to handle this.
