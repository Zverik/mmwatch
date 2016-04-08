import os.path, sys
import peewee

path = os.path.dirname(sys.argv[0]) if len(sys.argv) < 2 else sys.argv[1]
database = peewee.SqliteDatabase(os.path.join(path, 'mapsme-changes.db'))

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

class Seen(peewee.Model):
  """A model for a storage of processed objects."""
  obj = peewee.TextField(index=True)
  class Meta:
    database = database
