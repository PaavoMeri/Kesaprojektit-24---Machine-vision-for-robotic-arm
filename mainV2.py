import threading
from dobot_api import DobotApiDashboard, DobotApi, DobotApiMove, MyType, alarmAlarmJsonFile # type: ignore
from time import sleep
import numpy as np
import re
import cv2
import sys
import tkinter as tk
from tkinter import messagebox

current_actual = None
algorithm_queue = None
enableStatus_robot = None
robotErrorState = False
globalLockValue = threading.Lock()

# Define color ranges in HSV
color_ranges_hsv = {
    #Pink wraps around the hsv colorspace so it needs 2 ranges
    "pink1": (np.array([0, 45, 65]), np.array([4, 175, 185])),
    "pink2": (np.array([172, 45, 65]), np.array([180, 175, 185])),

    "orange": (np.array([8, 50, 175]), np.array([15, 190, 205])),
    "purple": (np.array([145, 35, 35]), np.array([165, 140, 75])),
    "green": (np.array([50, 40, 40]), np.array([90, 255, 255])),
    "blue": (np.array([100, 100, 100]), np.array([130, 255, 255])),
    "yellow": (np.array([27, 135, 130]), np.array([36, 200, 200])),
}

# CHANGE PLACE LOCATIONS
PLACE_LOCATIONS = {
    'blue': [-345, -190, -20],
    'green': [-338, -270, -20],
    
    'yellow': [-266, -316, -20],
    'pink': [-271, -235, -20],

    'orange': [-280, -152, -20],
    'purple': [-271, -235, -20]
}

# Define Z coordinates
Z_ABOVE = -20 # Intermediate height above the pickup location
Z_GROUND = -169 # Tile pickup height
Z_PLACE = 20 # The height where the tile is dropped
Z_ABOVE_PLACE = 20 # Intermediate place above the location

# Kernel for morphological operations
kernel = np.ones((3, 3), np.uint8)

# Load the transformation matrix from the file
transformation_matrix = np.loadtxt(r"C:\Users\Paavo Meri\Documents\GitHub\Kesaprojektit-24---Machine-vision-for-robotic-arm\transformation_matrix.txt")


def ConnectRobot(): 
    try:
        ip = "192.168.1.6"
        dashboardPort = 29999
        movePort = 30003
        feedPort = 30004
        print("Connection being established...")
        dashboard = DobotApiDashboard(ip, dashboardPort)
        move = DobotApiMove(ip, movePort)
        feed = DobotApi(ip, feedPort)
        print(">. <Connection successful>! <")
        return dashboard, move, feed
    except Exception as e:
        print(":(Connection failed:(")
        raise e

def RunPoint(move: DobotApiMove, point_list: list):
    move.MovJ(point_list[0], point_list[1], point_list[2], point_list[3])

def SuctionCup(dashboard: DobotApiDashboard, PORT, STATUS):
    dashboard.DO(PORT, STATUS) # PORT 1 = suction PORT 2 = air pressure     STATUS: 1 = on 0 = off

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
        
def show_warning(color, requested, available):
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    result = messagebox.askokcancel( f"Not enough {color} tiles detected.\nRequested: {requested}, Available: {available}\nDo you want to continue?")
    root.destroy()
    return result

def transform_coordinates(transformation_matrix, pixel_coord):
    pixel_coord = np.append(pixel_coord, 1)  # Add the homogeneous coordinate
    robot_coord = transformation_matrix.T @ pixel_coord
    return robot_coord[:2]  # Return the first two coordinates (x, y)

def process_image(color_coordinates):
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
    sleep(0.5)
    if not cap.isOpened():
        print("Error: Could not open video device.")
        return None

    try:  # Added try block
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            return None

        height, width, _ = frame.shape
        crop_top = 0 
        crop_bottom = height
        crop_left = 1250
        crop_right = width
        cropped_frame = frame[crop_top:crop_bottom, crop_left:crop_right]
        hsv = cv2.cvtColor(cropped_frame, cv2.COLOR_BGR2HSV)
        process_pink_color(hsv, cropped_frame, color_coordinates)

        for color, (lower, upper) in color_ranges_hsv.items():
            if "pink" in color:
                continue
            
            mask = cv2.inRange(hsv, lower, upper)
            mask = cv2.GaussianBlur(mask, (15, 15), 0)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
            
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 500:
                    rect = cv2.minAreaRect(contour)
                    box = cv2.boxPoints(rect)
                    box = np.intp(box)
                    
                    width = rect[1][0]
                    height = rect[1][1]
                    
                    aspect_ratio = float(width) / height if width > height else float(height) / width
                    
                    min_size = 100
                    max_size = 999
                    
                    if 0.8 < aspect_ratio < 1.2 and min_size < width < max_size and min_size < height < max_size:
                        center_x = int(rect[0][0])
                        center_y = int(rect[0][1])
                        
                        transformed_x, transformed_y = transform_coordinates(transformation_matrix, np.array([center_x, center_y]))
                        
                        if color not in color_coordinates:
                            color_coordinates[color] = []
                        color_coordinates[color].append((transformed_x, transformed_y))
                        
                        cv2.drawContours(cropped_frame, [box], 0, (0, 255, 0), 5)
                        cv2.circle(cropped_frame, (center_x, center_y), 3, (0, 0, 255), -1)
                        cv2.putText(cropped_frame, color, (center_x + 10, center_y), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3)

        screen_res = 1280, 720
        scale_width = screen_res[0] / cropped_frame.shape[1]
        scale_height = screen_res[1] / cropped_frame.shape[0]
        scale = min(scale_width, scale_height)
        window_width = int(cropped_frame.shape[1] * scale)
        window_height = int(cropped_frame.shape[0] * scale)
        resized_frame = cv2.resize(cropped_frame, (window_width, window_height))
        
        return resized_frame
    finally:  # Added finally block
        cap.release()

