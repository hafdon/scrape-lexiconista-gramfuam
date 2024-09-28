import requests
import io
from pydub import AudioSegment
from pydub.playback import play

# URL of the audio file
url = 'http://breistest.lexiconista.com/CanU-verb/dúirt%20mé.mp3'

# Fetch the audio file from the URL
response = requests.get(url)
audio_data = io.BytesIO(response.content)

# Load the audio file into pydub
audio = AudioSegment.from_file(audio_data, format="mp3")

# Play the audio
play(audio)
