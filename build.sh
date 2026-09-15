#!/usr/bin/env bash
# Comando de build para Render. Se corre una vez en cada deploy, antes de
# levantar el server.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
