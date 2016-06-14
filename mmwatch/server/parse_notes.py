#!/usr/bin/env python
import urllib2
import json
from tempfile import TemporaryFile
from bz2file import BZ2File
from db import database, Change
from lxml import etree
from datetime import datetime


def hour_difference(start, timestamp):
    last_ts = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
    diff = last_ts - start
    return diff.seconds / 3600 + diff.days * 24


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
                    if len(element) > 0 and element[0].text and '#mapsme' in element[0].text:
                        note_id = element.get('id')
                        try:
                            ch = Change.get(Change.changeset == note_id, Change.action == 'n')
                            if element[-1].get('action') == 'closed' and ch.processed is None:
                                print('Found closed note {0}'.format(note_id))
                                ch.processed = hour_difference(ch.timestamp, element[-1].get('timestamp'))
                                ch.save()
                        except Change.DoesNotExist:
                            ch = Change()
                            ch.action = 'n'
                            ch.version = ''
                            ch.changeset = note_id
                            ch.user = element[0].get('user') if element[0].get('uid') else 'Anonymous Note'
                            print('Found new note {0} by {1}'.format(note_id, ch.user.encode('utf-8')))
                            ch.timestamp = datetime.strptime(element[0].get('timestamp'), '%Y-%m-%dT%H:%M:%SZ')
                            if element[-1].get('action') == 'closed' and ch.processed is None:
                                ch.processed = hour_difference(ch.timestamp, element[-1].get('timestamp'))
                            changes = [(element.get('lon'), element.get('lat')), {'note': element[0].text}]
                            ch.changes = json.dumps(changes, ensure_ascii=False)
                            ch.save()
                    element.clear()


if __name__ == '__main__':
    process_notes()
