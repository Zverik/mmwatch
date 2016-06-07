# MAPS.ME Monitoring Site

A script and a simple web page for vieweing MAPS.ME edits statistics.
It is installed at [osmz.ru](http://py.osmz.ru/mmwatch/).

## Installation

First, add `server/mapsme-process.py` to crontab. Like this:

    */3 * * * * /var/www/sites/mmwatch/mmwatch/process.py >> /var/www/sites/mmwatch/mmwatch/mapsme-process.log

It will create a database of changes and start updating it once every three minutes.
If you need to pre-populate the database with earlier edits, comment out the cron line,
delete `mapsme-changes.db`, edit the sequence number in `mapsme-state.txt` to an earlier value
and run `mapsme-process.py` from a command line. It works rather slow, so be prepared to wait and,
if unlucky, respond to OSM admins' mail about making requests to the API too often.

When pushing to the production, turn off `DEBUG` in `mmwatch/config.py`.

Now you need to add the WSGI application to your web server. Refer to [this manual](http://flask.pocoo.org/docs/0.10/deploying/)
or maybe [this one about Gunicorn](https://www.digitalocean.com/community/tutorials/how-to-deploy-python-wsgi-apps-using-gunicorn-http-server-behind-nginx).

## Switching to Another Database

Edit `mmwatch/config.py`, replacing the `DATABASE_URI`.
Refer to [this section](http://docs.peewee-orm.com/en/latest/peewee/database.html#connecting-using-a-database-url)
of the Peewee documentation.

## API

There is almost no API in the service, except `/user?name=<OSM User Name>` call,
which returns user's rank and number of edits.

## Author and License

Written by Ilya Zverev, published under WTFPL.
