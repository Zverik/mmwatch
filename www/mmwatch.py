#!/usr/bin/python
import os, json, peewee
from flask import Flask, request, render_template, url_for
from flask.ext.compress import Compress
from datetime import datetime, timedelta
import config

app = Flask(__name__)
app.debug = config.DEBUG
Compress(app)

database = peewee.SqliteDatabase(os.path.join(config.DATABASE_PATH, 'mapsme-changes.db'))

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

  def explain_action(self):
    explains = { 'a': 'done smth strange', 'c': 'created', 'd': 'deleted', 'm': 'modified', 'n': 'left a note' }
    return explains[self.action]

  def changed_coord(self):
    if self.action == 'a':
      return None
    c = json.loads(self.changes)[0]
    if self.action == 'm':
      return c[1]
    return c

  def changed_tags(self):
    if self.action == 'a':
      return {}
    tags = json.loads(self.changes)[1]
    for t in tags:
      if self.action == 'c':
        tags[t] = [None, tags[t]]
      elif self.action == 'd':
        tags[t] = [tags[t], None]
      if tags[t][0] is None:
        tags[t].append('create')
      elif tags[t][1] is None:
        tags[t].append('delete')
      elif tags[t][0] != tags[t][1]:
        tags[t].append('modify')
      else:
        tags[t].append('nothing')
    return tags

  class Meta:
    database = database
    db_table = 'mapsme_change'

@app.before_request
def before_request():
  database.connect()

@app.teardown_request
def teardown(exception):
  if not database.is_closed():
    database.close()

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

  # Construct queries
  q = {}
  q['changes'] = Change.select().order_by(Change.id.desc()).paginate(params['page'], config.PAGE_SIZE)
  q['users'] = Change.select(Change.user, peewee.fn.Count(Change.id).alias('count')).group_by(Change.user).order_by(peewee.fn.Count(Change.id).desc())
  q['tags'] = Change.select(Change.main_tag, peewee.fn.Count(Change.id).alias('count')).group_by(Change.main_tag).order_by(peewee.fn.Count(Change.id).desc())
  q['versions'] = Change.select(Change.version, peewee.fn.Count(Change.id).alias('count')).group_by(Change.version).order_by(peewee.fn.Count(Change.id).desc())
  q['stat_src'] = Change.select(Change.action, Change.obj_type, peewee.fn.Count(Change.id).alias('count')).group_by(Change.action, Change.obj_type).order_by(peewee.fn.Count(Change.id).desc())
  q['dates'] = Change.select(Change.timestamp, peewee.fn.Count(Change.id).alias('count')).group_by(Change.timestamp.day).order_by(-Change.id)
  # TODO: debug timezones

  # Apply filters
  for k in q:
    if user:
      q[k] = q[k].where(Change.user == user)
    if version:
      q[k] = q[k].where(Change.version == version)
    if action:
      q[k] = q[k].where(Change.action == action)
    if platform:
      if platform != 'other':
        q[k] = q[k].where(Change.version.startswith('MAPS.ME {0}'.format(platform)))
      else:
        q[k] = q[k].where(~Change.version.startswith('MAPS.ME ios') & ~Change.version.startswith('MAPS.ME android'))
    if not nolimit:
      if k in ('users', 'tags', 'versions', 'dates'):
        q[k] = q[k].limit(config.TOP)
    if date:
      pdate = datetime.strptime(date + ' UTC', '%d.%m.%Y %Z')
      pdate1 = pdate + timedelta(days=1)
      q[k] = q[k].where((Change.timestamp >= pdate) & (Change.timestamp < pdate1))

  # Calculate statistics
  stats = {}
  stats['created'] = stats['deleted'] = stats['modified'] = stats['anomalies'] = 0
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

  # List of dates for filtering
  dates = []
  for row in q['dates']:
    dates.append(row.timestamp.strftime('%d.%m.%Y'))
  if False:
    curdate = datetime.now()
    earliest = Change.select(Change.timestamp).order_by(Change.id).limit(1).get().timestamp - timedelta(days=1)
    for n in range(100 if nolimit else config.TOP):
      if curdate < earliest:
        break
      dates.append(curdate.strftime('%d.%m.%Y'))
      curdate -= timedelta(days=1)

  return render_template('index.html', stats=stats, changes=q['changes'], users=q['users'], tags=q['tags'], versions=q['versions'], dates=q['dates'], params=params, purl=purl)

if __name__ == '__main__':
  app.run(threaded=True)
