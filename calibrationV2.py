import threading
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove, MyType, alarmAlarmJsonFile # type: ignore
from time import sleep
import numpy as np
import re
import cv2
import os
import tkinter as tk
from tkinter import messagebox

current_actual = None
algorithm_queue = None
enableStatus_robot = None
robotErrorState = False
globalLockValue = threading.Lock()
kernel = np.ones((3, 3), np.uint8)

# Predefined points
robot_points = [
    [32.48, -237.79, -166, 0], 
    [111.85, -212.34, -166, 0], 
    [177.73, -161.28, -166, 0], 
    [58.61, -258.44, -166, 0], 
    [143.47, -222.80, -166, 0], 
    [211.02, -160.30, -166, 0], 
    [88.55, -276.15, -166, 0], 
    [177.66, -229.21, -166, 0], 
    [245.34, -154.63, -166, 0], 
    [121.96, -290.43, -166, 0], 
    [213.94, -231.21, -166, 0], 
    [46.02, -336.87, -166, 0], 
    [158.46, -300.82, -166, 0], 
    [251.79, -228.48, -166, 0], 
    [80.73, -355.96, -166, 0], 
    [197.61, -306.88, -166, 0], 
    [290.65, -220.79, -166, 0], 
    [119.08, -371.38, -166, 0], 
    [238.92, -308.25, -166, 0], 
    [346.80, -178.40, -166, 0]
]

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

def show_confirmation_popup():
    root = tk.Tk()
    root.withdraw()
    messagebox.showinfo("Confirmation", "Please confirm that the tile is in position and press OK to continue.")
    root.destroy()

def ConnectRobot():
    try:
        ip = "192.168.1.6"
        dashboardPort = 29999
        movePort = 30003
        feedPort = 30004
        print("Connection being established.")
        dashboard = DobotApiDashboard(ip, dashboardPort)
        move = DobotApiMove(ip, movePort)
        feed = DobotApi(ip, feedPort)
        print("Connection successful.")
        return dashboard, move, feed
    except Exception as e:
        print(":(Connection failed:(")
        raise e

def RunPoint(move: DobotApiMove, point_list: list):
    move.MovL(point_list[0], point_list[1], point_list[2], point_list[3])

def SuctionCup(dashboard: DobotApiDashboard, PORT, STATUS):
    dashboard.DO(PORT, STATUS)

def GetFeed(feed: DobotApi):
    global current_actual
    global algorithm_queue
    global enableStatus_robot
    global robotErrorState
    hasRead = 0
    while True:
        data = bytes()
        while hasRead < 1440:
            temp = feed.socket_dobot.recv(1440 - hasRead)
            if len(temp) > 0:
                hasRead += len(temp)
                data += temp
        hasRead = 0
        feedInfo = np.frombuffer(data, dtype=MyType)
        if hex((feedInfo['test_value'][0])) == '0x123456789abcdef':
            globalLockValue.acquire()
            # Refresh Properties
            current_actual = feedInfo["tool_vector_actual"][0]
            algorithm_queue = feedInfo['isRunQueuedCmd'][0]
            enableStatus_robot = feedInfo['EnableStatus'][0]
            robotErrorState = feedInfo['ErrorStatus'][0]
            globalLockValue.release()
        sleep(0.001)

def WaitArrive(point_list):
    while True:
        is_arrive = True
        globalLockValue.acquire()
        if current_actual is not None:
            for index in range(4):
                if abs(current_actual[index] - point_list[index]) > 1:
                    is_arrive = False
            if is_arrive:
                globalLockValue.release()
                return
        globalLockValue.release()
        sleep(0.001)

def ClearRobotError(dashboard: DobotApiDashboard):
    global robotErrorState
    dataController, dataServo = alarmAlarmJsonFile()
    while True:
        globalLockValue.acquire()
        if robotErrorState:
            numbers = re.findall(r'-?\d+', dashboard.GetErrorID())
            numbers = [int(num) for num in numbers]
            if numbers[0] == 0:
                if len(numbers) > 1:
                    for i in numbers[1:]:
                        alarmState = False
                        if i == -2:
                            print("Machine alarms Machine collisions ", i)
                            alarmState = True
                        if alarmState:
                            continue                
                        for item in dataController:
                            if i == item["id"]:
                                print("machine alarm Controller errorid", i, item["zh_CN"]["description"])
                                alarmState = True
                                break 
                        if alarmState:
                            continue
                        for item in dataServo:
                            if i == item["id"]:
                                print("machine alarm Servo errorid", i, item["zh_CN"]["description"])
                                break  
                    choose = input("Entering 1 will clear the error and the machine will continue to run. ")     
                    if int(choose) == 1:
                        dashboard.ClearError()
                        sleep(0.01)
                        dashboard.Continue()
        else:  
            if int(enableStatus_robot[0]) == 1 and int(algorithm_queue[0]) == 0:
                dashboard.Continue()
        globalLockValue.release()
        sleep(5)

