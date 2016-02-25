#!/usr/bin/python
import sys, os, urllib2, re, gzip
import peewee, json
from lxml import etree
from StringIO import StringIO
from datetime import datetime

path = os.path.dirname(sys.argv[0]) if len(sys.argv) < 2 else sys.argv[1]
database = peewee.SqliteDatabase(os.path.join(path, 'mapsme-changes.db'))
STATE_FILENAME = os.path.join(path, 'mapsme-state.txt')
REPLICATION_BASE_URL = 'http://planet.openstreetmap.org/replication/changesets'
API_ENDPOINT = 'https://api.openstreetmap.org/api/0.6'
MAIN_TAGS = ('amenity', 'shop', 'tourism', 'historic', 'craft', 'emergency', 'barrier', 'highway', 'entrance', 'building')
INTERESTING_TAGS = list(MAIN_TAGS) + ['name']

class Change(peewee.Model):
  """A model for the change. Just a single table."""
  changeset = peewee.IntegerField()
  user = peewee.CharField(max_length=250, index=True)
  version = peewee.CharField(max_length=250)
  timestamp = peewee.DateTimeField(index=True)
  action = peewee.FixedCharField(max_length=1) # c, d, m, a
  obj_type = peewee.FixedCharField(max_length=1, null=True)
  obj_id = peewee.IntegerField(null=True)
  main_tag = peewee.CharField(max_length=100, null=True)
  address = peewee.BooleanField(default=False)
  changes = peewee.TextField()

  class Meta:
    database = database
    db_table = 'mapsme_change'

def download_last_state():
  """Downloads last changeset replication sequence number from the planet website."""
  state = urllib2.urlopen(REPLICATION_BASE_URL + '/state.yaml').read()
  m = re.search(r'sequence:\s+(\d+)', state)
  # Not checking to throw exception in case of an error
  return int(m.group(1))

def read_last_state():
  state = None
  try:
    with open(STATE_FILENAME, 'r') as f:
      m = re.search(r'\d+', f.read())
      state = int(m.group(0))
  except:
    pass
  return state

def write_last_state(state):
  with open(STATE_FILENAME, 'w') as f:
    f.write(str(state))

def filter_changeset(changeset):
  """A changeset object is a dict of tags plus 'id', 'timestamp' and 'user' fields."""
  return 'created_by' in changeset and 'maps.me' in changeset['created_by'].lower()

def download_replication(state):
  """Downloads replication archive for a given state, and returns a list of changeset data to process."""
  changesets = []
  url = '{0}/{1:03}/{2:03}/{3:03}.osm.gz'.format(REPLICATION_BASE_URL, int(state / 1000000), int(state / 1000) % 1000, state % 1000)
  response = urllib2.urlopen(url)
  data = response.read()
  gz = gzip.GzipFile(fileobj=StringIO(data))
  chdata = {}
  for event, element in etree.iterparse(gz, events=('start', 'end')):
    if event == 'start':
      if element.tag == 'changeset':
        chdata = {}
      elif element.tag == 'tag':
        chdata[element.get('k')] = element.get('v').encode('utf-8')
    elif event == 'end' and element.tag == 'changeset':
      chdata['id'] = int(element.get('id'))
      chdata['user'] = element.get('user').encode('utf-8')
      chdata['timestamp'] = element.get('created_at')
      if filter_changeset(chdata):
        changesets.append(chdata)
  return changesets

def obj_to_dict(obj):
  """Converts XML object to an easy to use dict."""
  if obj is None:
    return None
  res = {}
  res['type'] = obj.tag
  res['id'] = int(obj.get('id'))
  res['version'] = int(obj.get('version'))
  res['deleted'] = obj.get('visible') == 'false'
  if obj.tag == 'node' and 'lon' in obj.keys() and 'lat' in obj.keys():
    res['coords'] = (obj.get('lon'), obj.get('lat'))
  res['tags'] = { tag.get('k') : tag.get('v') for tag in obj.iterchildren('tag')}
  if obj.tag == 'way':
    res['refs'] = [x.get('ref') for x in obj.iterchildren('nd')]
  elif obj.tag == 'relation':
    res['refs'] = [(x.get('type'), x.get('ref'), x.get('role')) for x in obj.iterchildren('member')]
  return res

