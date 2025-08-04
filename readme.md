# BlueProximity v2 for Linux

A modern Python script to automatically lock and unlock your Linux desktop based on the proximity of your Bluetooth devices (phone, headphones, etc.). This is a replacement for the deprecated BlueProximity application, designed for modern Ubuntu/Debian-based systems.

## Features

- **Proximity Detection**: Uses Bluetooth RSSI (Received Signal Strength Indication) to determine if a device is near or far.
- **Auto Lock/Unlock**: Locks the screen when all monitored devices go out of range and unlocks when one comes back.
- **Multi-Device Support**: Monitor multiple devices simultaneously (e.g., your phone and your headphones).
- **Configurable**: Easily adjust distance thresholds, timeouts, and other settings.
- **Rotating Logs**: Keeps 7 days of logs at `/path/to/your/repo/logs/blueproximity-<date>.log`.

## Prerequisites

This script is designed for Debian-based Linux distributions like Ubuntu 22.04/24.04.

You will need the following packages:
- `bluez`: For Bluetooth communication (`hcitool`).
- `python3-dbus`: For interacting with the desktop's screen saver.
- `python3-gi`: Python bindings for GObject libraries.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/krt1k/blueproximity-v2.git](https://github.com/krt1k/blueproximity-v2.git)
    cd blueproximity-v2
    ```

2.  **Install dependencies:**
    ```bash
    sudo apt update
    sudo apt install bluez python3-dbus python3-gi
    ```
    *(Note: These are system packages, not pip packages, as they provide system-level bindings.)*

3.  **Find your device's Bluetooth MAC address:**
    Turn on your device's Bluetooth and make it discoverable. Then run:
    ```bash
    hcitool scan
    ```
    Copy the MAC address (e.g., `XX:XX:XX:XX:XX:XX`) of the device(s) you want to monitor.

4.  **Configure the script:**
    Open `blueproximity.py` in a text editor and modify the `CONFIG` section at the top:
    - Add your device name and MAC address to the `devices` dictionary.
    - Adjust the `unlock_distance` and `lock_distance` thresholds based on your environment. A good starting point is to run the script and observe the reported RSSI values when your device is nearby.

## Usage

1.  **Run from the terminal:**
    Make the script executable and run it to test your configuration.
    ```bash
    chmod +x blueproximity.py
    python3 blueproximity.py
    ```

2.  **Run automatically on startup:**
    - Open the "Startup Applications" program on Ubuntu.
    - Click "Add".
    - **Name**: `Bluetooth Proximity Lock`
    - **Command**: `/full/path/to/your/blueproximity-v2/blueproximity.py`
    - **Comment**: `Locks and unlocks the screen based on phone proximity.`
    - Click "Add". The script will now run automatically every time you log in.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
