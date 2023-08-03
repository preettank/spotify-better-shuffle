from dotenv import load_dotenv
import os
from flask import Flask, request, url_for, session, redirect, render_template
from spotipy.oauth2 import SpotifyOAuth
import time
import spotipy
import random

load_dotenv()
# App config
app = Flask(__name__)

app.secret_key = os.getenv("APP_KEY")
app.config['SESSION_COOKIE_NAME'] = "COOKIES"
TOKEN_INFO = "token_info"


@app.route('/')
def login():
    sp_ouath = create_spotify_oauth()
    auth_url = sp_ouath.get_authorize_url()
    return redirect(auth_url)


@app.route('/redirect')
def redirectPage():
    if os.path.exists(os.getenv("CACHE_PATH")):
        os.remove(os.getenv("CACHE_PATH"))
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('getPlaylist', _external=True))


@app.route('/getPlaylist', methods =['POST', 'GET'])
def getPlaylist():
    if os.path.exists(os.getenv("CACHE_PATH")):
        os.remove(os.getenv("CACHE_PATH"))
    try:
        token_info = get_token()
    except:
        print("user not logged in")
        return redirect(url_for("login", _external=False))
    sp = spotipy.Spotify(auth=token_info['access_token'])

    if request.method == 'POST':
        # checks the premium status of the user
        user_premium_status = sp.current_user()['product']
        if user_premium_status != "premium":
            return "Sorry you must be a premium user to use this app."
        
        # obtains the user-specified playlist/device id
        playlist_id = request.form.get('playlists')
        device = request.form.get('devices')

        # obtains user tracks from the specified playlist
        iteration = 0
        all_songs = []
        user_market = sp.current_user()['country']
        while True:
            tracks = sp.playlist_tracks(playlist_id= playlist_id, fields=None, limit=100, offset=iteration * 100, market=user_market)['items']
            iteration += 1
            all_songs += tracks
            if (len(tracks) < 100):
                break
        
        # obtains specific track data and puts it in a dictionary
        indexes = {}
        available_tracks = []
        for i, track in enumerate(all_songs):
            indexes[i+1] = [track['track']['uri'], track['track']['name']]
            if len(track['track']['artists']) > 1:
                artists = ""
                counter = 1
                for names in track['track']['artists']:
                    artists += f"{names['name']}"
                    if counter != len(track['track']['artists']):
                        artists += ", "
                    counter += 1
                indexes[i+1].append(artists)
            else:
                indexes[i+1].append(track['track']['artists'][0]['name'])
            # removes local files and unplayable songs in the user's market from available tracks
            if track['track']['is_local']:
                del indexes[i+1]
            elif track['track']['is_playable'] == False:
                del indexes[i+1]
            else:
                available_tracks.append(i+1)
        
        # generates 75 random numbers from the available track indexes
        if len(available_tracks) > 75:
            numbers = random.sample(available_tracks, 75)
        else:
            numbers = random.sample(available_tracks, len(available_tracks))

        # from the numbers, obtains the uris of the tracks
        uris = []
        track_data = []
        for num in numbers:
            uris.append(indexes[num][0])
            track_data.append([indexes[num][1], num, indexes[num][2]])

        # starts playback on the user-specified device based on the uris
        try:
            sp.start_playback(uris=uris, offset = {"position": 0}, device_id=device)
        except:
            return "Must select both a playlist and a device. If no device showed up, activate the device by playing something on the player. Then go back to the previous page."
        sp.shuffle(state=False, device_id=device)

        playlist_data, devices = playlists_devices(sp)

        return render_template("getTracks.html", track_data=track_data, playlist_data=playlist_data, devices = devices)
        
    else:
        playlist_data, devices = playlists_devices(sp)
        return render_template('getTracks.html', playlist_data=playlist_data, devices = devices)


# Checks to see if token is valid and gets a new token if not
def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        raise "exception"
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if (is_expired):
        sp_ouath = create_spotify_oauth()
        token_info = sp_ouath.refresh_access_token(token_info['refresh_token'])
    return token_info


def create_spotify_oauth():
    return SpotifyOAuth(
        client_id = os.getenv("CLIENT_ID"),
        client_secret = os.getenv("CLIENT_SECRET"),
        redirect_uri=url_for('redirectPage', _external=True),
        scope=("user-library-read", "playlist-read-private", "user-modify-playback-state", "user-read-playback-state", "user-read-private"))


# obtains user playlist and device data
def playlists_devices(sp):
    iteration = 0
    all_playlists = []
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=0)['items']
        iteration += 1
        all_playlists += playlists
        if (len(playlists) < 50):
            break

    playlist_data = []
    for i, playlist in enumerate(playlists):
        playlist_data.append([playlist['name'], playlist['uri'], playlist['id'], playlist['owner']['display_name']])

    devices = sp.devices()['devices']

    return playlist_data, devices
