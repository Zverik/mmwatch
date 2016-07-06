from www import app
from flask import session, url_for, redirect, request
from flask_oauthlib.client import OAuth, get_etree
from db import Change
from peewee import fn
import json

API_ENDPOINT = 'https://api.openstreetmap.org/api/0.6/'

oauth = OAuth()
openstreetmap = oauth.remote_app('OpenStreetMap',
                                 base_url=API_ENDPOINT,
                                 request_token_url='https://www.openstreetmap.org/oauth/request_token',
                                 access_token_url='https://www.openstreetmap.org/oauth/access_token',
                                 authorize_url='https://www.openstreetmap.org/oauth/authorize',
                                 consumer_key=app.config['OAUTH_KEY'],
                                 consumer_secret=app.config['OAUTH_SECRET']
                                 )


@app.route('/revert')
def revert():
    if 'osm_token' not in session:
        return openstreetmap.authorize(callback=url_for('oauth'))

    objects = request.args.get('objects').split(',')
    q = Change.select(fn.Distinct(Change.user)).where(Change.id << objects).tuples()
    names = [ch[0].encode('utf-8') for ch in q]

    return '''
You are to revert {count} edit{s} by {names}.<br>
<a href="javascript:window.close();">Close this window</a> if you pressed the button by mistake.<br><br>
<form action="{action}" method="get">
<input type="hidden" name="objects" value="{objects}">
<input type="submit" value="Continue with the revert">
</form>'''.format(
        count=len(objects), objects=','.join(objects), s=('' if len(objects) == 1 else 's'),
        names=', '.join(names), action=url_for('actual_revert'))


@app.route('/oauth')
@openstreetmap.authorized_handler
def oauth(resp):
    if resp is None:
        return 'Denied. <a href="' + url_for('revert') + '">Try again</a>.'
    session['osm_token'] = (
            resp['oauth_token'],
            resp['oauth_token_secret']
    )
    return redirect(url_for('revert'))


@openstreetmap.tokengetter
def get_token(token='user'):
    if token == 'user' and 'osm_token' in session:
        return session['osm_token']
    return None


@app.route('/logout')
def logout():
    if 'osm_token' in session:
        del session['osm_token']
    return redirect(url_for('the_one_and_only_page'))


@app.route('/dorevert')
def actual_revert():
    if 'osm_token' not in session:
        return 'Not authenticated'

    objects = [int(x) for x in request.args.get('objects').split(',')]
    q = Change.select().where(Change.id << objects)
    changes = [ch for ch in q]

    # Build a list of objects and request latest versions
    nwr_list = {'n': [], 'w': [], 'r': []}
    ch_list = {}
    notes = []
    for ch in changes:
        if ch.action in ('c', 'm') and ch.obj_type in ('n', 'w', 'r'):
            nwr_list[ch.obj_type].append(ch.obj_id)
            if ch.action == 'm':
                ch_list['{0}{1}'.format(ch.obj_type, ch.obj_id)] = json.loads(ch.changes)
        elif ch.action == 'n':
            notes.append(ch.changeset)

    # Make three requests for all objects from lists
    # For each object, revert unchanged tags and coords, prepare osc
    etree = get_etree()
    osc = etree.Element('osmChange', {'version': '0.6'})
    for typ in ('node', 'way', 'relation'):
        if len(nwr_list[typ[0]]) == 0:
            continue
        resp = openstreetmap.get('{0}s?{0}s={1}'.format(typ, ','.join((str(x) for x in nwr_list[typ[0]]))))
        if resp.status != 200:
            return 'Failed to get {0}s: {1} {2}'.format(typ, resp.status, resp.data)
        for obj in resp.data:
            if obj.get('visible') == 'false':
                # Not undeleting objects
                continue
            v = int(obj.get('version'))
            ref = '{0}{1}'.format(typ[0], obj.get('id'))
            if v == 1 and ref not in ch_list:
                # First version that was created, deleting it
                d = etree.SubElement(osc, 'delete')
                etree.SubElement(d, obj.tag, {
                    'id': obj.get('id'),
                    'version': obj.get('version')
                })
            elif v > 1 and ref in ch_list:
                # Reverting tag and coord changes
                m = etree.SubElement(osc, 'modify')
                rev = revert_change(obj, ch_list[ref])
                if rev is not None:
                    m.append(rev)

    if len(osc) == 0:
        return 'These changes have already been reverted.'

    # Create a changeset
    q = Change.select(fn.Distinct(Change.user)).where(Change.id << objects).tuples()
    names = [ch[0].encode('utf-8') for ch in q]
    comment = 'Reverting MAPS.ME changes by {0}'.format(', '.join(names))

    create_xml = etree.Element('osm')
    ch = etree.SubElement(create_xml, 'changeset')
    etree.SubElement(ch, 'tag', {'k': 'created_by', 'v': 'MMWatch Reverter'})
    etree.SubElement(ch, 'tag', {'k': 'comment', 'v': comment.decode('utf-8')})
    changeset_xml = etree.tostring(create_xml)
    resp = openstreetmap.put('changeset/create', changeset_xml, format=None)
    if resp.status != 200:
        return 'Failed to open a changeset: {0} {1}'.format(resp.status, resp.data)
    changeset_id = int(resp.raw_data)

    # Upload changes
    fill_changeset(osc, changeset_id)
    print etree.tostring(osc)
    try:
        resp = openstreetmap.post('/changeset/{0}/upload'.format(changeset_id), data=etree.tostring(osc), format=None)
        if resp.status != 200:
            return 'Failed to upload changes: {0} {1}'.format(resp.status, resp.data)
    finally:
        # Close the changeset
        openstreetmap.put('changeset/{0}/close'.format(changeset_id))

    return redirect('https://www.openstreetmap.org/changeset/{0}'.format(changeset_id))


def revert_change(obj, change):
    """Receives XML node of an element and a list of changes.
    Returns either an XML for OSC, or None."""
    etree = get_etree()
    elem = etree.Element(obj.tag)
    for k in ('id', 'version', 'lat', 'lon'):
        if k in obj.keys():
            elem.set(k, obj.get(k))
    # TODO
    print 'Reverting', obj.tag, obj.get('id')
    return elem


def fill_changeset(osc, changeset_id):
    for act in osc:
        for elem in act:
            elem.set('changeset', changeset_id)
