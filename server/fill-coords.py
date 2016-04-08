#!/usr/bin/env python
# Adds coordinates to modified objects in the database
import sys, urllib2, json
from db import *
from lxml import etree

API_ENDPOINT = 'https://api.openstreetmap.org/api/0.6'

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
  q = Change.select().where(Change.changes.startswith('[null,') & (Change.action == 'm')).limit(10)
  for row in q:
    changes = json.loads(row.changes)
    if not changes[0]:
      coord = find_coord(row.obj_type, row.obj_id)
      changes[0] = (coord, coord)
      row.changes = changes
      row.save()
