import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import subprocess
import cv2
import numpy as np
from time import sleep
import threading

# Aseta kalibrointi- ja pääskriptien polut
CALIBRATION_SCRIPT_PATH = r"C:\Users\Paavo Meri\Desktop\Projekti\Projekti\calibrationV2.py"
MAIN_SCRIPT_PATH = r"C:\Users\Paavo Meri\Desktop\Projekti\Projekti\mainV2.py"

# Define color ranges in HSV
color_ranges_hsv = {
    #Pink wraps around the hsv colorspace so it needs 2 ranges
    "pink1": (np.array([0, 45, 65]), np.array([4, 175, 185])),
    "pink2": (np.array([172, 45, 65]), np.array([180, 175, 185])),

    "orange": (np.array([8, 50, 175]), np.array([15, 190, 205])),
    "purple": (np.array([145, 35, 35]), np.array([165, 140, 75])),
    "green": (np.array([50, 40, 40]), np.array([90, 255, 255])),
    "blue": (np.array([100, 100, 100]), np.array([130, 255, 255])),
    "yellow": (np.array([27, 135, 130]), np.array([35, 200, 180])),
}

# Kernel for morphological operations
kernel = np.ones((3, 3), np.uint8)

def process_image():
    # Initialize the webcam
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    # Set desired resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)

    sleep(0.1)
    if not cap.isOpened():
        print("Error: Could not open video device.")
        return None

    # Capture a single frame
    ret, frame = cap.read()
    #cap.release()

    if not ret:
        print("Error: Could not read frame.")
        return None

    # Get image dimensions
    height, width, _ = frame.shape
    
    crop_top = 0 
    crop_bottom = height - 0
    crop_left = 1250  # Remove 1250 pixels from the left
    crop_right = width - 0 
             
    # Crop the image
    cropped_frame = frame[crop_top:crop_bottom, crop_left:crop_right]
    
    # Convert to HSV
    hsv = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2HSV)

    # Process pink color
    process_pink_color(hsv, cropped_frame)

    # Process other colors
    for color, (lower, upper) in color_ranges_hsv.items():
        if "pink" in color:
            continue  # Skip pink as it is already processed
        
        # Create a mask for the current color
        mask = cv2.inRange(hsv, lower, upper)
        
        # Apply Gaussian blur to the mask to reduce noise
        mask = cv2.GaussianBlur(mask, (15, 15), 0)

        # Apply morphological operations to remove small noise and fill gaps
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            # Calculate contour area and ignore small areas
            area = cv2.contourArea(contour)
            if area > 500:  # Adjust this threshold as needed
                # Get the minimum area rectangle
                rect = cv2.minAreaRect(contour)
                box = cv2.boxPoints(rect)
                box = np.intp(box)
                
                # Calculate width and height of the rectangle
                width = rect[1][0]
                height = rect[1][1]
                
                # Calculate aspect ratio
                aspect_ratio = float(width) / height if width > height else float(height) / width
                
                # Define minimum and maximum size thresholds
                min_size = 100  # Adjust this minimum size threshold as needed
                max_size = 999  # Adjust this maximum size threshold as needed
                
                # Filter based on aspect ratio and size
                if 0.8 < aspect_ratio < 1.2 and min_size < width < max_size and min_size < height < max_size:
                    # Draw the rotated bounding box
                    cv2.drawContours(cropped_frame, [box], 0, (0, 255, 0), 5)
                    
                    # Calculate the center of the bounding box
                    center_x = int(rect[0][0])
                    center_y = int(rect[0][1])
                    
                    # Draw the center point
                    cv2.circle(cropped_frame, (center_x, center_y), 3, (0, 0, 255), -1)
                    
                    # Print the coordinates with the color label
                    print(f"{color.capitalize()} center coordinates: ({center_x}, {center_y})")
                    
                    # Put the color label next to the bounding box
                    cv2.putText(cropped_frame, color, (center_x + 10, center_y), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3)

        # Resize the image to fit your screen dimensions or a fixed size
        screen_res = 640, 360  # You can adjust this to your screen resolution
        scale_width = screen_res[0] / cropped_frame.shape[1]
        scale_height = screen_res[1] / cropped_frame.shape[0]
        scale = min(scale_width, scale_height)
        window_width = int(cropped_frame.shape[1] * scale)
        window_height = int(cropped_frame.shape[0] * scale)
        resized_frame = cv2.resize(cropped_frame, (window_width, window_height))

    # Display the image with contours
    cv2.imshow('Detected Contours', resized_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# Same as the process_image function but for pink
def process_pink_color(hsv, cropped_frame):
    # Combine masks for pink
    pink_mask = cv2.inRange(hsv, color_ranges_hsv["pink1"][0], color_ranges_hsv["pink1"][1]) | \
                cv2.inRange(hsv, color_ranges_hsv["pink2"][0], color_ranges_hsv["pink2"][1])
    
    pink_mask = cv2.GaussianBlur(pink_mask, (15, 15), 0)

    pink_mask = cv2.morphologyEx(pink_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    pink_mask = cv2.morphologyEx(pink_mask, cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = cv2.findContours(pink_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        # Calculate contour area and ignore small areas
        area = cv2.contourArea(contour)
        if area > 500:  # Adjust this threshold as needed
            # Get the minimum area rectangle
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            box = np.intp(box)
            
            # Calculate width and height of the rectangle
            width = rect[1][0]
            height = rect[1][1]
            
            # Calculate aspect ratio
            aspect_ratio = float(width) / height if width > height else float(height) / width
            
            # Define minimum and maximum size thresholds
            min_size = 100  # Adjust this minimum size threshold as needed
            max_size = 999  # Adjust this maximum size threshold as needed
            
            # Filter based on aspect ratio and size
            if 0.8 < aspect_ratio < 1.2 and min_size < width < max_size and min_size < height < max_size:
                # Draw the rotated bounding box
                cv2.drawContours(cropped_frame, [box], 0, (0, 255, 0), 5)
                
                # Calculate the center of the bounding box
                center_x = int(rect[0][0])
                center_y = int(rect[0][1])
                
                # Draw the center point
                cv2.circle(cropped_frame, (center_x, center_y), 3, (0, 0, 255), -1)
                
                # Print the coordinates with the color label
                print(f"Pink center coordinates: ({center_x}, {center_y})")
                
                # Put the color label next to the bounding box
                cv2.putText(cropped_frame, "pink", (center_x + 10, center_y), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3)

def run_calibration_script():
    try:
        result = subprocess.run(["python", CALIBRATION_SCRIPT_PATH], check=True)
        if result.returncode == 0:
            messagebox.showinfo("Success", "Calibration script executed successfully.")
        else:
            messagebox.showerror("Error", "Calibration script failed.")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

def run_main_script():
    try:
        blue_count = int(blue_spinbox.get())
        green_count = int(green_spinbox.get())
        yellow_count = int(yellow_spinbox.get())
        pink_count = int(pink_spinbox.get())
        orange_count = int(orange_spinbox.get())
        purple_count = int(purple_spinbox.get())
    except ValueError:
        messagebox.showerror("Invalid input", "Please enter valid numbers.")
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
app.geometry("1280x720")

frame = tk.Frame(app)
frame.pack(pady=20)

calibration_button = tk.Button(frame, text="Run Calibration Script", command=run_calibration_script)
calibration_button.pack(pady=10)

get_image_button = tk.Button(frame, text="Get Image", command=process_image)
get_image_button.pack(pady=10)

tk.Label(frame, text="Enter count for each color:").pack(pady=5)

vcmd = (app.register(validate_input), '%P', '%S')

tk.Label(frame, text="Blue:").pack()
blue_spinbox = tk.Spinbox(frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
blue_spinbox.pack()

tk.Label(frame, text="Green:").pack()
green_spinbox = tk.Spinbox(frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
green_spinbox.pack()

tk.Label(frame, text="Yellow:").pack()
yellow_spinbox = tk.Spinbox(frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
yellow_spinbox.pack()

tk.Label(frame, text="Pink:").pack()
pink_spinbox = tk.Spinbox(frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
pink_spinbox.pack()

tk.Label(frame, text="Orange:").pack()
orange_spinbox = tk.Spinbox(frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
orange_spinbox.pack()

tk.Label(frame, text="Purple:").pack()
purple_spinbox = tk.Spinbox(frame, from_=0, to=100, increment=1, validate='key', validatecommand=vcmd)
purple_spinbox.pack()

main_button = tk.Button(frame, text="Run Main Script", command=run_main_script)
main_button.pack(pady=10)

image_label = tk.Label(frame)
image_label.pack(pady=10)

app.mainloop()
