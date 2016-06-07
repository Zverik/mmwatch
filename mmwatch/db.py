import config
import json
from peewee import *
from playhouse.db_url import connect

database = connect(config.DATABASE_URI)


class BaseModel(Model):
    class Meta:
        database = database


class Change(BaseModel):
    """A model for the change. Just a single table."""
    changeset = IntegerField()
    user = CharField(max_length=250, index=True)
    version = CharField(max_length=250)
    timestamp = DateTimeField(index=True)
    action = FixedCharField(max_length=1, index=True)  # c=created, d=deleted, m=modified, a=anomaly, n=note
    obj_type = FixedCharField(max_length=1, null=True)
    obj_id = IntegerField(null=True)
    main_tag = CharField(max_length=100, null=True)
    address = BooleanField(default=False)
    processed = IntegerField(null=True)  # number of hours between modifying and an external fix of the object
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


class Seen(BaseModel):
    """A model for a storage of processed objects."""
    obj = TextField(index=True)


class User(BaseModel):
    """A model for user stats."""
    user = CharField(max_length=250, unique=True)
    edits = IntegerField()
    rank = IntegerField(default=0)
    joined = DateField()


class State(BaseModel):
    """A model for storing replication state."""
    state = IntegerField()
