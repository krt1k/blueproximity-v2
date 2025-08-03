#!/usr/bin/env python3
import asyncio
from bleak import BleakScanner
import dbus
import time
import sys

# --- Configuration ---
# Replace with your phone's Bluetooth MAC address
# Note: On some systems, especially with BLE, the address might change.
# You may need to find the specific address your computer sees.
DEVICE_ADDRESS = "78:02:8B:CE:F6:DF"

# RSSI thresholds - you'll need to experiment to find the right values
# A higher number means a stronger signal (closer)
LOCK_THRESHOLD = -70  # Lock when RSSI drops below this value
UNLOCK_THRESHOLD = -60 # Unlock when RSSI goes above this value

# How long the device needs to be "away" before locking (in seconds)
AWAY_TIMEOUT = 15
# --- End Configuration ---

# Global state
last_seen_time = 0
is_locked = False

def get_screensaver_interface():
    """Gets the D-Bus interface for the screensaver."""
    try:
        session_bus = dbus.SessionBus()
        # For GNOME Desktop
        screensaver_object = session_bus.get_object('org.gnome.ScreenSaver',
                                                    '/org/gnome/ScreenSaver')
        return dbus.Interface(screensaver_object, 'org.gnome.ScreenSaver')
    except dbus.exceptions.DBusException as e:
        print(f"Error connecting to D-Bus. Is this a GNOME desktop? Error: {e}")
        # Add checks for other desktop environments if needed
        # For Cinnamon: 'org.cinnamon.ScreenSaver'
        # For MATE: 'org.mate.ScreenSaver'
        sys.exit(1)

def lock_screen(interface):
    """Locks the screen if it's not already locked."""
    global is_locked
    try:
        if not interface.GetActive():
            interface.Lock()
            is_locked = True
            print("Screen locked.")
    except dbus.exceptions.DBusException as e:
        print(f"Error locking screen: {e}")

def unlock_screen(interface):
    """Unlocks the screen if it is locked."""
    global is_locked
    try:
        # Note: True unlocking is a security risk and complex.
        # This deactivates the screensaver, showing the password prompt.
        if interface.GetActive():
            # This method might not work on all systems to "unlock".
            # It essentially dismisses the lock screen overlay.
            interface.SetActive(False)
            is_locked = False
            print("Screen unlocked (password prompt shown).")
    except dbus.exceptions.DBusException as e:
        print(f"Error unlocking screen: {e}")

def detection_callback(device, advertisement_data):
    """Callback for when a device is detected by BleakScanner."""
    global last_seen_time
    if device.address.upper() == DEVICE_ADDRESS.upper():
        print(f"Device found: {device.address} | RSSI: {advertisement_data.rssi}")
        last_seen_time = time.time()
        
        screensaver = get_screensaver_interface()
        if advertisement_data.rssi > UNLOCK_THRESHOLD:
            if is_locked or screensaver.GetActive():
                 unlock_screen(screensaver)

async def main():
    """Main function to run the scanner and check for device absence."""
    global last_seen_time
    if DEVICE_ADDRESS == "XX:XX:XX:XX:XX:XX":
        print("Please edit the script and set your device's MAC address.")
        sys.exit(1)

    print("Starting proximity monitor...")
    print(f"Device to track: {DEVICE_ADDRESS.upper()}")
    print(f"Lock threshold: RSSI < {LOCK_THRESHOLD}")
    print(f"Unlock threshold: RSSI > {UNLOCK_THRESHOLD}")

    # Initialize last_seen_time to now to prevent immediate lock
    last_seen_time = time.time()

    # The detection callback is now passed to the constructor
    scanner = BleakScanner(detection_callback=detection_callback)
    await scanner.start()

    screensaver = get_screensaver_interface()

    while True:
        await asyncio.sleep(5) # Check every 5 seconds
        
        time_since_seen = time.time() - last_seen_time
        print(f"Time since last seen: {time_since_seen:.2f} seconds")

        if time_since_seen > AWAY_TIMEOUT:
            if not is_locked and not screensaver.GetActive():
                print("Device is away. Locking screen.")
                lock_screen(screensaver)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopping proximity monitor.")
        sys.exit(0)
