DEBUG = True

import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'server', 'mapsme-changes.db')
# DATABASE_URI = 'postgresql://localhost/mmwatch'

PAGE_SIZE = 100
TOP = 10

# See https://github.com/Zverik/queryat
# Example: 'http://localhost:5000/queryat/'
QUERYAT_URL = None
GEOCODE_BATCH = 20
