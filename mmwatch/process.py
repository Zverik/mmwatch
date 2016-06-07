#!/usr/bin/env python
from server import mapsme_process
from server import parse_notes
print 'Processing changes'
mapsme_process.process()
print 'Processing notes'
parse_notes.process_notes()
