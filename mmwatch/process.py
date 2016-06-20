#!/usr/bin/env python
import os, sys
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)
PYTHON = 'python2.7'
VENV_DIR = os.path.join(BASE_DIR, 'venv', 'lib', PYTHON, 'site-packages')
if os.path.exists(VENV_DIR):
    sys.path.insert(1, VENV_DIR)

from server import mapsme_process, geocode
mapsme_process.process()
geocode.add_countries()

from db import State
from server import parse_notes
# By this time connection is already established by mapsme_process.
st = State.get(State.id == 1)
if st.run_hourly():
    parse_notes.process_notes()
    # State could have been modified.
    st = State.get(State.id == 1)
    st.update_hourly()
    st.save()
