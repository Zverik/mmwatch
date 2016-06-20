DEBUG = True

import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'server', 'mapsme-changes.db')
# DATABASE_URI = 'postgresql://localhost/mmwatch'

PAGE_SIZE = 100
TOP = 10

QUERYAT_URL = 'http://tile.osmz.ru/queryat/'
GEOCODE_BATCH = 20
