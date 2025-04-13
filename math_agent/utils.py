import pyautogui
try:
    while True:
        x, y = pyautogui.position()
        print(f"Mouse Position: ({x}, {y})", end="\r")
except Exception as e:
    print("Tracking stopped.")