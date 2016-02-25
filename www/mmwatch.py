#!/usr/bin/python
import os, json, peewee
from flask import Flask, request, render_template
from flask.ext.compress import Compress
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

@app.route('/')
def the_one_and_only_page():
  changes = Change.select().order_by(Change.id.desc()).paginate(1, config.PAGE_SIZE)
  users = Change.select(Change.user, peewee.fn.Count(Change.id).alias('count')).group_by(Change.user).order_by(peewee.fn.Count(Change.id).desc()).limit(config.TOP)
  tags = Change.select(Change.main_tag, peewee.fn.Count(Change.id).alias('count')).group_by(Change.main_tag).order_by(peewee.fn.Count(Change.id).desc()).limit(config.TOP)
  versions = Change.select(Change.version, peewee.fn.Count(Change.id).alias('count')).group_by(Change.version).order_by(peewee.fn.Count(Change.id).desc()).limit(config.TOP)
  stat_src = Change.select(Change.action, Change.obj_type, peewee.fn.Count(Change.id).alias('count')).group_by(Change.action, Change.obj_type).order_by(peewee.fn.Count(Change.id).desc()).limit(config.TOP)
  stats = {}
  stats['created'] = stats['deleted'] = stats['modified'] = stats['anomalies'] = 0
  stats['nodes'] = stats['ways'] = stats['relations'] = stats['total'] = 0
  for stat in stat_src:
    stats['total'] += stat.count
    if stat.action == 'c':
      stats['created'] += stat.count
    elif stat.action == 'd':
      stats['deleted'] += stat.count
    elif stat.action == 'm':
      stats['modified'] += stat.count
    elif stat.action == 'a':
      stats['anomalies'] += stat.count
    if stat.obj_type == 'n':
      stats['nodes'] += stat.count
    elif stat.obj_type == 'w':
      stats['ways'] += stat.count
    elif stat.obj_type == 'r':
      stats['relations'] += stat.count

  return render_template('index.html', stats=stats, changes=changes, users=users, tags=tags, versions=versions)

if __name__ == '__main__':
  app.run(threaded=True)
