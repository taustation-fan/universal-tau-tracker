#/bin/bash
CTT_DB=/home/ctt/data/ctt.sqlite3  gunicorn --bind '127.0.0.1:8812' ctt:app
