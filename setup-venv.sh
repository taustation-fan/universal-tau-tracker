#!/bin/bash
set -e
virtualenv -p python3 venv
source venv/bin/activate
_prefix=$(echo venv/lib/python3.*)
pwd > $_prefix/site-packages/utt.pth
pip install -r requirements.txt
pip install ipython

echo ""
echo "Your development environment is ready to roll!"
echo "To use it, run 'source venv/bin/activate' in your shell."
