import os.path, sys
from peewee import *

#path = os.path.dirname(sys.argv[0]) if len(sys.argv) < 2 else sys.argv[1]
path = os.path.dirname(sys.argv[0])
database = SqliteDatabase(os.path.join(path, 'mapsme-changes.db'))

class Change(Model):
  """A model for the change. Just a single table."""
  changeset = IntegerField()
  user = CharField(max_length=250, index=True)
  version = CharField(max_length=250)
  timestamp = DateTimeField(index=True)
  action = FixedCharField(max_length=1, index=True) # c=created, d=deleted, m=modified, a=anomaly, n=note
  obj_type = FixedCharField(max_length=1, null=True)
  obj_id = IntegerField(null=True)
  main_tag = CharField(max_length=100, null=True)
  address = BooleanField(default=False)
  processed = IntegerField(null=True) # number of hours between modifying and an external fix of the object
  changes = TextField()

  class Meta:
    database = database

class Seen(Model):
  """A model for a storage of processed objects."""
  obj = TextField(index=True)

  class Meta:
    database = database

class User(Model):
  """A model for user stats."""
  user = CharField(max_length=250, unique=True)
  edits = IntegerField()
  rank = IntegerField(default=0)
  joined = DateField()

  class Meta:
    database = database
