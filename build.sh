#!/usr/bin/env bash
# Comando de build para Render. Se corre una vez en cada deploy, antes de
# levantar el server.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# El disco de Render es efímero (se borra en cada deploy), así que hay que
# volver a cargar las fotos reales de los platos en cada build. Es
# idempotente -- si la foto ya está en el disco, no hace nada.
python manage.py cargar_fotos_articulos