def create_change(changeset, obj):
  """Creates a Change object, ready to be populated with changes."""
  # Find the main tag
  main = None
  for k in MAIN_TAGS:
    if k in obj['tags']:
      main = '{0}={1}'.format(k, obj['tags'][k])
      break
  if main is None:
    return None

  ch = Change()
  ch.changeset = changeset['id']
  ch.user = changeset['user']
  ch.timestamp = datetime.strptime(changeset['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
  ch.version = changeset['created_by']
  ch.obj_type = obj['type'][:1]
  ch.obj_id = obj['id']
  ch.main_tag = main
  return ch

def has_address_tags(tags):
  for k in tags:
    if k[:5] == 'addr:':
      return True
  return False

def record_obj_diff(changeset, obj, prev, anomalies):
  ch = None
  if prev is None or prev['deleted']:
    if not obj['deleted']:
      # Creation
      ch = create_change(changeset, obj)
      if ch is not None:
        ch.action = 'c'
        ch.address = has_address_tags(obj['tags'])
        coords = None if 'coords' not in obj else obj['coords']
        ch.changes = json.dumps((coords, obj['tags']), ensure_ascii=False)
      else:
        anomalies[obj['type'][0] + 'c'] += 1
  elif obj['deleted']:
    # Deletion
    ch = create_change(changeset, prev)
    if ch is not None:
      ch.action = 'd'
      coords = None if 'coords' not in prev else prev['coords']
      ch.changes = json.dumps((coords, prev['tags']), ensure_ascii=False)
    else:
      anomalies[prev['type'][0] + 'd'] += 1
  else:
    # Both objects are present, compare them
    if 'coords' not in obj or obj['coords'] == prev['coords']:
      coords = None
    else:
      coords = (prev['coords'], obj['coords'])
    tags = {}
    for k in prev['tags']:
      new_val = None if k not in obj['tags'] else obj['tags'][k]
      if k in INTERESTING_TAGS or prev['tags'][k] != new_val:
        tags[k] = (prev['tags'][k], new_val)
    for k in obj['tags']:
      if k not in prev['tags']:
        tags[k] = (None, obj['tags'][k])
    ch = create_change(changeset, obj)
    if ch is not None:
      ch.action = 'm'
      ch.address = has_address_tags(tags)
      ch.changes = json.dumps((coords, tags), ensure_ascii=False)
    else:
      anomalies[prev['type'][0] + 'm'] += 1
    if 'refs' in obj and obj['refs'] != prev['refs']:
      anomalies['way_ref' if obj['type'] == 'way' else 'rel_ref'] += 1
  if ch is not None:
    ch.save()

def record_changeset_diff(changeset):
  """Received changeset data dict, downloads individual object changes and store changes to a database."""
  response = urllib2.urlopen('{0}/changeset/{1}/download'.format(API_ENDPOINT, changeset['id']))
  root = etree.parse(response).getroot()
  anomalies = {}
  for k in ('way_ref', 'rel_ref', 'nc', 'wc', 'rc', 'nm', 'wm', 'rm', 'nd', 'wd', 'rd'):
    anomalies[k] = 0
  for action in root:
    for obj_xml in action:
      obj = obj_to_dict(obj_xml)
      if obj['version'] == 1:
        prev = None
      else:
        response2 = urllib2.urlopen('{0}/{1}/{2}/{3}'.format(API_ENDPOINT, obj['type'], obj['id'], obj['version'] - 1))
        prev = obj_to_dict(etree.parse(response2).getroot()[0])
      record_obj_diff(changeset, obj, prev, anomalies)
  if sum(anomalies.itervalues()) > 0:
    ch = Change()
    ch.changeset = changeset['id']
    ch.user = changeset['user']
    ch.timestamp = datetime.strptime(changeset['timestamp'], '%Y-%m-%dT%H:%M:%SZ')
    ch.version = changeset['created_by']
    ch.action = 'a'
    ch.changes = json.dumps(anomalies)
    ch.save()

if __name__ == '__main__':
  try:
    cur_state = download_last_state()
  except Exception as e:
    print 'Failed to download last state:', e
    sys.exit(1)

  state = read_last_state()
  if state is None:
    state = cur_state - 1

  database.connect()
  database.create_tables([Change], safe=True)

  for i in range(state + 1, cur_state + 1):
    print i
    try:
      changesets = download_replication(i)
      for c in changesets:
        print '-', c
        record_changeset_diff(c)
    except Exception as e:
      print 'Failed to download and process replication {0}: {1}'.format(i, e)
      raise e
      break
    write_last_state(i)
