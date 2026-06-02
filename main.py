"""
main.py — Entry point for NW Airtrace.

Run:  python main.py
Packages required: pip install pillow opencv-python-headless numpy
"""

import tkinter as tk
from tkinter import messagebox
import traceback

from app import ShapePlotter  # imports the root application class

if __name__ == "__main__":
    try:
        app = ShapePlotter()   # creates the Tk root window and builds all UI
        app.mainloop()         # starts the Tkinter event loop; blocks until window closes
    except Exception as e:
        try:
            messagebox.showerror(
                "Fatal Error",
                f"An unexpected error occurred:\n\n{e}\n\n" + traceback.format_exc()
            )  # shows a GUI error dialog if the app crashes at the top level
        except Exception:
            print("FATAL:", traceback.format_exc())  # last-resort console fallback if Tk itself failed
