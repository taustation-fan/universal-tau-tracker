#/bin/bash
source venv/bin/activate
mkdir -p log
export PYTHONUNBUFFERED=1
gunicorn --bind '127.0.0.1:8812' utt:app | tee -a  log/utt-$(date --iso).log
