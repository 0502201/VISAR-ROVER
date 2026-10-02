import cv2
import numpy as np
import requests
import time
import threading
import os
from flask import Flask, render_template, Response, request
from flask_socketio import SocketIO, emit

# ==========================================
#  CONFIGURATION
# ==========================================
ESP32_IP = "10.101.122.229" 
CAM_URL = "http://10.101.122.19:8080/video"

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

lock = threading.Lock()
frame_lock = threading.Lock()
latest_raw_frame = None
latest_boxes = []
global_stats = {"severity": "Normal", "crack_count": 0, "distance": -1}

# ==========================================
#  TELEMETRY & CAMERA THREADS
# ==========================================
def frame_reader():
    global latest_raw_frame
    while True:
        cap = cv2.VideoCapture(CAM_URL)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            time.sleep(2)
            continue
        while True:
            ret, frame = cap.read()
            if not ret: break
            with frame_lock:
                latest_raw_frame = frame
        cap.release()
        time.sleep(1)

def telemetry_thread():
    while True:
        try:
            response = requests.get(f"http://{ESP32_IP}/status", timeout=1.0)
            if response.status_code == 200:
                data = response.json()
                dist = data.get("distance", -1)
                global_stats["distance"] = dist
                socketio.emit('telemetry_hw', {'mode': data.get("mode", "manual"), 'distance': dist})
        except: pass
        time.sleep(1)

# ==========================================
#  FUSED VISION ENGINE (AS PER USER CODE)
# ==========================================
# VISION CONFIG PARAMETERS
MIN_AREA = 150       # Lowered severely to catch very thin, disconnected hairline segments
MAX_AREA = 100000
ASPECT_RATIO_THRESHOLD = 0.5  # Permissive enough to catch diagonal cracks (1:1 box ratio)
STRAIGHT_ANGLE_TOL = 10
TEXTURE_VAR_THRESHOLD = 1 # Minimal variance for smooth painted walls

# HELPER FUNCTIONS
def is_straight_line(edges):
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
    if lines is None:
        return False
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
        if angle < STRAIGHT_ANGLE_TOL or angle > 180 - STRAIGHT_ANGLE_TOL or (80 < angle < 100):
            return True
    return False

def has_curvature(contour):
    epsilon = 0.01 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return len(approx) >= 3 # Lowered to 3 so triangular missing tiles (corner breaks) pass

def texture_variation(gray, x, y, w, h):
    roi = gray[y:y+h, x:x+w]
    return np.var(roi)

def is_valid_crack(contour, gray):
    area = cv2.contourArea(contour)
    if area < MIN_AREA or area > MAX_AREA:
        return False
        
    perimeter = cv2.arcLength(contour, True)
    if perimeter == 0:
        return False

    # 1. Circularity Check (Thinness/Spindliness)
    # Cracks are thin irregular lines. A perfect circle is 1.0, square is 0.78, pens ~0.25-0.40.
    circularity = (4 * np.pi * area) / (perimeter * perimeter)
    if circularity > 0.35 and area < 15000:
        return False
        
    # 2. Solidity Check (Organic branching)
    # Cracks zig-zag, leaving empty space in their convex hull. Pens/wires have high solidity (~0.95+).
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull)
    if hull_area > 0:
        solidity = float(area) / hull_area
        if solidity > 0.80 and area < 15000:
            return False

    # 3. Manufactured Shape / Rectangularity Check
    # A wire, pen, or laptop edge sits perfectly inside its minimum bounding rectangle (`minAreaRect`).
    rect = cv2.minAreaRect(contour)
    rect_area = rect[1][0] * rect[1][1]
    if rect_area > 0:
        rectangularity = float(area) / rect_area
        if rectangularity > 0.80 and area < 15000: 
            return False

    # 4. Jaggedness / Simple Polygon Check 
    # Perfectly straight lines (wires) and boxes simplify to 4 points. Cracks are bumpy and require many points.
    epsilon = 0.01 * perimeter
    approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) <= 4 and area < 15000:
        return False
        
    return True
