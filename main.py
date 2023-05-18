import requests
import json
import urllib.parse
import json
from tqdm import tqdm
import os

BEARER = "" # Bearer ....
CLIENT_TOKEN = "" # comes from https://clienttoken.spotify.com/v1/clienttoken
SPOTIFY_APP_VERSION = "" # use latest x.y.zz.aaa.a0b1c2d3e
LYRICS_URL = "https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}?format=json&vocalRemoval=false&market=from_token"
DISCOGRAPHY_URL = "https://api-partner.spotify.com/pathfinder/v1/query?operationName=queryArtistDiscographyAll&variables={variables}&extensions={extensions}"
DISCOGRAPHY_EXTENSIONS = {"persistedQuery":{"version":1,"sha256Hash":"35a699e12a728c1a02f5bf67121a50f87341e65054e13126c03b7697fbd26692"}}
DISCOGRAPHY_VARIABLES = {"uri":"spotify:artist:{uri}","offset":0,"limit":100}
ALBUM_TRACKS_URL = "https://api-partner.spotify.com/pathfinder/v1/query?operationName=queryAlbumTracks&variables={variables}&extensions={extensions}"
ALBUM_TRACKS_VARIABLES = {"uri":"{uri}","offset":0,"limit":300}
ALBUM_TRACKS_EXTENSIONS = {"persistedQuery":{"version":1,"sha256Hash":"f387592b8a1d259b833237a51ed9b23d7d8ac83da78c6f4be3e6a08edef83d5b"}}

headers = {
    "accept": "application/json",
    "accept-language": "en",
    "app-platform": "WebPlayer",
    "authorization": f"{BEARER}",
    "client-token": f"{CLIENT_TOKEN}",
    "spotify-app-version": SPOTIFY_APP_VERSION,
    "Referer": "https://open.spotify.com/",
    "Referrer-Policy": "strict-origin-when-cross-origin"
  }

def get_lyrics(track_id: str) -> dict:
  r = requests.get(LYRICS_URL.format(track_id=track_id), headers=headers)
  if not r.ok:
    return None
  else:
    return r.json()

def lyrics_to_text(lyrics: dict) -> str:
  if 'lyrics' in lyrics:
    lyrics = lyrics['lyrics']
  text = ""
  for line in lyrics['lines']:
    text += f"{line['words']}\n"
  return text

def format_extensions(extensions: dict) -> str:
  return urllib.parse.quote(
    json.dumps(
      extensions
    ).replace(" ", "")
  )

def format_variables(variables: dict, uri: str) -> str:
  _variables = variables.copy()
  _variables['uri'] = _variables['uri'].format(uri=uri)
  return urllib.parse.quote(
    json.dumps(
      _variables
    ).replace(" ", "")
  )

def get_discography(artist_id: str) -> list:
  r = requests.get(
    DISCOGRAPHY_URL.format(
      variables = format_variables(DISCOGRAPHY_VARIABLES, artist_id),
      extensions = format_extensions(DISCOGRAPHY_EXTENSIONS)
    ),
    headers=headers
  )
  j = r.json()
  return j['data']['artistUnion']['discography']['all']['items']

def get_album_tracks(album_uri: str) -> list:
  r = requests.get(
    ALBUM_TRACKS_URL.format(
      variables = format_variables(ALBUM_TRACKS_VARIABLES, album_uri),
      extensions = format_extensions(ALBUM_TRACKS_EXTENSIONS)
    ),
    headers=headers
  )
  j = r.json()
  return j['data']['albumUnion']['tracks']['items']

def related_artists(artist_id: str) -> list:
  r = requests.get(
     f"https://api.spotify.com/v1/artists/{artist_id}/related-artists",
     headers=headers
  )
  artists = []
  for artist in r.json()['artists']:
    artists.append(artist['uri'])
  return artists

def spider_artists(initial_artist_id: str = None, artists_json_file: str = None, searched_json_file: str = "searched.json"):
    if initial_artist_id is None and artists_json_file is None:
       print("initial_artist_id or artists_json_file required")
       return
    if initial_artist_id and artists_json_file:
       print("initial_artist_id or artists_json_file")
       return
    if initial_artist_id:
        initial_artist_id = initial_artist_id.replace("spotify:artist:", "")
        try:
            related = related_artists(artist_id)
        except Exception as e:
            print(e)
        artists = related
        searched = []
    else:
       artists = json.load(open(artists_json_file))
       searched = json.load(open(searched_json_file))
    original = set(artists)
    all_artists = set(artists)
    artists = list(set(artists) - set(searched))

    artist_bar = tqdm(total=len(original))
    artist_bar.update(len(original))

    idx = 0
    while len(artists) > 0:
        artist_id = artists.pop()
        artist_id = artist_id.replace("spotify:artist:", "")
        try:
            related = related_artists(artist_id)
        except Exception as e:
            print(e)
            break
        new = set(related) - all_artists
        artist_bar.desc = f"{idx}/{len(artists)}"
        artist_bar.total += len(new)
        artist_bar.update(len(new))
        artist_bar.refresh()
        for item in new:
            all_artists.add(item)
        idx += 1
    searched = list(original - set(artists)) + list(searched)
    json.dump(list(searched), open(searched_json_file, "w"))
    json.dump(list(all_artists), open(artists_json_file, "w"))

def lyrics(artists_json_file: str, base_path: str = "."):
    artists = json.load(open(artists_json_file))
    pbar = tqdm(artists, total=len(artists))
    for artist_id in artists:
        artist_id = artist_id.replace("spotify:artist:", "")
        if os.path.exists(f'{base_path}/artist_{artist_id}.json'):
            pbar.update(1)
            continue
        all_tracks = {}
        discography = get_discography(artist_id)
        for album in discography:
            for release in album['releases']['items']:
                album_id = release['uri'].replace('spotify:album:', '')
                all_tracks[album_id] = {}
                all_tracks[album_id]['raw'] = release
                all_tracks[album_id]['tracks'] = {}
                tracks = get_album_tracks(release['uri'])
                for track in tracks:
                    track_id = track['track']['uri'].replace('spotify:track:','')
                    all_tracks[album_id]['tracks'][track_id] = {}
                    all_tracks[album_id]['tracks'][track_id]['raw'] = track
                    lyrics = get_lyrics(track_id)
                    all_tracks[album_id]['tracks'][track_id]['lyrics'] = lyrics
                    desc = f"{artist_id}/{album_id}/{track_id}/"
                    if lyrics is None:
                        desc += "no lyrics"
                    else:
                        desc += lyrics['lyrics']['syncType']
                    pbar.desc = desc
                    pbar.refresh()
        with open(f'{base_path}/artist_{artist_id}.json', "w", encoding="utf-8") as f:
            json.dump(all_tracks, f)
        pbar.update(1)

if __name__ == "__main__":
   print(
   """
   spider_artists(initial_artist_id="...") # with or without spotify:artist:
   after initial_artist_id 
   spider_artists(artists_json_file="all_artists.json")
   repeat until you reach required number of artists
   then 
   lyrics(artists_json_file="all_artists.json"
   """
   )