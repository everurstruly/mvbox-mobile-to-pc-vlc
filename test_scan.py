import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from devices.mtp_client import get_devices, scan_mtp
from core.config_manager import load_config

def test_scan():
    config = load_config()
    devices = get_devices()
    print(f"Devices found: {devices}")
    if not devices:
        print("No devices found")
        return
    device_ref = devices[0]['id']
    print(f"Using device: {device_ref}")
    try:
        videos, subtitles = scan_mtp(device_ref, config, print, [], None)
        print(f"Found {len(videos)} videos and {len(subtitles)} subtitles")
        for v in videos[:5]:  # show first 5
            print(f"Video: {v['name']} at {v['virtual_path']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_scan()