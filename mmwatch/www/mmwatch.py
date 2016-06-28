import os, json, peewee
from flask import Flask, send_file, request, render_template, url_for, abort, jsonify, Response
from datetime import datetime, timedelta
from StringIO import StringIO
import config
from db import database, Change, User

app = Flask(__name__)
app.debug = config.DEBUG

try:
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass


@app.before_request
def before_request():
    database.connect()


@app.teardown_request
def teardown(exception):
    if not database.is_closed():
        database.close()


@app.route('/user')
def get_user_rating():
    name = request.args.get('name')
    if name is None:
        abort(400)
    fmt = request.args.get('format', 'json')
    try:
        user = User.get(User.user == name)
    except User.DoesNotExist:
        abort(404)
    if fmt == 'xml':
        def quoteattr(s):
            return '"{0}"'.format(str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<mmwatch>\n'
        for field in (('name', user.user.encode('utf-8')), ('rank', user.rank), ('edits', user.edits), ('joined', user.joined.isoformat())):
            xml = xml + '  <{0} value={1} />\n'.format(field[0], quoteattr(field[1]))
        xml = xml + '</mmwatch>'
        return Response(xml, mimetype='application/xml')
    return jsonify(name=user.user, rank=user.rank, edits=user.edits, joined=user.joined.isoformat())


def purl(params, **kwargs):
    p2 = params.copy()
    for k, v in kwargs.iteritems():
        p2[k] = v
    if 'page' in p2 and p2['page'] <= 1:
        del p2['page']
    return url_for('the_one_and_only_page', **p2)


@app.route('/')
def the_one_and_only_page():
    # Parse query params
    params = {}
    page = request.args.get('page', '1')
    params['page'] = int(page) if page.isdigit() else 1
    user = request.args.get('user', None)
    if user is not None:
        params['user'] = user
    platform = request.args.get('platform', None)
    if platform is not None:
        params['platform'] = platform
    version = request.args.get('version', None)
    if version is not None:
        params['version'] = version
    date = request.args.get('date', None)
    if date is not None:
        params['date'] = date
    nolimit = request.args.get('nolimit', None) is not None
    action = request.args.get('action', None)
    if action is not None:
        params['action'] = action
    changeset = request.args.get('changeset', None)
    if changeset is not None and changeset.isdigit():
        params['changeset'] = changeset
    namech = request.args.get('namech', None) is not None
    country = request.args.get('country', None)
    if country is not None:
        params['country'] = country

    # Construct queries
    q = {}
    q['changes'] = Change.select().order_by(Change.id.desc()).paginate(params['page'], config.PAGE_SIZE)
    q['users'] = Change.select(Change.user, peewee.fn.Count(Change.id).alias('count')).group_by(Change.user).order_by(peewee.fn.Count(Change.id).desc())
    q['tags'] = Change.select(Change.main_tag, peewee.fn.Count(Change.id).alias('count')).group_by(Change.main_tag).order_by(peewee.fn.Count(Change.id).desc())
    q['versions'] = Change.select(Change.version, peewee.fn.Count(Change.id).alias('count')).group_by(
        Change.version).order_by(peewee.fn.Count(Change.id).desc())
    q['stat_src'] = Change.select(Change.action, Change.obj_type, peewee.fn.Count(Change.id).alias('count')).group_by(
        Change.action, Change.obj_type).order_by(peewee.fn.Count(Change.id).desc())
    q['dates'] = Change.select(database.truncate_date('day', Change.timestamp).alias('day'), peewee.fn.Min(
        Change.timestamp).alias('timestamp'), peewee.fn.Count(Change.id).alias('count'), peewee.fn.Count(
        peewee.fn.Distinct(Change.user)).alias('users')).group_by(peewee.SQL('day')).order_by(-peewee.SQL('day'))
    q['countries'] = Change.select(Change.country, peewee.fn.Count(Change.id).alias('count')).group_by(
        Change.country).order_by(peewee.fn.Count(Change.id).desc())

    # Apply filters
    for k in q:
        if user:
            q[k] = q[k].where(Change.user == user)
        if version:
            q[k] = q[k].where(Change.version == version)
        if action:
            q[k] = q[k].where(Change.action == action)
        if 'changeset' in params:
            q[k] = q[k].where(Change.changeset == params['changeset'])
        if platform:
            if platform != 'other':
                q[k] = q[k].where(Change.version.startswith('MAPS.ME {0}'.format(platform)))
            else:
                q[k] = q[k].where(~Change.version.startswith('MAPS.ME ios') & ~Change.version.startswith('MAPS.ME android'))
        if k in ('users', 'tags', 'versions', 'dates', 'countries'):
            if not nolimit:
                q[k] = q[k].limit(config.TOP)
            else:
                q[k] = q[k].limit(1000)
        if date:
            pdate = datetime.strptime(date + ' UTC', '%d.%m.%Y %Z')
            pdate1 = pdate + timedelta(days=1)
            q[k] = q[k].where((Change.timestamp >= pdate) & (Change.timestamp < pdate1))
        if namech:
            q[k] = q[k].where((Change.action == 'm') & (Change.changes.contains('"name"')))
        if country:
            q[k] = q[k].where(Change.country == country)

    # Export geojson if export option is set
    if request.args.get('export', None) == '1':
        features = []
        for ch in q['changes'].limit(3000):
            coord = ch.changed_coord()
            if coord is None:
                continue
            props = { 'obj_type': ch.obj_type, 'obj_id': ch.obj_id, 'action': ch.action, 'main_tag': ch.main_tag, 'user': ch.user }
            f = { 'type': 'Feature', 'properties': props, 'geometry': { 'type': 'Point', 'coordinates': [float(coord[0]), float(coord[1])] } }
            features.append(f)
        content = json.dumps({ 'type': 'FeatureCollection', 'features': features })
        return send_file(StringIO(str(content)), mimetype='Content-Type: application/vnd.geo+json',
                         attachment_filename='mapsme_changes.geojson', as_attachment=True)

    # Calculate statistics
    stats = {}
    stats['created'] = stats['deleted'] = stats['modified'] = stats['notes'] = stats['anomalies'] = 0
    stats['nodes'] = stats['ways'] = stats['relations'] = stats['total'] = 0
    for stat in q['stat_src']:
        stats['total'] += stat.count
        if stat.action == 'c':
            stats['created'] += stat.count
        elif stat.action == 'd':
            stats['deleted'] += stat.count
        elif stat.action == 'm':
            stats['modified'] += stat.count
        elif stat.action == 'n':
            stats['notes'] += stat.count
        elif stat.action == 'a':
            stats['anomalies'] += stat.count
        if stat.obj_type == 'n':
            stats['nodes'] += stat.count
        elif stat.obj_type == 'w':
            stats['ways'] += stat.count
        elif stat.obj_type == 'r':
            stats['relations'] += stat.count
    stats['pages'] = (stats['total'] + config.PAGE_SIZE - 1) / config.PAGE_SIZE
    stats['users'] = q['users'].count(clear_limit=True)

    return render_template('index.html', stats=stats,
                           changes=q['changes'], users=q['users'], tags=q['tags'],
                           versions=q['versions'], dates=q['dates'], countries=q['countries'],
                           params=params, purl=purl)
