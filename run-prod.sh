#/bin/bash
source venv/bin/activate
gunicorn --bind '127.0.0.1:8812' utt:app
