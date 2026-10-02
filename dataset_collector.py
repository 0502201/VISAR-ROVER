import cv2
import time
import os

# Configuration
CAM_URL = "http://192.168.29.141:8080/video"
OUTPUT_DIR = "dataset_cracks"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print("=========================================")
print("  VISAR Automated Dataset Collector")
print("=========================================")
print(f"Target: {CAM_URL}")
print("Mission: Capture 5 Rounds composed of 5 photos each.")
print("=========================================\n")

cap = cv2.VideoCapture(CAM_URL)
if not cap.isOpened():
    print("[!] ERROR: Cannot connect to camera stream. Is the phone/camera server running?")
    exit(1)

total_photos = 0

for round_num in range(1, 6):
    print(f"\n--- [ ROUND {round_num} / 5 ] ---")
    
    if round_num == 1:
        print(">> Aim the camera at the FIRST target area.")
        print(">> Capturing will begin in 5 seconds...")
        for i in range(5, 0, -1):
            print(f"    ... {i}")
            time.sleep(1)
    else:
        print(">> Please REPOSITION the camera to a new crack area.")
        print(">> Capturing will begin in 10 seconds...")
        for i in range(10, 0, -1):
            print(f"    ... {i}")
            time.sleep(1)

    print(f">> [BURST CAPTURE] Taking 5 photos for Round {round_num}...")
    
    for photo_num in range(1, 6):
        # Read multiple times rapidly to clear out OpenCV's frame buffer and get a real-time shot
        for _ in range(5): 
            cap.read()
            
        ret, frame = cap.read()
        if ret:
            # We save the raw frame for maximum training quality
            filename = os.path.join(OUTPUT_DIR, f"crack_round{round_num}_photo{photo_num}.jpg")
            cv2.imwrite(filename, frame)
            print(f"   [+] Saved {filename}")
            total_photos += 1
        else:
            print(f"   [!] STREAM HICCUP: Failed to capture photo {photo_num}")
            
        # Small 0.5s pause between burst shots
        time.sleep(0.5) 

cap.release()
print("\n=========================================")
print(f"COLLECTION COMPLETE! {total_photos} photos saved to the '{OUTPUT_DIR}' folder.")
print("You can use these for testing or YOLO model training.")
print("=========================================")
