from www import app
from flask import render_template, session, url_for, redirect
from flask_oauthlib.client import OAuth, get_etree
import config
from db import database, Change

API_ENDPOINT = 'https://api.openstreetmap.org/api/0.6/'

oauth = OAuth()
openstreetmap = oauth.remote_app('OpenStreetMap',
                                 base_url=API_ENDPOINT,
                                 request_token_url='https://www.openstreetmap.org/oauth/request_token',
                                 access_token_url='https://www.openstreetmap.org/oauth/access_token',
                                 authorize_url='https://www.openstreetmap.org/oauth/authorize',
                                 consumer_key=config.OAUTH_KEY,
                                 consumer_secret=config.OAUTH_SECRET
                                 )


@app.route('/revert')
def revert():
    if 'osm_token' not in session:
        return openstreetmap.authorize(callback=url_for('oauth'))
    return 'TODO'


@app.route('/oauth')
@openstreetmap.authorized_handler
def oauth(resp):
    if resp is None:
        return 'Denied. <a href="' + url_for('revert') + '">Try again</a>.'
    session['osm_token'] = (
            resp['oauth_token'],
            resp['oauth_token_secret']
    )
    user_details = openstreetmap.get('user/details').data
    session['osm_username'] = user_details[0].get('display_name')
    return redirect(url_for('revert'))


@openstreetmap.tokengetter
def get_token(token='user'):
    if token == 'user' and 'osm_token' in session:
        return session['osm_token']
    return None


@app.route('/logout')
def logout():
    if 'osm_token' in session:
        del session['osm_token']
    if 'osm_username' in session:
        del session['osm_username']
    return redirect(url_for('the_one_and_only_page'))
