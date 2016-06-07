DEBUG = True

import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'server', 'mapsme-changes.db')

PAGE_SIZE = 100
TOP = 10
