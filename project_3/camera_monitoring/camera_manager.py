import json
import os
import cv2
import requests
import datetime
from typing import List, Dict, Optional
import numpy as np

class CameraManager:
    def __init__(self):
        self.cameras_file = "data/cameras.json"
        self.ensure_data_directory()
        self.cameras = self.load_cameras()
    
    def ensure_data_directory(self):
        """Ensure data directory exists"""
        os.makedirs("data", exist_ok=True)
    
    def load_cameras(self) -> List[Dict]:
        """Load cameras from JSON file"""
        if os.path.exists(self.cameras_file):
            try:
                with open(self.cameras_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def save_cameras(self):
        """Save cameras to JSON file"""
        with open(self.cameras_file, 'w') as f:
            json.dump(self.cameras, f, indent=2)
    
    def add_camera(self, name: str, url: str) -> bool:
        """Add a new camera"""
        # Check if camera already exists
        for camera in self.cameras:
            if camera['name'] == name or camera['url'] == url:
                return False
        
        # Test camera connection
        if not self.check_camera_status(url):
            return False
        
        camera_data = {
            'name': name,
            'url': url,
            'added_date': datetime.datetime.now().isoformat(),
            'status': 'active'
        }
        
        self.cameras.append(camera_data)
        self.save_cameras()
        return True
    
    def remove_camera(self, index: int) -> bool:
        """Remove a camera by index"""
        if 0 <= index < len(self.cameras):
            self.cameras.pop(index)
            self.save_cameras()
            return True
        return False
    
    def get_cameras(self) -> List[Dict]:
        """Get all cameras"""
        return self.cameras
    
    def check_camera_status(self, url: str) -> bool:
        """Check if camera URL or local webcam is accessible"""
        try:
            # Check if it's a local webcam (integer index)
            if url.isdigit():
                camera_index = int(url)
                cap = cv2.VideoCapture(camera_index)
            else:
                # It's a URL
                cap = cv2.VideoCapture(url)
            
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                return ret and frame is not None
            return False
        except Exception:
            if not url.isdigit():
                try:
                    # Fallback: try HTTP request for stream URLs only
                    response = requests.head(url, timeout=5)
                    return response.status_code == 200
                except Exception:
                    return False
            return False
    
    def capture_frame(self, url: str) -> Optional[np.ndarray]:
        """Capture a frame from camera (URL or local webcam)"""
        try:
            # Check if it's a local webcam (integer index)
            if url.isdigit():
                camera_index = int(url)
                cap = cv2.VideoCapture(camera_index)
            else:
                # It's a URL
                cap = cv2.VideoCapture(url)
            
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    return frame
            return None
        except Exception as e:
            print(f"Error capturing frame: {e}")
            return None
    
    def get_camera_by_name(self, name: str) -> Optional[Dict]:
        """Get camera by name"""
        for camera in self.cameras:
            if camera['name'] == name:
                return camera
        return None
