#!/bin/sh
cd /http/
. /http/venv/bin/activate
export PYTHONPATH=$PYTHONPATH:/http/
cd /http/ausentesCCBv1/
/http/venv/bin/gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8004 &
echo "O servidor controleMusicalv1 está em execução."
