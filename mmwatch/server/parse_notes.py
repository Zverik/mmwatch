#!/usr/bin/env python
import bz2, urllib2, json
from tempfile import TemporaryFile
from bz2file import BZ2File
from db import *
from lxml import etree
from datetime import datetime


def process_notes():
    response = urllib2.urlopen('http://planet.openstreetmap.org/notes/planet-notes-latest.osn.bz2')
    # Parsing bz2 through a temporary file
    tmpfile = TemporaryFile()
    while True:
        chunk = response.read(512*1024)
        if not chunk:
            break
        tmpfile.write(chunk)
    tmpfile.seek(0)

    database.connect()
    with database.atomic():
        with BZ2File(tmpfile) as f:
            for event, element in etree.iterparse(f):
                if element.tag == 'note':
                    if len(element) > 0 and '#mapsme' in element[0].text:
                        note_id = element.get('id')
                        try:
                            ch = Change.get(Change.changeset == note_id, Change.action == 'n')
                            if element[-1].get('action') == 'closed':
                                # TODO: mark as closed
                                last_ts = element[-1].get('timestamp')
                        except Change.DoesNotExist:
                            print 'Found new note', note_id, 'by', element[0].get('user')
                            # No such note, add it
                            ch = Change()
                            ch.changeset = note_id
                            ch.user = element[0].get('user') if element[0].get('uid') else 'Anonymous'
                            ch.version = ''
                            ch.timestamp = element[0].get('timestamp')
                            ch.action = 'n'
                            changes = [(element.get('lon'), element.get('lat')), {'name': element[0].text}]
                            ch.changes = json.dumps(changes)
                            ch.save()
                    element.clear()


if __name__ == '__main__':
    process_notes()
