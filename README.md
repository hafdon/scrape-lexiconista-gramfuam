# Audio Quiz App

## Overview

The Audio Quiz App is a Python-based application that allows users to test their knowledge of Irish verb pronunciations. The app plays audio files from a list of URLs and prompts the user to guess the correct text associated with the audio. The app supports three dialects: Munster (CanM), Ulster (CanU), and Connacht (CanC).

## Features

- **Dialect Selection**: Users can choose between Munster, Ulster, and Connacht dialects.
- **File Loading**: Load a list of audio URLs from a text file.
- **Audio Playback**: Play audio files directly from the URLs.
- **Answer Checking**: Users can input their guess and check if it matches the correct text.
- **Shuffling**: The list of URLs is shuffled to ensure a random order for each quiz session.

## Requirements

- Python 3.x
- `tkinter` for the GUI
- `requests` for downloading audio files
- `pygame` for audio playback

## Installation

1. Clone the repository:
    ```sh
    git clone irish-verb-form-audio-quiz
    cd irish-verb-form-audio-quiz
    ```

2. Create a virtual environment and activate it:
    ```sh
    python -m venv .venv
    source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
    ```

3. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

## Usage

1. Run the application:
    ```sh
    python audio_quiz_app.py
    ```

2. Select the dialect you want to practice.

3. Click "Open URL File" to load a text file containing the list of audio URLs.

4. Click "Play Audio" to start the quiz. The audio will play, and you can enter your guess in the provided entry box.

5. Click "Check Answer" to see if your guess is correct.

6. Click "Next" to move to the next audio file.

## Help
   ```commandline
   usage: check_gramplay_optimized.py [-h] [--concurrent-requests CONCURRENT_REQUESTS]
                                      [--batch-write-interval BATCH_WRITE_INTERVAL]
                                      [--retries RETRIES] [--backoff-factor BACKOFF_FACTOR]
   
   Process URLs with optional configuration.
   
   optional arguments:
     -h, --help            show this help message and exit
     --concurrent-requests CONCURRENT_REQUESTS
                           Number of concurrent requests (default: 400)
     --batch-write-interval BATCH_WRITE_INTERVAL
                           Seconds between batch writes (default: 5)
     --retries RETRIES     Number of retry attempts for failed requests (default: 3)
     --backoff-factor BACKOFF_FACTOR
                           Factor for exponential backoff (default: 12)
   
   ```

## File Format

The URL file should be a plain text file (`.txt`) with each line containing a single URL. Example:
```
http://breistest.lexiconista.com/CanM-verb/déarfadh%20sé.mp3
http://breistest.lexiconista.com/CanU-verb/déarfadh%20sé.mp3
http://breistest.lexiconista.com/CanC-verb/déarfadh%20sé.mp3
```

## .gitignore

The `.gitignore` file includes:
```
.venv
audio_files
```

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## Acknowledgements

- The audio files are sourced from Lexiconista.
- The app uses `pygame` for audio playback and `tkinter` for the GUI.