import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DEBUG = True

DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'server', 'mapsme-changes.db')
# DATABASE_URI = 'postgresql://localhost/mmwatch'

PAGE_SIZE = 100
TOP = 10
BAN_USERS = set([481934])
HIDE_FILTERS = True

# See https://github.com/Zverik/queryat
# Example: 'http://localhost:5000/queryat/'
QUERYAT_URL = None
GEOCODE_BATCH = 20

# Override these (and anything else) in config_local.py
OAUTH_KEY = ''
OAUTH_SECRET = ''
SECRET_KEY = 'sdkjfhsfljhsadf'

# Set to the URL of mmwatch installation, to update filters
ENDPOINT = None

try:
    from config_local import *
except ImportError:
    pass
