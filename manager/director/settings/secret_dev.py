# This file is in Git. For local customizations, edit secret.py instead.
import getpass
import socket

DEBUG = True

if getpass.getuser() == "vagrant" and socket.gethostname() == "directorvm":
    # In the VM
    RABBITMQ_HOST = "localhost"
    RABBITMQ_PORT = 5672
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = "6379"
else:
    # On the host
    RABBITMQ_HOST = "localhost"
    RABBITMQ_PORT = 5673
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = "6380"

CELERY_BROKER_URL = "amqp://guest:guest@{}:{}/manager".format(RABBITMQ_HOST, RABBITMQ_PORT)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        }
    }
}
