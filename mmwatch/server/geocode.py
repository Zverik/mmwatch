#!/usr/bin/env python
import urllib2
import json
import config
from db import database, Change


def geocode(lon, lat):
    """Returns a country by these coordinates."""
    try:
        url = '{0}qr?lon={1}&lat={2}'.format(config.QUERYAT_URL, lon, lat)
        resp = urllib2.urlopen(url)
        data = json.load(resp)
        if 'countries' in data and len(data['countries']) > 0:
            c = data['countries'][0]
            return c['en' if 'en' in c else 'name'].encode('utf-8')
        print('Could not geocode: {0}'.format(url))
        return 'Unknown'
    except urllib2.HTTPError:
        print('HTTPError: ' + url)
    except urllib2.URLError:
        print('URLError: ' + url)
    return None


def add_countries():
    if config.QUERYAT_URL is None or config.GEOCODE_BATCH <= 0:
        return
    database.connect()
    with database.atomic():
        q = Change.select().where((Change.country >> None) & (Change.action != 'a') & (~Change.changes.startswith('[[null, null]'))).limit(
            config.GEOCODE_BATCH + 200)
        count = config.GEOCODE_BATCH
        for ch in q:
            coord = ch.changed_coord()
            if coord is not None:
                country = geocode(coord[0], coord[1])
                if country is not None:
                    ch.country = country[:150]
                    ch.save()
            else:
                # print('Empty coordinates: {0} {1} {2}'.format(ch.id, ch.action, ch.changes.encode('utf-8')))
                pass

            # We request more because of these empty coordinates errors
            count -= 1
            if count <= 0:
                break


if __name__ == '__main__':
    add_countries()
