#!/usr/bin/env python3
"""
Custom BlueProximity - Ubuntu Screen Lock/Unlock via Bluetooth Proximity
A modern replacement for the deprecated BlueProximity application

Key Features:
- Monitor Bluetooth device proximity using RSSI
- Automatically lock/unlock Ubuntu screen based on device distance
- Support for multiple devices (iPhone and Android)
- Configurable distance thresholds and timeouts
- Compatible with Ubuntu 22.04 and 24.04

Dependencies:
- python3-dbus
- python3-gi
- bluez
"""

import time
import threading
import subprocess
import dbus
import logging
from logging.handlers import TimedRotatingFileHandler
import signal
import sys
import os
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

# --- Configuration - Edit these values for your setup ---
CONFIG = {
    'devices': {
        # Add your device MAC addresses here
        # Find them using: bluetoothctl scan on
        'iPhone': '78:44:8B:CE:H1:DI',        # Your iPhone MAC
        'ULT-WEAR': '00:A4:0ZC:EC:2B:6B',        # Your ULT-WEAR MAC
        # 'Android': 'YY:YY:YY:YY:YY:YY'        # Add an Android MAC if needed
    },
    # --- IMPORTANT: Adjust these based on your environment ---
    # A stronger signal has a higher RSSI (e.g., -40 is stronger than -70)
    'unlock_distance': -10,  # Lock will be disabled if RSSI is stronger (higher) than this
    'lock_distance': -15,    # Lock will be enabled if RSSI is weaker (lower) than this
    
    'scan_interval': 5,      # Seconds between scans
    'lock_timeout': 15,      # Seconds of being "away" before locking
    'unlock_timeout': 5,     # Seconds of being "present" before unlocking
    'debug_mode': True,      # Set to False to reduce logging
}
# --- End Configuration ---


