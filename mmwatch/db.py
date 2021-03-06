import config
import json
import time
from peewee import *
from playhouse.db_url import connect

database = connect(config.DATABASE_URI)
if 'mysql' in config.DATABASE_URI:
    database.execute_sql("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci;")


class BaseModel(Model):
    class Meta:
        database = database


class Change(BaseModel):
    """A model for the change. Just a single table."""
    changeset = IntegerField()
    user = CharField(max_length=190, index=True)
    version = CharField(max_length=250)
    timestamp = DateTimeField(index=True)
    action = FixedCharField(max_length=1, index=True)  # c=created, d=deleted, m=modified, a=anomaly, n=note
    obj_type = FixedCharField(max_length=1, null=True)
    obj_id = BigIntegerField(null=True)
    main_tag = CharField(max_length=100, null=True)
    address = BooleanField(default=False)
    processed = IntegerField(null=True)  # number of hours between modifying and an external fix of the object
    country = CharField(max_length=150, null=True, index=True)
    changes = TextField()

    def explain_action(self):
        explains = {'a': 'done smth strange', 'c': 'created', 'd': 'deleted', 'm': 'modified', 'n': 'left a note'}
        return explains[self.action]

    def changed_coord(self):
        if self.action == 'a':
            return None
        c = json.loads(self.changes)[0]
        if self.action == 'm' and c is not None:
            return c[1]
        return c

    def changed_tags(self):
        if self.action == 'a':
            return {}
        tags = json.loads(self.changes)[1]
        for t in tags:
            if self.action in ('c', 'n'):
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


class Seen(BaseModel):
    """A model for a storage of processed objects."""
    obj = CharField(max_length=30, index=True)


class User(BaseModel):
    """A model for user stats."""
    user = CharField(max_length=190, unique=True)
    edits = IntegerField()
    rank = IntegerField(default=0)
    joined = DateField()


class State(BaseModel):
    """A model for storing replication state."""
    state = IntegerField()  # Replication state
    notes = IntegerField(default=0)  # File size of notes dump
    hourly = IntegerField(default=0)  # Unix Timestamp of last object check

    def run_hourly(self):
        """Returns True if it's time to run hourly tasks."""
        timestamp = time.time()
        return self.hourly + 3600 < timestamp

    def update_hourly(self):
        self.hourly = int(time.time())
