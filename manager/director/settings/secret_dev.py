# This file is in Git. For local customizations, edit secret.py instead.

DEBUG = True

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
REDIS_HOST = "127.0.0.1"
REDIS_PORT = "6379"

CHANNELS_REDIS_DB = 0
CHANNELS_REDIS_PREFIX = "manager-channels:"

CELERY_BROKER_URL = "amqp://guest:guest@{}:{}/manager".format(RABBITMQ_HOST, RABBITMQ_PORT)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["redis://{}:{}/{}".format(REDIS_HOST, REDIS_PORT, CHANNELS_REDIS_DB)],
            "prefix": CHANNELS_REDIS_PREFIX,
        },
    }
}

DIRECTOR_APPSERVER_HOSTS = ["localhost:5000"]

SITE_URL_FORMATS = {
    None: "http://127.0.0.1:8081/{}/",
}