class BluetoothProximityMonitor:
    def __init__(self):
        self.setup_logging()
        self.device_is_present = {}
        self.lock_timers = {}
        self.unlock_timers = {}
        self.screen_locked_by_script = False
        self.running = True
        
        try:
            DBusGMainLoop(set_as_default=True)
            self.session_bus = dbus.SessionBus()
            self.logger.info("D-Bus session initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize D-Bus: {e}")
            sys.exit(1)
            
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def setup_logging(self):
        level = logging.DEBUG if CONFIG['debug_mode'] else logging.INFO
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file_path = os.path.join(log_dir, 'proximity.log')

        # Configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        # Console handler
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)

        # File handler with 7-day rotation
        file_handler = TimedRotatingFileHandler(
            log_file_path, when='midnight', interval=1, backupCount=7
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
    def signal_handler(self, signum, frame):
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        for timer in list(self.lock_timers.values()) + list(self.unlock_timers.values()):
            if timer:
                timer.cancel()
        sys.exit(0)
        
    def get_device_rssi(self, mac_address):
        try:
            result = subprocess.run(
                ['hcitool', 'rssi', mac_address],
                capture_output=True, text=True, timeout=4
            )
            if result.returncode == 0 and 'RSSI return value:' in result.stdout:
                rssi = int(result.stdout.split(':')[-1].strip())
                self.logger.debug(f"hcitool RSSI for {mac_address}: {rssi}")
                return rssi
        except Exception as e:
            self.logger.debug(f"hcitool method failed for {mac_address}: {e}")
        return None
        
    def lock_screen(self):
        if self.is_screen_locked():
            return
        try:
            screensaver = self.session_bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver')
            screensaver.Lock(dbus_interface='org.gnome.ScreenSaver')
            self.screen_locked_by_script = True
            self.logger.info("Screen locked successfully.")
        except Exception as e:
            self.logger.error(f"Failed to lock screen: {e}")
            
    def unlock_screen(self):
        if not self.is_screen_locked() or not self.screen_locked_by_script:
            return
        try:
            screensaver = self.session_bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver')
            screensaver.SetActive(False, dbus_interface='org.gnome.ScreenSaver')
            self.screen_locked_by_script = False
            self.logger.info("Screen unlock attempted (woke screen).")
        except Exception as e:
            self.logger.error(f"Failed to unlock screen: {e}")

    def is_screen_locked(self):
        try:
            screensaver = self.session_bus.get_object('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver')
            return bool(screensaver.GetActive(dbus_interface='org.gnome.ScreenSaver'))
        except Exception as e:
            self.logger.debug(f"Failed to check screen lock status: {e}")
            return False # Assume not locked if status check fails
            
    def handle_device_proximity(self, device_name, mac_address):
        """More robust proximity logic based on state transitions."""
        rssi = self.get_device_rssi(mac_address)
        if rssi is None:
            self.logger.debug(f"{device_name} has no valid RSSI; skipping state update.")
            return
        # Determine the current presence based on RSSI
        is_currently_present = rssi >= CONFIG['lock_distance']
        
        # Get the last known state, default to the current state if unknown
        last_known_state = self.device_is_present.get(device_name, True)
        
        if is_currently_present != last_known_state:
            # State has changed!
            self.logger.info(f"State change for {device_name}: {'Present' if is_currently_present else 'Away'} (RSSI: {rssi})")
            if is_currently_present:
                # Device came back
                self.cancel_timer('lock', device_name)
                self.start_unlock_timer(device_name)
            else:
                # Device left
                self.cancel_timer('unlock', device_name)
                self.start_lock_timer(device_name)
        
        # Update the state
        self.device_is_present[device_name] = is_currently_present
        self.logger.debug(f"{device_name} is {'Present' if is_currently_present else 'Away'} with RSSI: {rssi}")
        
    def start_lock_timer(self, device_name):
        self.cancel_timer('lock', device_name) # Ensure no old timer is running
        def lock_action():
            if not any(self.device_is_present.values()): # Only lock if ALL devices are away
                self.logger.info("All devices are away, locking screen.")
                self.lock_screen()
        
        self.lock_timers[device_name] = threading.Timer(CONFIG['lock_timeout'], lock_action)
        self.lock_timers[device_name].start()
        self.logger.info(f"Lock timer started for {device_name} ({CONFIG['lock_timeout']}s)")
        
    def start_unlock_timer(self, device_name):
        self.cancel_timer('unlock', device_name)
        def unlock_action():
            # Check if at least one device is present
            if any(self.device_is_present.values()):
                self.logger.info(f"{device_name} is present, attempting to unlock.")
                self.unlock_screen()
        
        self.unlock_timers[device_name] = threading.Timer(CONFIG['unlock_timeout'], unlock_action)
        self.unlock_timers[device_name].start()
        self.logger.info(f"Unlock timer started for {device_name} ({CONFIG['unlock_timeout']}s)")

    def cancel_timer(self, timer_type, device_name):
        timer_dict = self.lock_timers if timer_type == 'lock' else self.unlock_timers
        if device_name in timer_dict and timer_dict[device_name]:
            timer_dict[device_name].cancel()
            self.logger.info(f"{timer_type.capitalize()} timer cancelled for {device_name}")

    def validate_configuration(self):
        if not CONFIG['devices'] or all(mac in ['XX:XX:XX:XX:XX:XX', 'YY:YY:YY:YY:YY:YY'] for mac in CONFIG['devices'].values()):
            self.logger.error("Configuration error: No valid device MAC addresses found.")
            return False
        return True
        
    def run(self):
        if not self.validate_configuration():
            return
            
        self.logger.info("Starting Bluetooth proximity monitoring...")
        self.logger.info(f"Monitoring devices: {list(CONFIG['devices'].keys())}")
        self.logger.info(f"Unlock if RSSI > {CONFIG['unlock_distance']} dBm | Lock if RSSI < {CONFIG['lock_distance']} dBm")

        while self.running:
            for device_name, mac_address in CONFIG['devices'].items():
                if not self.running: break
                self.handle_device_proximity(device_name, mac_address)
            
            if self.running:
                time.sleep(CONFIG['scan_interval'])

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      Custom BlueProximity for Ubuntu")
    print("="*50 + "\n")
    
    monitor = BluetoothProximityMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        monitor.signal_handler(signal.SIGINT, None)