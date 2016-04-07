#!/usr/bin/python
# Adds coordinates to modified objects in the database
import sys, os, urllib2, re, gzip
import peewee, json
from lxml import etree
from StringIO import StringIO
from datetime import datetime

path = os.path.dirname(sys.argv[0]) if len(sys.argv) < 2 else sys.argv[1]
database = peewee.SqliteDatabase(os.path.join(path, 'mapsme-changes.db'))
API_ENDPOINT = 'https://api.openstreetmap.org/api/0.6'

class Change(peewee.Model):
  """A model for the change. Just a single table."""
  changeset = peewee.IntegerField()
  user = peewee.CharField(max_length=250, index=True)
  version = peewee.CharField(max_length=250)
  timestamp = peewee.DateTimeField(index=True)
  action = peewee.FixedCharField(max_length=1) # c=created, d=deleted, m=modified, a=anomaly, n=note
  obj_type = peewee.FixedCharField(max_length=1, null=True)
  obj_id = peewee.IntegerField(null=True)
  main_tag = peewee.CharField(max_length=100, null=True)
  address = peewee.BooleanField(default=False)
  changes = peewee.TextField()

  class Meta:
    database = database
    db_table = 'mapsme_change'

def find_coord(obj_type, obj_id):
  if obj_type not in ('n', 'w'):
    return None
  typs = { 'n': 'node', 'w': 'way' }
  try:
    response = urllib2.urlopen('{0}/{1}/{2}'.format(API_ENDPOINT, typs[obj_type], obj_id))
  except urllib2.HTTPError as e:
    if e.code == 404:
      return None
    raise e
  obj = etree.parse(response).getroot()[0]
  if obj.tag == 'node':
    return (obj.get('lon'), obj.get('lat'))
  else:
    # Get coordinate of the first node
    nd = obj.find('nd')
    return find_coord('n', nd.get('ref'))

if __name__ == '__main__':
  database.connect()
  q = Change.select().where(Change.changes.contains('[null,') & Change.action == 'm')
  for row in q:
    changes = json.loads(row.changes)
    if not changes[0]:
      changes[0] = find_coord(row.obj_type, row_obj_id)
      row.save()
