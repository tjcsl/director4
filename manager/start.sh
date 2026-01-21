#!/bin/bash
cp -r /etc/director-shell-keys/* /manager/director-shell-keys/

if [ $CELERY ]; then
    exec celery -A director worker --pool solo
else
    python3 manage.py migrate
    python3 manage.py shell < scripts/update-db.py
    exec python3 manage.py runserver 0.0.0.0:8080
fi
