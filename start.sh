#!/usr/bin/env bash

# O Gunicorn é o servidor de produção que o Render exige.
# O Render injeta a porta correta na variável $PORT.
gunicorn --workers 4 --threads 2 --timeout 60 app:app