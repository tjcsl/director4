# This file is in Git. For local customizations, edit secret.py instead.

DEBUG = True

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
REDIS_HOST = "127.0.0.1"
REDIS_PORT = "6379"

CELERY_BROKER_URL = "amqp://guest:guest@{}:{}/manager".format(RABBITMQ_HOST, RABBITMQ_PORT)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [(REDIS_HOST, REDIS_PORT)]},
    }
}
