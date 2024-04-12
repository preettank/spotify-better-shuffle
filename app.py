from dotenv import load_dotenv
import os
from flask import Flask, request, url_for, session, redirect, render_template, make_response
from spotipy.oauth2 import SpotifyOAuth
import time
import spotipy
import random
import json

load_dotenv()
# App config
app = Flask(__name__)

app.secret_key = os.getenv("APP_KEY")
app.config['SESSION_COOKIE_NAME'] = "COOKIES"
TOKEN_INFO = "token_info"

@app.route('/')
def home():
    # landing page
    return render_template('home.html')


@app.route('/login')
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
    token_info = sp_oauth.get_access_token(code, check_cache =False)
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
            # skip local files and unplayable songs in the user's market from available tracks
            try:
                if track['track']['is_local']:
                    continue
                elif track['track']['is_playable'] == False:
                    continue
            except:
                continue

            indexes[i+1] = [track['track']['uri'], track['track']['name'], track['track']['album']['images'][2]['url']]
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
            track_data.append([indexes[num][1], num, indexes[num][2], indexes[num][3]])

        playlist_data, devices = playlists_devices(sp)

        # checks the premium status of the user, if not premium does not start playback
        user_premium_status = sp.current_user()['product']
        if user_premium_status != "premium":
            return render_template('getTracks.html', track_data=track_data, playlist_data = playlist_data, devices = devices, user_premium_status= user_premium_status, uris = uris)
        
        # starts playback on the user-specified device based on the track uris
        try:
            sp.start_playback(uris=uris, offset = {"position": 0}, device_id=device)
        except:
            return "Must select both a playlist and a device. If no device showed up, activate the device by playing something on the player. Then go back to the previous page."
        sp.shuffle(state=False, device_id=device)

        return render_template("getTracks.html", track_data=track_data, playlist_data=playlist_data, devices = devices, user_premium_status= user_premium_status, uris = uris)
        
    else:
        playlist_data, devices = playlists_devices(sp)
        user_premium_status = sp.current_user()['product']
        return render_template('getTracks.html', playlist_data=playlist_data, devices = devices, user_premium_status= user_premium_status)

# creates new playlist with the shuffled tracks
# checks dynamically with htmx if the create playlist button was clicked
@app.route('/createPlaylist', methods=['POST'])
def createPlaylist():
    try:
        token_info = get_token()
    except:
        print("user not logged in")
        return redirect(url_for("login", _external=False))
    sp = spotipy.Spotify(auth=token_info['access_token'])

    data = request.get_json()

    uris = data.get('uris')
    user_id = sp.current_user()['id']

    created_playlistID = sp.user_playlist_create(user=user_id, name="Better Shuffle Results", public=True, collaborative=False, description="Playlist automatically generated by https://github.com/preettank/spotify-better-shuffle")['id']
    # can only add a maxium of 100 so if total shuffled tracks is ever changed make sure to for loop below statment
    sp.user_playlist_add_tracks(user=user_id, playlist_id=created_playlistID, tracks = eval(uris))

    response = make_response('', 204)
    return response

# skips to the next track or goes back to the previous track
# checks dynamically with htmx if either skip button was clicked
@app.route('/skipTrack', methods=['POST'])
def skipTrack():
    try:
        token_info = get_token()
    except: 
        print("user not logged in")
        return redirect(url_for("login", _external=False))
    sp = spotipy.Spotify(auth=token_info['access_token'])

    if 'skip' in request.form:
        sp.next_track()
    elif 'skipB' in request.form:
        sp.previous_track()

    response = make_response('', 204)
    return response

# plays the track that was clicked on the table
# checks dynamically with javascript if a row was clicked
@app.route('/rowClicked', methods=['POST'])
def rowClicked():
    try:
        token_info = get_token()
    except:
        print("user not logged in")
        return redirect(url_for("login", _external=False)
    )
    sp = spotipy.Spotify(auth=token_info['access_token'])

    data = request.get_json()
    row_index_json = data.get('rowIndex')
    row_index = json.loads(row_index_json)['rowIndex']
    uris = data.get('uris')

    sp.start_playback(uris=eval(uris), offset = {"position": row_index})

    response = make_response('', 204)
    return response

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
        scope=("user-library-read", "playlist-read-private", "user-modify-playback-state", "user-read-playback-state", "user-read-private", "playlist-modify-public"))


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
