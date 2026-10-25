#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
if [ ! -f .venv/bibliotecapi-deps ] || ! cmp -s bibliotecapi/requirements.txt .venv/bibliotecapi-deps; then
    .venv/bin/python -m pip install -r bibliotecapi/requirements.txt
    cp bibliotecapi/requirements.txt .venv/bibliotecapi-deps
fi
.venv/bin/python bibliotecapi/manage.py migrate --noinput
.venv/bin/python bibliotecapi/manage.py preparar_biblioteca --se-vazio
printf '\nAbra http://127.0.0.1:8000 no navegador. Para encerrar, pressione Ctrl+C.\n\n'
.venv/bin/python bibliotecapi/manage.py runserver 127.0.0.1:8000 --noreload
