import os
import re
from dotenv import load_dotenv
import time
import spotipy
import requests
import streamlit as st
import lyricsgenius as lg
from bs4 import BeautifulSoup
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

st.title("Producer Search🔍")
st.header("Find Your Music!")

client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI")
genius_access_token = os.getenv("GENIUS_ACCESS_TOKEN")

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, '
                  'like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

base_url = 'https://genius.com/artists'

spots = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope='user-library-read'
))

genius = lg.Genius(genius_access_token, timeout=10, retries=3)


def parse_input(user_input):
    if " by " in user_input.lower():
        track_name, artist_name = user_input.split(" by ", 1)
        return track_name.strip(), artist_name.strip()
    st.warning("Please use the format above")
    return None, None


def get_song_details(track_name, artist_name):
    try:
        song = genius.search_song(track_name, artist_name)
        if not song:
            print(f"{track_name} by {artist_name} doesn't exist on Genius")
            return None, None

        print(f"Your song: {song.title} by {song.artist} has been found😗🫵🏽")

        producers = []

        song_info = genius.song(song.id)
        description = song_info.get('song', {}).get('description', {}).get('plain', '')

        producer_pattern = r'(?:Produced by|Producer[s]?|Production by)\s*([^,\n.]+?)(?:,|\sand\s|$)'
        matches = re.findall(producer_pattern, description, re.IGNORECASE)
        if matches:
            for match in matches:
                cleaned = [name.strip() for name in match.split('&') if name.strip()]
                producers.extend(cleaned)

        if not producers and 'producer_artists' in song_info.get('song', {}):
            producers = [p['name'] for p in song_info['song']['producer_artists']]

        return song.id, producers if producers else None
    except Exception as e:
        print(f"There was an error fetching song details from Genius: {e}")
        return None, None



def song_search(producer_name):
    try:
        url = f"https://genius.com/artists/{producer_name}"
        print(f"Scraping producer page now 🔍... ({url})")
        time.sleep(1)

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        page_soup = BeautifulSoup(response.text, 'html.parser')

        song_data = {
            'producer_name': producer_name,
            'songs': []
        }

        titles = page_soup.find_all('div', class_='mini_card-title')
        artists = page_soup.find_all('div', class_='mini_card-subtitle')

        if titles and artists:
            for title_el, artist_el in zip(titles, artists):
                title = title_el.get_text(strip=True)
                artist = artist_el.get_text(strip=True)
                song_data['songs'].append({'title': title, 'artist': artist})
        else:
            print(f"{producer_name} has zero song cards on their page. Chai😔✋🏽!")

        return song_data

    except Exception as e:
        import traceback
        print(f"There was an error scraping {producer_name}'s page : {e}")
        traceback.print_exc()
        return {'producer_name': producer_name, 'songs': []}


user_input = st.text_input("Enter a track name and artist (e.g., Gimme Dat by Ayra):")

suggested_input = None
if user_input:
    results = spots.search(q=user_input, type='track', limit=5)
    suggestions = [f"{item['name']} by {item['artists'][0]['name']}" for item in results['tracks']['items']]

    if suggestions:
        suggested_input = st.selectbox("Did you mean:", suggestions)
    else:
        st.info("No suggestions found yet. Try refining your search.")

final_input = suggested_input if suggested_input else user_input

if st.button("Find Your Music"):
    if not final_input:
        st.warning("Please enter a track and artist.")
    else:
        track_name, artist_name = parse_input(final_input)
        if not artist_name:
            st.warning("Please include artist name using format: Track by Artist.")
        else:
            with st.spinner(f"Searching Spotify for '{track_name}' by {artist_name}..."):
                result = spots.search(q=f"{track_name} {artist_name}", type='track', limit=1)

            if not result['tracks']['items']:
                st.error(f"{track_name} by {artist_name} was not found on Spotify.")
            else:
                track = result['tracks']['items'][0]
                artist_name = track['artists'][0]['name']
                st.success(f"Found: '{track['name']}' by {artist_name}")

                spotify_url = track.get('external_urls', {}).get('spotify')
                if spotify_url:
                    st.markdown(f'[🔗-Spotify]({spotify_url})')

                with st.spinner("Finding your producers..."):
                    song_id, producers = get_song_details(track['name'], artist_name)

                if not song_id:
                    st.error("No song found on Genius!")
                else:
                    if producers:
                        st.info(f"Producers: {', '.join(producers)}")
                        for producer in producers:
                            with st.spinner(f"Scraping your favorites now..."):
                                producer_slug = producer.lower().replace(" ", "-")
                                song_data = song_search(producer_slug)

                            with st.expander(f"Songs by {producer}"):
                                if song_data and song_data['songs']:
                                    for idx, song in enumerate(song_data['songs'], start=1):
                                        try:
                                            search_result = spots.search(q=f"{song['title']} {song['artist']}",
                                                                         type='track', limit=1)
                                            if search_result['tracks']['items']:
                                                song_url = search_result['tracks']['items'][0]['external_urls'][
                                                    'spotify']
                                                st.markdown(
                                                    f"{idx}. {song['title']} by {song['artist']}  — [🔗 Spotify]({song_url})")
                                            else:
                                                st.write(
                                                    f"{idx}. {song['title']} by {song['artist']} (Not found on Spotify)")
                                        except Exception as e:
                                            st.write(
                                                f"{idx}. {song['title']} by {song['artist']} (Error searching Spotify)")
                                else:
                                    st.warning(f"No songs found on producer page '{producer_slug}'.")
                    else:
                        st.warning(f"No producer info found on Genius for '{track['name']}' by {artist_name}.")
