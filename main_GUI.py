import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import subprocess
import cv2
import numpy as np
import threading
from time import sleep

CALIBRATION_SCRIPT_PATH = r"C:\Users\Paavo Meri\Documents\GitHub\Kesaprojektit-24---Machine-vision-for-robotic-arm\calibrationV2.py"
MAIN_SCRIPT_PATH = r"C:\Users\Paavo Meri\Documents\GitHub\Kesaprojektit-24---Machine-vision-for-robotic-arm\mainV2.py"

class LiveFeed:
    def __init__(self, label):
        self.label = label
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # Reduced resolution
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)  # Reduced resolution
        self.cap.set(cv2.CAP_PROP_FPS, 15)  # Adjusted FPS for better performance
        self.running = True
        if self.cap.isOpened():
            self.aspect_ratio = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) / self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        else:
            self.aspect_ratio = 16 / 9  # Default aspect ratio if camera fails to open
        self.thread = threading.Thread(target=self.update_frame)
        self.thread.daemon = True
        self.thread.start()

    def start(self):
        if not self.running:
            self.running = True
            self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # Reduced resolution
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)  # Reduced resolution
            self.cap.set(cv2.CAP_PROP_FPS, 15)  # Adjusted FPS for better performance
            if self.cap.isOpened():
                self.aspect_ratio = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) / self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            else:
                self.aspect_ratio = 16 / 9  # Default aspect ratio if camera fails to open
            self.thread = threading.Thread(target=self.update_frame)
            self.thread.daemon = True
            self.thread.start()

    def update_frame(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(image_rgb)

                # Maintain aspect ratio
                window_width = app.winfo_width()
                window_height = int(window_width / self.aspect_ratio)
                
                if window_height > app.winfo_height():
                    window_height = app.winfo_height()
                    window_width = int(window_height * self.aspect_ratio)

                pil_image = pil_image.resize((window_width, window_height), Image.LANCZOS)
                tk_image = ImageTk.PhotoImage(pil_image)

                # Update the GUI on the main thread
                self.label.after(0, self.update_gui, tk_image)
            else:
                sleep(0.03)

    def update_gui(self, tk_image):
        self.label.config(image=tk_image)
        self.label.image = tk_image

    def stop(self):
        self.running = False
        self.cap.release()

def run_calibration_script():
    live_feed.stop()
    try:
        result = subprocess.run(["python", CALIBRATION_SCRIPT_PATH], check=True)
        if result.returncode == 0:
            messagebox.showinfo("Success", "Calibration script executed successfully.")
        else:
            messagebox.showerror("Error", "Calibration script failed.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    live_feed.start()

def run_main_script():
    live_feed.stop()
    try:
        blue_count = int(blue_spinbox.get())
        green_count = int(green_spinbox.get())
        yellow_count = int(yellow_spinbox.get())
        pink_count = int(pink_spinbox.get())
        orange_count = int(orange_spinbox.get())
        purple_count = int(purple_spinbox.get())
    except ValueError:
        messagebox.showerror("Invalid input", "Please enter valid numbers.")
        live_feed.start()
        return

    def process_and_run_script():
        try:
            result = subprocess.run([
                "python", MAIN_SCRIPT_PATH, 
                str(blue_count), str(green_count), str(yellow_count), 
                str(pink_count), str(orange_count), str(purple_count)
            ], check=True)
            if result.returncode == 0:
                messagebox.showinfo("Success", "Main script executed successfully.")
            else:
                messagebox.showerror("Error", "Main script failed.")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
        finally:
            # Reset the spinbox values to 0
            blue_spinbox.delete(0, tk.END)
            blue_spinbox.insert(0, '0')
            green_spinbox.delete(0, tk.END)
            green_spinbox.insert(0, '0')
            yellow_spinbox.delete(0, tk.END)
            yellow_spinbox.insert(0, '0')
            pink_spinbox.delete(0, tk.END)
            pink_spinbox.insert(0, '0')
            orange_spinbox.delete(0, tk.END)
            orange_spinbox.insert(0, '0')
            purple_spinbox.delete(0, tk.END)
            purple_spinbox.insert(0, '0')
            live_feed.start()

    # Run the script in a separate thread to avoid blocking the GUI
    threading.Thread(target=process_and_run_script).start()

def validate_input(value_if_allowed, text):
    if text.isdigit() and int(text) >= 0:
        return True
    elif text == "":
        return True
    else:
        return False

app = tk.Tk()
app.title("Pick and Place Robot Controller")
app.geometry("1280x720")  # Ensure the app has an initial size
app.update()  # Force the geometry manager to calculate the window size

# Controls on the left side
control_frame = tk.Frame(app)
control_frame.pack(side="left", fill="y", padx=10, pady=10)

calibration_button = tk.Button(control_frame, text="Run Calibration Script", command=run_calibration_script)
calibration_button.pack(pady=10)

tk.Label(control_frame, text="Enter count for each color:").pack(pady=5)

vcmd = (app.register(validate_input), '%P', '%S')

tk.Label(control_frame, text="Blue:").pack()
blue_spinbox = tk.Spinbox(control_frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
blue_spinbox.pack()

tk.Label(control_frame, text="Green:").pack()
green_spinbox = tk.Spinbox(control_frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
green_spinbox.pack()

tk.Label(control_frame, text="Yellow:").pack()
yellow_spinbox = tk.Spinbox(control_frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
yellow_spinbox.pack()

tk.Label(control_frame, text="Pink:").pack()
pink_spinbox = tk.Spinbox(control_frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
pink_spinbox.pack()

tk.Label(control_frame, text="Orange:").pack()
orange_spinbox = tk.Spinbox(control_frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
orange_spinbox.pack()

tk.Label(control_frame, text="Purple:").pack()
purple_spinbox = tk.Spinbox(control_frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
purple_spinbox.pack()

main_button = tk.Button(control_frame, text="Run Main Script", command=run_main_script)
main_button.pack(pady=10)

# Image on the right side
image_label = tk.Label(app)
image_label.pack(side="right", fill=tk.BOTH, expand=True, padx=10, pady=10)

live_feed = LiveFeed(image_label)

app.mainloop()