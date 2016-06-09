#!/usr/bin/env python
import os, sys
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)
PYTHON = 'python2.7'
VENV_DIR = os.path.join(BASE_DIR, 'venv', 'lib', PYTHON, 'site-packages')
if os.path.exists(VENV_DIR):
    sys.path.insert(1, VENV_DIR)

from server import mapsme_process
mapsme_process.process()
