#!/usr/bin/env python
import urllib2, re, gzip, json
import config
from db import *
from lxml import etree
from StringIO import StringIO
from datetime import datetime, date

REPLICATION_BASE_URL = 'http://planet.openstreetmap.org/replication/changesets'
API_ENDPOINT = 'https://api.openstreetmap.org/api/0.6'
MAIN_TAGS = ('amenity', 'shop', 'tourism', 'historic', 'craft', 'office', 'emergency', 'barrier',
             'highway', 'leisure', 'waterway', 'natural', 'place', 'entrance', 'building')
INTERESTING_TAGS = list(MAIN_TAGS) + ['name']


def log(s):
    print unicode(s).encode('utf8')


def download_last_state():
    """Downloads last changeset replication sequence number from the planet website."""
    state = urllib2.urlopen(REPLICATION_BASE_URL + '/state.yaml').read()
    m = re.search(r'sequence:\s+(\d+)', state)
    # Not checking to throw exception in case of an error
    return int(m.group(1))


def filter_changeset(changeset):
    """A changeset object is a dict of tags plus 'id', 'timestamp' and 'user' fields."""
    if changeset['uid'] in config.BAN_USERS:
        return False
    return 'created_by' in changeset and changeset['created_by'][:7] == 'MAPS.ME' and 'JOSM' not in changeset['created_by']


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
                chdata[element.get('k')] = element.get('v')
        elif event == 'end' and element.tag == 'changeset':
            chdata['id'] = int(element.get('id'))
            # The maximum length of the field is 190 characters due to a MySQL index limitation
            chdata['user'] = element.get('user')[:190]
            chdata['uid'] = int(element.get('uid'))
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
    res['tags'] = {tag.get('k'): tag.get('v') for tag in obj.iterchildren('tag')}
    if obj.tag == 'way':
        res['refs'] = [x.get('ref') for x in obj.iterchildren('nd')]
    elif obj.tag == 'relation':
        res['refs'] = [(x.get('type'), x.get('ref'), x.get('role')) for x in obj.iterchildren('member')]
    return res


def obj_signature(obj):
    return ''.join([obj['type'][0], str(obj['id']), '.', str(obj['version'])])


def was_object_processed(obj1):
    """If the object of given version is already processed, skip it."""
    return Seen.select().where(Seen.obj == obj_signature(obj1)).exists()


def record_object(obj1):
    """If the object of given version is already processed, skip it."""
    seen = Seen()
    seen.obj = obj_signature(obj1)
    seen.save()


def record_user_edit(name):
    """Update user edits count."""
    try:
        user = User.get(User.user == name)
    except User.DoesNotExist:
        user = User()
        user.user = name
        user.edits = 0
        user.joined = date.today()
    user.edits += 1
    user.save()


def create_change(changeset, obj):
    """Creates a Change object, ready to be populated with changes."""
    # Find the main tag
    main = None
    for k in MAIN_TAGS:
        if k in obj['tags']:
            main = u'{0}={1}'.format(k, obj['tags'][k])
            break
    if main is None:
        main = 'unknown'

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


def find_coord(obj_type, obj_id):
    """Queries OSM API to find a coord for an object."""
    try:
        response = urllib2.urlopen('{0}/{1}/{2}'.format(API_ENDPOINT, obj_type, obj_id))
    except urllib2.HTTPError as e:
        if e.code == 410:
            return None
        raise e
    obj = etree.parse(response).getroot()[0]
    if obj.tag == 'node':
        return (obj.get('lon'), obj.get('lat'))
    elif obj.tag == 'way':
        # Get coordinate of the first node
        nd = obj.find('nd')
        if nd is not None:
            return find_coord('node', nd.get('ref'))
    else:
        # This is a relation
        member = obj.find('member')
        if member is not None:
            return find_coord(member.get('type'), member.get('ref'))
    return None


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
        if 'coords' not in obj:
            tmpc = find_coord(obj['type'], obj['id'])
            coords = (tmpc, tmpc)
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
        record_object(obj)
        record_user_edit(changeset['user'])


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
            if not was_object_processed(obj):
                if obj['version'] == 1:
                    prev = None
                else:
                    url = '{0}/{1}/{2}/{3}'.format(API_ENDPOINT, obj['type'], obj['id'], obj['version'] - 1)
                    try:
                        response2 = urllib2.urlopen(url)
                        prev = obj_to_dict(etree.parse(response2).getroot()[0])
                    except urllib2.HTTPError:
                        log(u'Failed do download previous version: {0}'.format(url))
                        prev = None
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


def update_user_ranks():
    """Updates rank fields for users, so they are sorted in the descending order. O(n^2) complexity!"""
    with database.atomic():
        query = User.select().order_by(-User.edits, User.joined)
        rank = count = 1
        last_edits = -1
        for user in query:
            if user.edits != last_edits:
                rank = count
                last_edits = user.edits
            user.rank = rank
            user.save()
            count += 1


def process():
    try:
        cur_state = download_last_state()
    except Exception as e:
        log(u'Failed to download last state: {0}'.format(e))
        return

    database.connect()
    database.create_tables([Change, Seen, User, State], safe=True)

    try:
        state = State.get(id=1)
    except State.DoesNotExist:
        state = State()
        state.state = cur_state - 1

    for i in range(state.state + 1, cur_state + 1):
        log(i)
        try:
            changesets = download_replication(i)
            for c in changesets:
                log(u'- {0}'.format(c))
                record_changeset_diff(c)
        except ValueError as e:
            log(u'Failed to download and process replication {0}: {1}'.format(i, e))
            raise e
        state.state = i
        state.save()
    update_user_ranks()


if __name__ == '__main__':
    process()
