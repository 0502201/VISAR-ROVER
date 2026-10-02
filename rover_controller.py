import keyboard
import requests
import time

# ==========================================
#  CONFIGURE YOUR ESP32 IP ADDRESS HERE
# ==========================================
ESP32_IP = "10.101.122.229"  # <-- Change this to the IP printed in your Arduino Serial Monitor

BASE_URL = f"http://{ESP32_IP}/"

# Keep track of the current command to avoid spamming the ESP32 with the same command
current_cmd = "stop"

def send_command(cmd):
    global current_cmd
    if cmd != current_cmd:
        current_cmd = cmd
        try:
            url = f"{BASE_URL}{cmd}"
            # Fast timeout to prevent the script from freezing if connection is slow
            requests.get(url, timeout=0.5) 
            print(f"> Mapped Key Processed: Action -> {cmd.upper()}")
        except requests.exceptions.RequestException as e:
            print(f"[!] Error: Could not reach the Rover. Check if IP {ESP32_IP} is correct and Rover is powered on.")

def on_press(event):
    if event.name in ['w', 'up']:
        send_command("forward")
    elif event.name in ['s', 'down']:
        send_command("reverse")
    elif event.name in ['a', 'left']:
        send_command("left")
    elif event.name in ['d', 'right']:
        send_command("right")

def on_release(event):
    # Only send a stop command if a movement key was released
    if event.name in ['w', 'a', 's', 'd', 'up', 'down', 'left', 'right']:
        send_command("stop")

def main():
    print("===========================================")
    print("   🤖 VISAR ROVER KEYBOARD CONTROLLER    ")
    print("===========================================")
    print(f"Target Rover IP: {ESP32_IP}")
    print("\n[ Controls ]")
    print(" W or ↑ : Move Forward")
    print(" S or ↓ : Move Backward")
    print(" A or ← : Turn Left")
    print(" D or → : Turn Right")
    print("\nNOTE: The rover stops moving when you release the key.")
    print("Press 'ESC' to quit the controller.")
    print("===========================================\n")

    # Hook the keys
    keyboard.on_press(on_press)
    keyboard.on_release(on_release)

    # Block forever until ESC is pressed
    keyboard.wait('esc')
    print("Exiting VISAR Controller. Goodbye!")

if __name__ == "__main__":
    main()
