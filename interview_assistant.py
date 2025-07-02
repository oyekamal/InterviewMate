import tkinter as tk
from tkinter import scrolledtext, messagebox
import speech_recognition as sr
import pyaudio # Though not directly used if sr handles mic, good to have for potential direct use
import google.generativeai as genai
import threading
import os

# --- Configuration ---
# IMPORTANT: User needs to configure their Gemini API Key
# Option 1: Set an environment variable named GEMINI_API_KEY
# Option 2: Directly paste the key here (less secure)
# GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    # Attempt to read from a .env file if it exists, for convenience
    try:
        with open(".env", "r") as f:
            for line in f:
                if line.strip().startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.strip().split("=")[1]
                    break
    except FileNotFoundError:
        pass # .env file not found, that's fine

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("GEMINI_API_KEY not found in environment variables or .env file.")
    # Optionally, show a GUI error here or exit, as Gemini functionality will fail.
    # For now, we'll let it proceed and fail when Gemini is called.

# Global variable to hold the recognizer and microphone instance
r = sr.Recognizer()
mic = sr.Microphone()
is_listening = False
listening_thread = None

# --- STT Functionality ---
def toggle_listening():
    global is_listening, listening_thread
    if not GEMINI_API_KEY:
        messagebox.showerror("API Key Error", "Gemini API Key not configured. Please set the GEMINI_API_KEY environment variable.")
        return

    if is_listening:
        is_listening = False
        if listening_thread:
            # We can't forcefully stop a thread easily,
            # but STT library might offer a way or it will stop on next audio chunk processing.
            # For speech_recognition, stopping is managed by its internal listening loop ending.
            listen_button.config(text="Start Listening")
            status_label.config(text="Status: Not Listening")
        print("Stopped listening.")
    else:
        is_listening = True
        listen_button.config(text="Stop Listening")
        status_label.config(text="Status: Listening...")
        transcribed_text_area.delete(1.0, tk.END) # Clear previous transcription
        gemini_suggestions_area.delete(1.0, tk.END) # Clear previous suggestions
        # Start listening in a new thread to avoid freezing the GUI
        listening_thread = threading.Thread(target=listen_for_audio, daemon=True)
        listening_thread.start()
        print("Started listening.")

def listen_for_audio():
    global is_listening
    # Adjust recognizer settings if needed
    r.pause_threshold = 0.8  # seconds of non-speaking audio before a phrase is considered complete
    r.energy_threshold = 300 # minimum audio energy to consider for recording

    while is_listening:
        print("Microphone check: Attempting to listen...")
        try:
            with mic as source:
                # r.adjust_for_ambient_noise(source, duration=0.5) # Adjust for noise (optional, can add latency)
                status_label.config(text="Status: Listening...")
                app.update_idletasks() # Update UI
                try:
                    audio = r.listen(source, timeout=5, phrase_time_limit=10) # Listen for up to 5s, phrase up to 10s
                except sr.WaitTimeoutError:
                    print("No speech detected in the last 5 seconds.")
                    if not is_listening: # Check if stopped while waiting
                        break
                    continue # Continue listening

            if not is_listening: # Check if stopped while processing
                break

            status_label.config(text="Status: Recognizing...")
            app.update_idletasks()
            try:
                text = r.recognize_google(audio) # Using Google Web Speech API
                print(f"Transcribed: {text}")
                transcribed_text_area.insert(tk.END, text + "\n")
                transcribed_text_area.see(tk.END) # Scroll to the end
            except sr.UnknownValueError:
                print("Google Web Speech API could not understand audio")
                # transcribed_text_area.insert(tk.END, "[Could not understand audio]\n")
            except sr.RequestError as e:
                print(f"Could not request results from Google Web Speech API; {e}")
                transcribed_text_area.insert(tk.END, f"[API Request Error: {e}]\n")
            finally:
                if is_listening: # If still listening, briefly show listening status
                    status_label.config(text="Status: Listening...")
                else:
                    status_label.config(text="Status: Not Listening")
                app.update_idletasks()

        except Exception as e:
            print(f"An error occurred with the microphone or STT: {e}")
            # transcribed_text_area.insert(tk.END, f"[Mic/STT Error: {e}]\n")
            status_label.config(text="Status: Error in STT. Retrying...")
            app.update_idletasks()
            if not is_listening:
                break
            threading.Event().wait(1) # Wait a bit before retrying

    status_label.config(text="Status: Not Listening")
    listen_button.config(text="Start Listening")
    is_listening = False # Ensure state is correct
    print("Listening loop ended.")


