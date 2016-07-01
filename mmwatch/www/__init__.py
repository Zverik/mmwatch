from flask import Flask
import config

app = Flask(__name__)
app.debug = config.DEBUG

try:
    from flask_compress import Compress
    Compress(app)
except ImportError:
    pass

import www.mmwatch
import www.revert
