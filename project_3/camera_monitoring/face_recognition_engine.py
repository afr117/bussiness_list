import cv2
import numpy as np
import os
import json
import datetime
from PIL import Image
from typing import List, Dict, Optional, Tuple
import pickle

class FaceRecognitionEngine:
    def __init__(self):
        self.reference_faces_dir = "data/reference_faces"
        self.detections_dir = "data/detections"
        self.reference_data_file = "data/reference_faces.json"
        self.detections_file = "data/detections.json"
        self.settings_file = "data/face_settings.json"
        
        # Initialize OpenCV face detector
        cascade_filename = 'haarcascade_frontalface_default.xml'
        
        # Try to get cascade path from cv2 package
        try:
            import pkg_resources
            cascade_path = pkg_resources.resource_filename('cv2', f'data/{cascade_filename}')
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
        except:
            # Alternative approaches to find cascade file
            possible_paths = [
                f'/usr/share/opencv4/haarcascades/{cascade_filename}',
                f'/usr/local/share/opencv4/haarcascades/{cascade_filename}',
                f'/opt/homebrew/share/opencv4/haarcascades/{cascade_filename}',
            ]
            
            self.face_cascade = None
            for path in possible_paths:
                if os.path.exists(path):
                    self.face_cascade = cv2.CascadeClassifier(path)
                    break
            
            # Final fallback - try to load from cv2 directly
            if self.face_cascade is None or self.face_cascade.empty():
                try:
                    self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + cascade_filename)
                except AttributeError:
                    # If cv2.data doesn't exist, create empty classifier
                    self.face_cascade = cv2.CascadeClassifier()
        
        # Validate that cascade is properly loaded
        if self.face_cascade is None or self.face_cascade.empty():
            print("Warning: Face cascade classifier could not be loaded. Face detection may not work.")
        
        self.ensure_directories()
        self.reference_faces = self.load_reference_faces()
        self.detections = self.load_detections()
        self.settings = self.load_settings()
    
    def ensure_directories(self):
        """Ensure all necessary directories exist"""
        os.makedirs(self.reference_faces_dir, exist_ok=True)
        os.makedirs(self.detections_dir, exist_ok=True)
    
    def load_reference_faces(self) -> Dict:
        """Load reference faces data"""
        if os.path.exists(self.reference_data_file):
            try:
                with open(self.reference_data_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}
        return {}
    
    def save_reference_faces(self):
        """Save reference faces data"""
        with open(self.reference_data_file, 'w') as f:
            json.dump(self.reference_faces, f, indent=2)
    
    def load_detections(self) -> List[Dict]:
        """Load detection history"""
        if os.path.exists(self.detections_file):
            try:
                with open(self.detections_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
        return []
    
    def save_detections(self):
        """Save detection history"""
        with open(self.detections_file, 'w') as f:
            json.dump(self.detections, f, indent=2)
    
    def load_settings(self) -> Dict:
        """Load face recognition settings"""
        default_settings = {
            'confidence_threshold': 0.6,
            'detection_frequency': 5
        }
        
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    return {**default_settings, **settings}
            except (json.JSONDecodeError, FileNotFoundError):
                return default_settings
        return default_settings
    
    def update_settings(self, new_settings: Dict):
        """Update face recognition settings"""
        self.settings.update(new_settings)
        with open(self.settings_file, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def add_reference_face(self, image: Image.Image, name: str) -> bool:
        """Add a reference face from PIL Image"""
        try:
            # Convert PIL image to numpy array
            image_np = np.array(image)
            
            # Convert RGB to BGR for OpenCV
            if len(image_np.shape) == 3 and image_np.shape[2] == 3:
                image_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
            else:
                image_cv = image_np
            
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
            
            # Detect faces using OpenCV
            if self.face_cascade is not None and not self.face_cascade.empty():
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            else:
                faces = []
            
            if len(faces) == 0:
                return False
            
            # Use the first detected face
            x, y, w, h = faces[0]
            face_crop = image_cv[y:y+h, x:x+w]
            
            # Save the image
            image_filename = f"{name.replace(' ', '_')}.jpg"
            image_path = os.path.join(self.reference_faces_dir, image_filename)
            cv2.imwrite(image_path, image_cv)
            
            # Save the face crop for comparison
            face_filename = f"{name.replace(' ', '_')}_face.jpg"
            face_path = os.path.join(self.reference_faces_dir, face_filename)
            cv2.imwrite(face_path, face_crop)
            
            # Update reference faces data
            self.reference_faces[name] = {
                'image_path': image_path,
                'face_path': face_path,
                'face_coordinates': (x, y, w, h),
                'added_date': datetime.datetime.now().isoformat()
            }
            
            self.save_reference_faces()
            return True
            
        except Exception as e:
            print(f"Error adding reference face: {e}")
            return False
    
    def remove_reference_face(self, name: str) -> bool:
        """Remove a reference face"""
        if name in self.reference_faces:
            face_data = self.reference_faces[name]
            
            # Remove files
            try:
                if os.path.exists(face_data['image_path']):
                    os.remove(face_data['image_path'])
                if os.path.exists(face_data['face_path']):
                    os.remove(face_data['face_path'])
            except Exception as e:
                print(f"Error removing files: {e}")
            
            # Remove from data
            del self.reference_faces[name]
            self.save_reference_faces()
            return True
        return False
    
    def get_reference_faces(self) -> Dict:
        """Get all reference faces"""
        return self.reference_faces
    
    def load_reference_face_image(self, name: str) -> Optional[np.ndarray]:
        """Load reference face image for comparison"""
        if name in self.reference_faces:
            face_path = self.reference_faces[name]['face_path']
            if os.path.exists(face_path):
                try:
                    return cv2.imread(face_path)
                except Exception as e:
                    print(f"Error loading face image: {e}")
        return None
    
    def detect_faces_in_frame(self, frame: np.ndarray, camera_name: str) -> List[Dict]:
        """Detect and recognize faces in a frame"""
        try:
            # Convert to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces using OpenCV
            if self.face_cascade is not None and not self.face_cascade.empty():
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
            else:
                faces = []
            
            matches = []
            
            for i, (x, y, w, h) in enumerate(faces):
                best_match_name = None
                best_match_confidence = 0
                all_comparisons = []
                
                # Extract face region
                face_crop = frame[y:y+h, x:x+w]
                
                # Compare with all reference faces using template matching
                for name in self.reference_faces:
                    reference_face = self.load_reference_face_image(name)
                    if reference_face is not None:
                        # Resize reference face to match detected face size
                        reference_resized = cv2.resize(reference_face, (w, h))
                        
                        # Calculate similarity using template matching
                        result = cv2.matchTemplate(face_crop, reference_resized, cv2.TM_CCOEFF_NORMED)
                        confidence = np.max(result)
                        
                        # Store all comparison results
                        all_comparisons.append({
                            'reference_name': name,
                            'confidence': float(confidence),
                            'percentage': float(confidence * 100)
                        })
                        
                        if confidence > best_match_confidence:
                            best_match_confidence = confidence
                            best_match_name = name
                
                # Sort comparisons by confidence
                all_comparisons.sort(key=lambda x: x['confidence'], reverse=True)
                
                # Check if match is above threshold
                if best_match_confidence >= self.settings['confidence_threshold'] and best_match_name:
                    # Save detection image
                    timestamp = datetime.datetime.now()
                    detection_filename = f"detection_{timestamp.strftime('%Y%m%d_%H%M%S')}_{i}.jpg"
                    detection_path = os.path.join(self.detections_dir, detection_filename)
                    
                    # Save face crop
                    cv2.imwrite(detection_path, face_crop)
                    
                    match_data = {
                        'name': best_match_name,
                        'confidence': float(best_match_confidence),
                        'percentage': float(best_match_confidence * 100),
                        'camera_name': camera_name,
                        'timestamp': timestamp.isoformat(),
                        'image_path': detection_path,
                        'matched_face': best_match_name,
                        'all_comparisons': all_comparisons,
                        'face_coordinates': (x, y, w, h)
                    }
                    
                    matches.append(match_data)
                    
                    # Add to detections history
                    self.detections.append(match_data)
                    self.save_detections()
                else:
                    # Still create entry for faces that don't meet threshold but show all comparisons
                    match_data = {
                        'name': 'No Match',
                        'confidence': float(best_match_confidence) if best_match_name else 0.0,
                        'percentage': float(best_match_confidence * 100) if best_match_name else 0.0,
                        'camera_name': camera_name,
                        'timestamp': datetime.datetime.now().isoformat(),
                        'matched_face': 'None',
                        'all_comparisons': all_comparisons,
                        'face_coordinates': (x, y, w, h)
                    }
                    matches.append(match_data)
            
            return matches
            
        except Exception as e:
            print(f"Error detecting faces: {e}")
            return []
    
    def get_recent_detections(self, limit: int = 50) -> List[Dict]:
        """Get recent detections"""
        return sorted(self.detections, key=lambda x: x['timestamp'], reverse=True)[:limit]
