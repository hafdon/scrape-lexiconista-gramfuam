import tkinter as tk
from tkinter import filedialog, messagebox
import requests
import urllib.parse
import pygame
import os
import io
import random  # Import the random module for shuffling

class AudioQuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Quiz App")

        self.url_list = []
        self.current_index = 0
        self.correct_text = ""

        self.selected_dialect = tk.StringVar(value='CanM')  # Default dialect is CanM

        # Initialize Pygame mixer for audio playback
        pygame.mixer.init()

        # Create GUI elements
        self.create_widgets()

    def create_widgets(self):
        # Dialect Selection
        dialect_frame = tk.LabelFrame(self.root, text="Select Dialect")
        dialect_frame.pack(pady=10)

        dialects = [("Munster (CanM)", "CanM"), ("Ulster (CanU)", "CanU"), ("Connacht (CanC)", "CanC")]
        for text, value in dialects:
            radio = tk.Radiobutton(dialect_frame, text=text, variable=self.selected_dialect, value=value)
            radio.pack(anchor=tk.W)

        # Open File Button
        self.open_button = tk.Button(self.root, text="Open URL File", command=self.open_file)
        self.open_button.pack(pady=10)

        # Play Button
        self.play_button = tk.Button(self.root, text="Play Audio", command=self.play_audio, state=tk.DISABLED)
        self.play_button.pack(pady=10)

        # Entry for user's guess
        self.guess_entry = tk.Entry(self.root, width=50)
        self.guess_entry.pack(pady=10)

        # Check Answer Button
        self.check_button = tk.Button(self.root, text="Check Answer", command=self.check_answer, state=tk.DISABLED)
        self.check_button.pack(pady=10)

        # Label to display the result
        self.result_label = tk.Label(self.root, text="")
        self.result_label.pack(pady=10)

        # Next Button
        self.next_button = tk.Button(self.root, text="Next", command=self.next_audio, state=tk.DISABLED)
        self.next_button.pack(pady=10)

    def open_file(self):
        # Open a file dialog to select the URL file
        file_path = filedialog.askopenfilename(title="Select URL File", filetypes=[("Text Files", "*.txt")])
        if file_path:
            # Read the URLs from the file
            with open(file_path, 'r', encoding='utf-8') as file:
                all_urls = [line.strip() for line in file if line.strip()]
            if all_urls:
                # Filter URLs based on selected dialect
                dialect_code = self.selected_dialect.get()
                self.url_list = [url for url in all_urls if f'/{dialect_code}-verb/' in url]

                if not self.url_list:
                    messagebox.showerror("Error", f"No URLs found for the selected dialect '{dialect_code}'.")
                    return

                # Shuffle the URL list
                random.shuffle(self.url_list)

                self.current_index = 0
                self.play_button.config(state=tk.NORMAL)
                self.check_button.config(state=tk.NORMAL)
                self.next_button.config(state=tk.DISABLED)
                self.result_label.config(text="")
                self.guess_entry.delete(0, tk.END)
                messagebox.showinfo("File Loaded", f"Loaded {len(self.url_list)} URLs for dialect '{dialect_code}'.")
            else:
                messagebox.showerror("Error", "The file is empty.")
        else:
            messagebox.showwarning("No File Selected", "Please select a URL file.")

    def play_audio(self):
        if self.current_index < len(self.url_list):
            url = self.url_list[self.current_index]
            self.correct_text = self.extract_text_from_url(url)
            try:
                # Download the audio content
                response = requests.get(url)
                response.raise_for_status()
                audio_data = io.BytesIO(response.content)

                # Stop any currently playing audio
                pygame.mixer.music.stop()

                # Load the audio data into Pygame mixer
                with open("temp_audio.mp3", "wb") as f:
                    f.write(audio_data.getbuffer())
                pygame.mixer.music.load("temp_audio.mp3")
                pygame.mixer.music.play()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to play audio: {e}")
        else:
            messagebox.showinfo("End of Quiz", "You have reached the end of the quiz.")
            self.play_button.config(state=tk.DISABLED)
            self.check_button.config(state=tk.DISABLED)

    def extract_text_from_url(self, url):
        # Extract the text from the URL
        filename = url.split('/')[-1]
        text_encoded = filename.replace('.mp3', '')
        text = urllib.parse.unquote(text_encoded)
        return text

    def check_answer(self):
        user_guess = self.guess_entry.get().strip()
        if user_guess:
            if user_guess.lower() == self.correct_text.lower():
                result = "Correct!"
            else:
                result = f"Incorrect! The correct text is:\n'{self.correct_text}'"
            self.result_label.config(text=result)
            self.next_button.config(state=tk.NORMAL)
            self.check_button.config(state=tk.DISABLED)
        else:
            messagebox.showwarning("Input Required", "Please enter your guess.")

    def next_audio(self):
        # Move to the next audio
        self.current_index += 1
        self.guess_entry.delete(0, tk.END)
        self.result_label.config(text="")
        self.next_button.config(state=tk.DISABLED)
        self.check_button.config(state=tk.NORMAL)
        self.play_audio()

    def on_closing(self):
        # Clean up temporary files and quit the app
        pygame.mixer.music.stop()
        if os.path.exists("temp_audio.mp3"):
            os.remove("temp_audio.mp3")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioQuizApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