# --- Gemini Functionality ---
def get_gemini_suggestion():
    if not GEMINI_API_KEY:
        messagebox.showerror("API Key Error", "Gemini API Key not configured. Please set the GEMINI_API_KEY environment variable.")
        return

    current_text = transcribed_text_area.get(1.0, tk.END).strip()
    if not current_text:
        messagebox.showinfo("No Text", "No transcribed text to send to Gemini.")
        return

    gemini_suggestions_area.delete(1.0, tk.END)
    gemini_suggestions_area.insert(tk.END, "Getting suggestions from Gemini...\n")
    app.update_idletasks()

    # Show loading status
    status_label.config(text="Status: Getting Gemini suggestion...")
    app.update_idletasks()

    try:
        # For text-only input
        model = genai.GenerativeModel('gemini-pro') # Or other suitable model

        # Simple prompt, can be made more sophisticated
        prompt = f"I am in an interview. Here is the recent conversation or question directed at me: \"{current_text}\". Please provide concise talking points or a suggested response for me."

        response = model.generate_content(prompt)

        gemini_suggestions_area.delete(1.0, tk.END)
        gemini_suggestions_area.insert(tk.END, response.text + "\n")
        print("Gemini Response:", response.text)

    except Exception as e:
        gemini_suggestions_area.delete(1.0, tk.END)
        gemini_suggestions_area.insert(tk.END, f"Error from Gemini: {e}\n")
        print(f"Error calling Gemini API: {e}")
    finally:
        status_label.config(text="Status: Idle" if not is_listening else "Status: Listening...")
        app.update_idletasks()


# --- GUI Setup ---
app = tk.Tk()
app.title("Interview Assistant MVP")
app.geometry("600x500") # Adjusted size for better layout

# Make the window always on top
app.attributes('-topmost', True)

# Frame for controls
control_frame = tk.Frame(app)
control_frame.pack(pady=10)

listen_button = tk.Button(control_frame, text="Start Listening", command=toggle_listening)
listen_button.pack(side=tk.LEFT, padx=5)

gemini_button = tk.Button(control_frame, text="Get Gemini Suggestion", command=get_gemini_suggestion)
gemini_button.pack(side=tk.LEFT, padx=5)

status_label = tk.Label(app, text="Status: Not Listening")
status_label.pack(pady=5)

# Transcribed Text Area
trans_frame = tk.LabelFrame(app, text="Transcribed Interview Text")
trans_frame.pack(padx=10, pady=5, fill="x")
transcribed_text_area = scrolledtext.ScrolledText(trans_frame, wrap=tk.WORD, height=10)
transcribed_text_area.pack(padx=5, pady=5, fill="x", expand=True)

# Gemini Suggestions Area
gemini_frame = tk.LabelFrame(app, text="Gemini Suggestions")
gemini_frame.pack(padx=10, pady=5, fill="both", expand=True)
gemini_suggestions_area = scrolledtext.ScrolledText(gemini_frame, wrap=tk.WORD, height=10)
gemini_suggestions_area.pack(padx=5, pady=5, fill="both", expand=True)


def on_closing():
    global is_listening
    print("Closing application...")
    if is_listening:
        is_listening = False # Signal listening thread to stop
        if listening_thread and listening_thread.is_alive():
            print("Waiting for listening thread to finish...")
            listening_thread.join(timeout=2) # Wait for the thread to finish
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_closing)

if __name__ == "__main__":
    if not GEMINI_API_KEY:
        messagebox.showwarning("API Key Missing",
                               "GEMINI_API_KEY is not set. Please set it as an environment variable "
                               "or in a .env file (e.g., GEMINI_API_KEY=YOUR_KEY).\n\n"
                               "The application will run, but Gemini features will not work.")
    app.mainloop()