def process_pink_color(hsv, cropped_frame, color_coordinates):
    pink_mask = cv2.inRange(hsv, color_ranges_hsv["pink1"][0], color_ranges_hsv["pink1"][1]) | \
                cv2.inRange(hsv, color_ranges_hsv["pink2"][0], color_ranges_hsv["pink2"][1])
    pink_mask = cv2.GaussianBlur(pink_mask, (15, 15), 0)
    pink_mask = cv2.morphologyEx(pink_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    pink_mask = cv2.morphologyEx(pink_mask, cv2.MORPH_OPEN, kernel, iterations=2)

    contours, _ = cv2.findContours(pink_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500:
            rect = cv2.minAreaRect(contour)
            box = cv2.boxPoints(rect)
            box = np.intp(box)
            
            width = rect[1][0]
            height = rect[1][1]
            
            aspect_ratio = float(width) / height if width > height else float(height) / width
            
            min_size = 100
            max_size = 999
            
            if 0.8 < aspect_ratio < 1.2 and min_size < width < max_size and min_size < height < max_size:
                center_x = int(rect[0][0])
                center_y = int(rect[0][1])
                
                transformed_x, transformed_y = transform_coordinates(transformation_matrix, np.array([center_x, center_y]))
                  
                if "pink" not in color_coordinates:
                    color_coordinates["pink"] = []
                color_coordinates["pink"].append((transformed_x, transformed_y))
                
                cv2.drawContours(cropped_frame, [box], 0, (0, 255, 0), 5)
                cv2.circle(cropped_frame, (center_x, center_y), 3, (0, 0, 255), -1)
                cv2.putText(cropped_frame, "pink", (center_x + 10, center_y), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 3)


def main(user_inputs):
    dashboard, move, feed = ConnectRobot()
    print("Enabling")
    dashboard.EnableRobot()
    print("Enabled)")
    feed_thread = threading.Thread(target=GetFeed, args=(feed,))
    feed_thread.setDaemon(True)
    feed_thread.start()
    feed_thread1 = threading.Thread(target=ClearRobotError, args=(dashboard,))
    feed_thread1.setDaemon(True)
    feed_thread1.start()
    print("Executing in a loop...")

    color_coordinates = {}
    process_image(color_coordinates)

    cv2.waitKey(0)
    cv2.destroyAllWindows()

    for color, coords in color_coordinates.items():
        print(f"Detected {len(coords)} {color} tiles")
        for coord in coords:
            print(f"{color} tile at {coord}")

    for color, count in user_inputs.items():
        coords = color_coordinates.get(color, [])
        if len(coords) < count:
            continue_execution = show_warning(color, count, len(coords))
            if not continue_execution:
                print("Execution stopped by the user.")
                return    

    for color, count in user_inputs.items():
        coords = color_coordinates.get(color, [])
        for i in range(count):
            if i < len(coords):
                coord = coords[i]
                above_tile = [coord[0], coord[1], Z_ABOVE, 0]
                tile = [coord[0], coord[1], Z_GROUND, 0]
                above_place_location = [PLACE_LOCATIONS[color][0], PLACE_LOCATIONS[color][1], Z_ABOVE_PLACE, 0]
                place_location = [PLACE_LOCATIONS[color][0], PLACE_LOCATIONS[color][1], Z_PLACE, 0]

                RunPoint(move, above_tile)
                WaitArrive(above_tile)
                RunPoint(move, tile)
                WaitArrive(tile)
                SuctionCup(dashboard, 1, 1)
                sleep(0.5)
                RunPoint(move, above_tile)
                WaitArrive(above_tile)

                RunPoint(move, above_place_location)
                WaitArrive(above_place_location)
                RunPoint(move, place_location)
                WaitArrive(place_location)
                SuctionCup(dashboard, 1, 0)
                SuctionCup(dashboard, 2, 1)
                sleep(0.2)
                SuctionCup(dashboard, 2, 0)

                RunPoint(move, above_place_location)
                WaitArrive(above_place_location)

            else:
                break

if __name__ == "__main__":
    if len(sys.argv) != 7:
        print("Usage: python main_script.py <blue_count> <green_count> <yellow_count> <pink_count> <orange_count> <purple_count>")
        sys.exit(1)

    user_inputs = {
        'blue': int(sys.argv[1]),
        'green': int(sys.argv[2]),
        'yellow': int(sys.argv[3]),
        'pink': int(sys.argv[4]),
        'orange': int(sys.argv[5]),
        'purple': int(sys.argv[6])
    }
    main(user_inputs)