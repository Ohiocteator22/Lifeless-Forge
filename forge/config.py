# forge/config.py
import json
import os
import sys
import subprocess
import platform

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".lifeless-forge")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def detect_system_theme():
    """Return True if system theme is dark, False if light, None if unknown."""
    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            # 0 = dark, 1 = light
            return value == 0
        except:
            return None
    elif system == "Darwin":  # macOS
        try:
            result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                return "Dark" in result.stdout
        except:
            pass
        return None
    else:  # Linux / others – no reliable detection
        return None