def process_vision():
    global latest_raw_frame, latest_boxes, global_stats
    last_emit_time = 0
    
    while True:
        with frame_lock:
            if latest_raw_frame is None:
                time.sleep(0.01)
                continue
            frame = cv2.resize(latest_raw_frame.copy(), (640, 480))

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Noise reduction (Lowered to 5x5 to avoid washing out very thin hairline cracks)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # Edge detection (Increased sensitivity for very faint wall cracks)
        edges = cv2.Canny(blur, 20, 80)

        # Morphological Dilation: Bridges gaps in spidery or disconnected cracks (like pitted concrete)
        kernel_dilate = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel_dilate, iterations=1)

        # REMOVE STRAIGHT LINES (WIRES) 
        # DISABLED: The actual cracks are strictly vertical; this function erases valid cracks!
        # if is_straight_line(edges):
        #     lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100, minLineLength=100, maxLineGap=10)
        #     if lines is not None:
        #         for line in lines:
        #             x1, y1, x2, y2 = line[0]
        #             angle = abs(np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi)
        #             if angle < 10 or angle > 170 or (80 < angle < 100):
        #                 cv2.line(edges, (x1, y1), (x2, y2), 0, 5)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        new_boxes = []
        crack_count = 0
        severity = "Normal"
        current_distance = global_stats.get("distance", -1)

        for cnt in contours:
            if is_valid_crack(cnt, gray):
                # Enforce distance (1-20cm). If sensor offline/error (-1), we allow detection for testing!
                if current_distance != -1 and (current_distance < 1 or current_distance > 20):
                    continue
                    
                crack_count += 1
                x, y, w, h = cv2.boundingRect(cnt)
                
                area = cv2.contourArea(cnt)
                if area > 15000:
                    color = (255, 0, 255) # Purple for Critical Voids
                    label = f"CRITICAL VOID [{int(area)}px]"
                    severity = "CRITICAL SPALLING"
                else:
                    color = (0, 0, 255) # Red for Detection
                    label = f"MAJOR CRACK [{int(area)}px]"
                    severity = "CRACK DETECTED"
                
                new_boxes.append((x, y, w, h, color, label))

        # Update and Emit
        now = time.time()
        if now - last_emit_time > 0.1:
            socketio.emit('telemetry_vision', {'cracks': crack_count, 'severity': severity})
            last_emit_time = now
        
        with lock:
            latest_boxes = new_boxes
            global_stats["severity"] = severity
            global_stats["crack_count"] = crack_count
            
        time.sleep(0.01)

def generate_frames():
    global latest_raw_frame, latest_boxes
    while True:
        with frame_lock:
            if latest_raw_frame is None:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame, "CONNECTING TO CAMERA...", (140, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                (flag, encodedImage) = cv2.imencode(".jpg", frame)
                if flag:
                    yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
                time.sleep(0.5)
                continue
            frame = cv2.resize(latest_raw_frame.copy(), (640, 480))
        
        with lock:
            boxes = latest_boxes
        
        # Draw the "Advanced Crack Detection" visuals
        for x, y, w, h, color, label in boxes:
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        (flag, encodedImage) = cv2.imencode(".jpg", frame)
        if not flag: continue
        yield(b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + bytearray(encodedImage) + b'\r\n')
        time.sleep(1/30.0)

@app.route('/')
def index(): return render_template('index.html')

@app.route('/video_feed')
def video_feed(): return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/control')
def control():
    cmd = request.args.get('cmd')
    if cmd:
        try:
            if cmd in ['manual']:
                requests.get(f"http://{ESP32_IP}/mode?m={cmd}", timeout=2.0)
            elif cmd in ['auto']:
                return "Auto Mode Disabled", 403
            else:
                requests.get(f"http://{ESP32_IP}/{cmd}", timeout=1.0)
            return "OK"
        except: return "Offline", 503
    return "No command", 400

if __name__ == '__main__':
    threading.Thread(target=frame_reader, daemon=True).start()
    threading.Thread(target=telemetry_thread, daemon=True).start()
    threading.Thread(target=process_vision, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