def process_image():
    # Initialize the webcam
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)

    # Set desired resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)

    sleep(1)
    if not cap.isOpened():
        print("Error: Could not open video device.")
        return None

    # Capture a single frame
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Error: Could not read frame.")
        return None
    detected_points = []
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
                    # Append the detected point to the list
                    detected_points.append((center_x, center_y))
        # Resize the image to fit your screen dimensions or a fixed size
        screen_res = 1280, 720  # You can adjust this to your screen resolution
        scale_width = screen_res[0] / cropped_frame.shape[1]
        scale_height = screen_res[1] / cropped_frame.shape[0]
        scale = min(scale_width, scale_height)
        window_width = int(cropped_frame.shape[1] * scale)
        window_height = int(cropped_frame.shape[0] * scale)
        resized_frame = cv2.resize(cropped_frame, (window_width, window_height))

    # Create a named window
    window_name = 'Detected Contours'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    # Set the window to be on top
    cv2.setWindowProperty(window_name, cv2.WND_PROP_TOPMOST, 1)
    
    # Display the image with contours
    cv2.imshow(window_name, resized_frame)
    cv2.waitKey(500)
    cv2.destroyAllWindows()

    print(f"Number of detected points: {len(detected_points)}")
    return detected_points if detected_points else None

#Same as the process_image function but for pink
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

def calculate_transformation_matrix(pixel_points, robot_points):
    # Ensure the points are in homogeneous coordinates for a 3x2 matrix calculation
    pixel_points_h = np.hstack((pixel_points, np.ones((pixel_points.shape[0], 1))))
    
    # Perform the least squares calculation to find the best fit transformation matrix
    transformation_matrix, _, _, _ = np.linalg.lstsq(pixel_points_h, robot_points[:, :2], rcond=None)

    # Format the matrix into the correct form
    transformation_matrix = np.vstack([transformation_matrix.T, [0, 0, 1]])
    
    return transformation_matrix

if __name__ == '__main__':
    dashboard, move, feed = ConnectRobot()
    print("Enabling...")
    dashboard.EnableRobot()
    print("Enabled:)")
    feed_thread = threading.Thread(target=GetFeed, args=(feed,))
    feed_thread.setDaemon(True)
    feed_thread.start()
    feed_thread1 = threading.Thread(target=ClearRobotError, args=(dashboard,))
    feed_thread1.setDaemon(True)
    feed_thread1.start()
    print("Loop")

    start_point = [300, 0, -100, 0]
    pickup_point = [300, 0, -165, 0]
    intermediate_point = pickup_point.copy()
    intermediate_point[2] = -100
    safe_position = start_point

    x_offset = 0
    y_offset = 0

    pixel_points = []
    
    for i, robot_point in enumerate(robot_points):
        if i == 0:
            current_pickup_point = pickup_point.copy()
            # Apply offsets for initial pickup
            current_pickup_point[0] += x_offset
            current_pickup_point[1] += y_offset
            # Move to 5mm above the pickup location
            above_pickup_point = current_pickup_point.copy()
            above_pickup_point[2] += 5
            RunPoint(move, above_pickup_point)
            WaitArrive(above_pickup_point)

            # Show confirmation popup
            show_confirmation_popup()
        else:
            current_pickup_point = robot_points[i - 1].copy()
            # Apply offsets for subsequent pickups
            current_pickup_point[0] += x_offset
            current_pickup_point[1] += y_offset

        RunPoint(move, start_point)
        WaitArrive(start_point)

        intermediate_pickup_point = current_pickup_point.copy()
        intermediate_pickup_point[2] = -100
        RunPoint(move, intermediate_pickup_point)
        WaitArrive(intermediate_pickup_point)

        # Move to the adjusted pickup location
        RunPoint(move, current_pickup_point)
        WaitArrive(current_pickup_point)

        SuctionCup(dashboard, 1, 1)
        sleep(0.3)

        RunPoint(move, intermediate_pickup_point)
        WaitArrive(intermediate_pickup_point)

        intermediate_robot_point = robot_point.copy()
        intermediate_robot_point[2] = -100
        RunPoint(move, intermediate_robot_point)
        WaitArrive(intermediate_robot_point)

        RunPoint(move, robot_point)
        WaitArrive(robot_point)

        SuctionCup(dashboard, 1, 0)
        SuctionCup(dashboard, 2, 1)
        sleep(0.2)
        SuctionCup(dashboard, 2, 0)

        intermediate_after_place_point = robot_point.copy()
        intermediate_after_place_point[2] = -100
        RunPoint(move, intermediate_after_place_point)
        WaitArrive(intermediate_after_place_point)

        RunPoint(move, safe_position)
        WaitArrive(safe_position)

        detected_points = process_image()
        if detected_points:
            # Assuming only one point is detected per iteration
            pixel_points.append(detected_points[0])

        RunPoint(move, start_point)
        WaitArrive(start_point)

    print(f"Number of robot points: {len(robot_points)}")
    print(f"Number of pixel points: {len(pixel_points)}")
    print(f"Pixel coordinates list: {pixel_points}")

    if len(pixel_points) == len(robot_points):
        transformation_matrix = calculate_transformation_matrix(np.array(pixel_points), np.array(robot_points))
        
        # Transpose the transformation matrix
        transformation_matrix = transformation_matrix.T

        # Save the transposed transformation matrix to a file
        np.savetxt('transformation_matrix.txt', transformation_matrix)

        print("Transposed Transformation Matrix:")
        print(transformation_matrix)
    else:
        print("Error: The number of detected pixel points does not match the number of robot points.")