import streamlit as st
import cv2
import json
import os
import numpy as np
from PIL import Image
import datetime
import time
import threading
from camera_manager import CameraManager
from face_recognition_engine import FaceRecognitionEngine
from notification_service import NotificationService

# Import streamlit-webrtc components
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av
import queue

# Initialize session state
if 'camera_manager' not in st.session_state:
    st.session_state.camera_manager = CameraManager()
if 'face_engine' not in st.session_state:
    st.session_state.face_engine = FaceRecognitionEngine()
if 'notification_service' not in st.session_state:
    st.session_state.notification_service = NotificationService()
if 'monitoring_active' not in st.session_state:
    st.session_state.monitoring_active = False
if 'last_notifications' not in st.session_state:
    st.session_state.last_notifications = {}
if 'camera_status_cache' not in st.session_state:
    st.session_state.camera_status_cache = {}
if 'cache_timestamps' not in st.session_state:
    st.session_state.cache_timestamps = {}

def get_cached_camera_status(camera_url: str) -> bool:
    """Get camera status with 30-second caching to reduce load"""
    import time
    cache_key = f"status_{camera_url}"
    current_time = time.time()
    
    # Check if we have a cached result that's less than 30 seconds old
    if (cache_key in st.session_state.camera_status_cache and 
        cache_key in st.session_state.cache_timestamps and 
        current_time - st.session_state.cache_timestamps[cache_key] < 30):
        return st.session_state.camera_status_cache[cache_key]
    
    # Get fresh status
    status = st.session_state.camera_manager.check_camera_status(camera_url)
    
    # Cache the result
    st.session_state.camera_status_cache[cache_key] = status
    st.session_state.cache_timestamps[cache_key] = current_time
    
    return status

def should_send_notification(match_name: str, camera_name: str) -> bool:
    """Check if notification should be sent (debouncing)"""
    import time
    notification_key = f"{match_name}_{camera_name}"
    current_time = time.time()
    
    # Only send notification if we haven't sent one for this person/camera in the last 60 seconds
    if (notification_key in st.session_state.last_notifications and 
        current_time - st.session_state.last_notifications[notification_key] < 60):
        return False
    
    st.session_state.last_notifications[notification_key] = current_time
    return True

# WebRTC Video Transformer for face recognition
class FaceRecognitionTransformer:
    def __init__(self, face_engine, notification_service, camera_name):
        self.face_engine = face_engine
        self.notification_service = notification_service
        self.camera_name = camera_name
        self.last_detection_time = 0
        self.detection_interval = 3  # Run face detection every 3 seconds
        self.latest_matches = []
        self.frame_count = 0

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        current_time = time.time()
        
        # Increment frame counter
        self.frame_count += 1
        
        # Run face detection every 3 seconds (not every frame)
        if current_time - self.last_detection_time > self.detection_interval:
            try:
                matches = self.face_engine.detect_faces_in_frame(img, self.camera_name)
                self.latest_matches = matches
                self.last_detection_time = current_time
                
                # Send notifications for matches
                for match in matches:
                    if match['name'] != 'No Match':
                        if should_send_notification(match['name'], self.camera_name):
                            self.notification_service.send_notification(
                                f"Live Stream Alert: {match['name']} detected with {match['percentage']:.1f}% confidence"
                            )
            except Exception as e:
                print(f"Face detection error: {e}")
        
        # Draw detection overlays on the frame
        if self.latest_matches:
            for match in self.latest_matches:
                if 'face_coordinates' in match:
                    x, y, w, h = match['face_coordinates']
                    # Draw rectangle around face
                    color = (0, 255, 0) if match['name'] != 'No Match' else (0, 0, 255)
                    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
                    
                    # Draw label
                    label = f"{match['name']} ({match['percentage']:.1f}%)"
                    cv2.putText(img, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Add frame counter overlay
        cv2.putText(img, f"Frame: {self.frame_count}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")

def main():
    st.set_page_config(
        page_title="Camera Monitoring System",
        page_icon="📹",
        layout="wide"
    )
    
    st.title("📹 Camera Monitoring System with Face Recognition")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Dashboard", "Camera Management", "Camera Feeds", "Face References", "Live Monitoring", "Settings"]
    )
    
    if page == "Dashboard":
        show_dashboard()
    elif page == "Camera Management":
        show_camera_management()
    elif page == "Camera Feeds":
        show_camera_feeds()
    elif page == "Face References":
        show_face_references()
    elif page == "Live Monitoring":
        show_live_monitoring()
    elif page == "Settings":
        show_settings()

def show_dashboard():
    st.header("📊 Dashboard")
    
    # Real-time status refresh
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("System Overview")
    with col2:
        if st.button("🔄 Refresh Status"):
            st.rerun()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Active Cameras", len(st.session_state.camera_manager.get_cameras()))
    
    with col2:
        st.metric("Reference Faces", len(st.session_state.face_engine.get_reference_faces()))
    
    with col3:
        detection_count = len(st.session_state.face_engine.get_recent_detections())
        st.metric("Recent Detections", detection_count)
    
    st.subheader("Camera Status")
    cameras = st.session_state.camera_manager.get_cameras()
    
    if cameras:
        for camera in cameras:
            with st.expander(f"📹 {camera['name']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**URL:** {camera['url']}")
                    st.write(f"**Added:** {camera['added_date']}")
                with col2:
                    status = get_cached_camera_status(camera['url'])
                    if status:
                        st.success("✅ Online")
                    else:
                        st.error("❌ Offline")
    else:
        st.info("No cameras configured. Add cameras in the Camera Management section.")
    
    st.subheader("Recent Detections")
    detections = st.session_state.face_engine.get_recent_detections()
    
    if detections:
        for detection in detections[-10:]:  # Show last 10 detections
            with st.expander(f"Detection at {detection['timestamp']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Camera:** {detection['camera_name']}")
                    st.write(f"**Match:** {detection['matched_face']}")
                    st.write(f"**Confidence:** {detection['confidence']:.2f}")
                with col2:
                    if os.path.exists(detection['image_path']):
                        st.image(detection['image_path'], width=200)
    else:
        st.info("No recent detections.")

def show_camera_management():
    st.header("⚙️ Camera Management")
    
    st.subheader("Add New Camera")
    
    # Quick Add Laptop Camera section
    st.info("💻 **Quick Setup:** To use your laptop's built-in camera, try Camera Index 0 first")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🎥 Add Laptop Camera (Index 0)", type="primary"):
            success = st.session_state.camera_manager.add_camera("Laptop Camera", "0")
            if success:
                st.success("Laptop camera added successfully! Go to Live Monitoring to test it.")
                st.rerun()
            else:
                st.error("Laptop camera not found. Make sure your webcam is connected and not being used by another app.")
    
    with col2:
        if st.button("🎥 Try Camera Index 1"):
            success = st.session_state.camera_manager.add_camera("Camera Index 1", "1")
            if success:
                st.success("Camera added successfully!")
                st.rerun()
            else:
                st.error("Camera not found at index 1.")
    
    st.markdown("---")
    st.subheader("Manual Camera Setup")
    
    with st.form("add_camera_form"):
        camera_name = st.text_input("Camera Name")
        camera_type = st.radio(
            "Camera Type",
            ["Laptop/USB Webcam (use camera index: 0, 1, 2, etc.)", "Network Camera (HTTP/HTTPS URL)"]
        )
        
        if "Laptop/USB" in camera_type:
            camera_url = st.text_input("Camera Index (0 for built-in, 1 for USB, etc.)", value="0")
            st.caption("Common values: 0 = built-in laptop camera, 1 = first USB camera")
        else:
            camera_url = st.text_input("Camera URL (HTTP/HTTPS stream)")
            st.caption("Example: http://192.168.1.100:8080/video")
        
        submitted = st.form_submit_button("Add Camera")
        
        if submitted:
            if camera_name and camera_url:
                success = st.session_state.camera_manager.add_camera(camera_name, camera_url)
                if success:
                    st.success(f"Camera '{camera_name}' added successfully!")
                    st.rerun()
                else:
                    if camera_url.isdigit():
                        st.error(f"Camera not found at index {camera_url}. Make sure your webcam is connected and not being used by another app.")
                    else:
                        st.error("Failed to add camera. Please check the URL.")
            else:
                st.error("Please fill in all fields.")
    
    st.subheader("Existing Cameras")
    cameras = st.session_state.camera_manager.get_cameras()
    
    if cameras:
        for i, camera in enumerate(cameras):
            with st.expander(f"📹 {camera['name']}"):
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**URL:** {camera['url']}")
                    st.write(f"**Added:** {camera['added_date']}")
                
                with col2:
                    if st.button("Test", key=f"test_{i}"):
                        status = st.session_state.camera_manager.check_camera_status(camera['url'])
                        if status:
                            st.success("✅ Working")
                        else:
                            st.error("❌ Failed")
                
                with col3:
                    if st.button("Remove", key=f"remove_{i}"):
                        st.session_state.camera_manager.remove_camera(i)
                        st.success("Camera removed!")
                        st.rerun()
    else:
        st.info("No cameras configured.")

def show_camera_feeds():
    st.header("📷 Camera Feed Snapshots")
    
    cameras = st.session_state.camera_manager.get_cameras()
    
    if not cameras:
        st.info("No cameras configured. Add cameras in Camera Management.")
        return
    
    # Feed update controls
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"Camera Snapshots ({len(cameras)})")
        st.caption("This page shows snapshot previews. For live streaming, use the Live Monitoring page.")
    with col2:
        refresh_rate = st.selectbox("Update Rate", ["Manual only", "5 seconds", "10 seconds", "30 seconds"], index=0)
        
        # Handle auto-refresh based on selection
        if refresh_rate != "Manual only":
            import time
            refresh_seconds = int(refresh_rate.split()[0])
            
            if 'feeds_last_refresh' not in st.session_state:
                st.session_state.feeds_last_refresh = time.time()
            
            if time.time() - st.session_state.feeds_last_refresh > refresh_seconds:
                st.session_state.feeds_last_refresh = time.time()
                st.rerun()
        
        # Manual refresh button
        if st.button("🔄 Update All Snapshots"):
            st.rerun()
    
    # Display camera feeds as snapshots
    for i, camera in enumerate(cameras):
        st.subheader(f"📹 {camera['name']}")
        
        # Camera status check with caching
        status = get_cached_camera_status(camera['url'])
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Display current snapshot
            if status:
                frame = st.session_state.camera_manager.capture_frame(camera['url'])
                if frame is not None:
                    # Convert BGR to RGB for display
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    caption_text = f"Snapshot - {camera['name']}"
                    if refresh_rate != "Manual only":
                        caption_text += f" (Auto-updates every {refresh_rate.lower()})"
                    st.image(frame_rgb, caption=caption_text, use_column_width=True)
                    
                    # Optional face detection (on-demand only to save CPU)
                    with st.expander("🔍 Face Detection Analysis", expanded=False):
                        if st.button(f"Analyze This Snapshot", key=f"analyze_{i}"):
                            with st.spinner("Analyzing snapshot for faces..."):
                                matches = st.session_state.face_engine.detect_faces_in_frame(frame, camera['name'])
                                if matches:
                                    valid_matches = [m for m in matches if m['name'] != 'No Match']
                                    if valid_matches:
                                        st.success(f"✅ Found {len(valid_matches)} known face(s)!")
                                        for match in valid_matches:
                                            st.write(f"🎯 **{match['name']}** - {match['percentage']:.1f}% confidence")
                                    else:
                                        st.info("👤 Face detected but no matches above threshold")
                                else:
                                    st.info("No faces detected in this snapshot")
                        st.caption("💡 For continuous face recognition monitoring, use the 'Live Monitoring' page")
                else:
                    st.error("❌ Failed to capture frame from camera")
            else:
                st.error(f"❌ Camera '{camera['name']}' is offline")
                st.image("https://via.placeholder.com/640x480?text=Camera+Offline", use_column_width=True)
        
        with col2:
            # Camera status and info
            if status:
                st.success("🟢 Online")
            else:
                st.error("🔴 Offline")
            
            st.write(f"**Added:** {camera['added_date'][:10]}")
            st.write(f"**URL:** {camera['url'][:25]}..." if len(camera['url']) > 25 else f"**URL:** {camera['url']}")
            
            # Control buttons
            if st.button("🔧 Test Connection", key=f"test_{i}"):
                with st.spinner("Testing..."):
                    new_status = st.session_state.camera_manager.check_camera_status(camera['url'])
                    if new_status:
                        st.success("✅ Working")
                    else:
                        st.error("❌ Failed")
            
            if st.button("📷 Save Snapshot", key=f"save_{i}"):
                if status:
                    frame = st.session_state.camera_manager.capture_frame(camera['url'])
                    if frame is not None:
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"snapshot_{camera['name'].replace(' ', '_')}_{timestamp}.jpg"
                        filepath = os.path.join("data/detections", filename)
                        os.makedirs("data/detections", exist_ok=True)
                        cv2.imwrite(filepath, frame)
                        st.success(f"Saved: {filename}")
                    else:
                        st.error("Capture failed")
                else:
                    st.error("Camera offline")
            
            # Link to live monitoring
            if st.button(f"🎥 Start Live Stream", key=f"monitor_{i}", type="primary"):
                st.info(f"Go to 'Live Monitoring' page to start live streaming (webcam mode currently available)")
        
        st.markdown("---")
    
    # Information about the two different viewing modes
    with st.expander("📖 Camera Feeds vs Live Monitoring - What's the Difference?", expanded=False):
        st.write("""
        **Camera Feeds Page** (Current):
        - Shows snapshots from all network cameras simultaneously
        - Good for monitoring multiple cameras at once
        - Manual or timed refresh options (5-30 seconds)
        - Face detection analysis on-demand only (saves CPU)
        - Lower resource usage, better for overview monitoring
        
        **Live Monitoring Page**:
        - Shows continuous live video stream at 15-30 FPS
        - Currently supports webcam streaming with WebRTC
        - Real-time face recognition with overlay boxes
        - Automatic notifications for face matches
        - Best for detailed monitoring and security analysis
        - Network camera streaming coming soon
        
        **Note:** For network cameras, use this page for snapshots and the Live Monitoring page will support them soon.
        """)
    
    # Tips for users
    if not st.session_state.camera_manager.get_cameras():
        st.info("💡 **Get Started**: Add cameras in 'Camera Management', then return here to view snapshots")
    elif not st.session_state.face_engine.get_reference_faces():
        st.info("💡 **Enable Face Recognition**: Upload reference faces in 'Face References' to identify people in camera feeds")

def show_face_references():
    st.header("👥 Face References")
    
    st.subheader("Upload Reference Face")
    uploaded_file = st.file_uploader(
        "Choose an image file",
        type=['jpg', 'jpeg', 'png'],
        help="Upload a clear image of the face you want to recognize"
    )
    
    if uploaded_file is not None:
        col1, col2 = st.columns(2)
        
        with col1:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", width=300)
        
        with col2:
            face_name = st.text_input("Name for this face")
            if st.button("Save Reference Face"):
                if face_name:
                    success = st.session_state.face_engine.add_reference_face(image, face_name)
                    if success:
                        st.success(f"Reference face for '{face_name}' saved successfully!")
                        st.rerun()
                    else:
                        st.error("No face detected in the image. Please upload a clear face image.")
                else:
                    st.error("Please enter a name for the face.")
    
    st.subheader("Existing Reference Faces")
    reference_faces = st.session_state.face_engine.get_reference_faces()
    
    if reference_faces:
        cols = st.columns(min(3, len(reference_faces)))
        for i, (name, info) in enumerate(reference_faces.items()):
            with cols[i % 3]:
                if os.path.exists(info['image_path']):
                    st.image(info['image_path'], caption=name, width=150)
                else:
                    st.write(f"📷 {name}")
                
                if st.button(f"Remove {name}", key=f"remove_face_{i}"):
                    st.session_state.face_engine.remove_reference_face(name)
                    st.success(f"Reference face '{name}' removed!")
                    st.rerun()
    else:
        st.info("No reference faces uploaded.")

def show_live_monitoring():
    st.header("🎥 Live Video Streaming with Face Recognition")
    
    cameras = st.session_state.camera_manager.get_cameras()
    reference_faces = st.session_state.face_engine.get_reference_faces()
    
    if not cameras:
        st.warning("No cameras configured. Please add cameras first.")
        return
    
    # Initialize session state for WebRTC
    if 'webrtc_transformer' not in st.session_state:
        st.session_state.webrtc_transformer = None
    
    # Streaming mode selection
    st.subheader("Choose Streaming Source")
    streaming_mode = st.radio(
        "Select video source:",
        ["📹 Use Webcam (Built-in Camera)", "🔗 Use Network Camera (Coming Soon)"],
        help="For now, webcam streaming is available. Network camera streaming will be added soon."
    )
    
    if "Webcam" in streaming_mode:
        # WebRTC Live Streaming Section
        st.subheader("🔴 Live Webcam Stream with Face Recognition")
        
        # Create face recognition transformer
        if st.session_state.webrtc_transformer is None:
            st.session_state.webrtc_transformer = FaceRecognitionTransformer(
                st.session_state.face_engine,
                st.session_state.notification_service,
                "Webcam"
            )
        
        # Configure WebRTC
        rtc_configuration = RTCConfiguration(
            {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
        )
        
        # Main streaming layout
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # WebRTC Streamer with face recognition
            webrtc_ctx = webrtc_streamer(
                key="live-monitoring",
                mode=WebRtcMode.SENDRECV,
                rtc_configuration=rtc_configuration,
                video_frame_callback=st.session_state.webrtc_transformer.transform,
                media_stream_constraints={"video": True, "audio": False},
                async_processing=True,
            )
            
            # Stream status
            if webrtc_ctx.state.playing:
                st.success("🔴 LIVE - Webcam streaming active with face recognition")
                st.caption("Face recognition analyzes frames every 3 seconds")
            else:
                st.info("▶️ Click the play button above to start live webcam streaming")
        
        with col2:
            # Stream information and controls
            st.subheader("📊 Stream Info")
            
            if webrtc_ctx.state.playing:
                st.success("🔴 Streaming Active")
                if st.session_state.webrtc_transformer:
                    st.write(f"**Frames Processed:** {st.session_state.webrtc_transformer.frame_count}")
                    st.write(f"**Face Detection:** Every 3 seconds")
                    st.write(f"**Latest Matches:** {len(st.session_state.webrtc_transformer.latest_matches)}")
            else:
                st.info("⏸️ Stream Stopped")
            
            # Reference faces
            if reference_faces:
                st.subheader("👥 Reference Faces")
                for name, info in reference_faces.items():
                    if os.path.exists(info['image_path']):
                        st.image(info['image_path'], caption=name, width=100)
                    else:
                        st.write(f"📷 {name}")
            else:
                st.info("No reference faces uploaded")
            
            # Detection settings
            st.subheader("⚙️ Settings")
            current_threshold = st.session_state.face_engine.settings['confidence_threshold']
            st.write(f"**Threshold:** {current_threshold*100:.1f}%")
            st.write(f"**Detection Interval:** 3 seconds")
            
            # Reset transformer button
            if st.button("🔄 Reset Detection Counter"):
                if st.session_state.webrtc_transformer:
                    st.session_state.webrtc_transformer.frame_count = 0
                    st.session_state.webrtc_transformer.latest_matches = []
                st.success("Counter reset!")
        
        # Detection Results Section
        if webrtc_ctx.state.playing and st.session_state.webrtc_transformer:
            if st.session_state.webrtc_transformer.latest_matches:
                st.subheader("🎯 Latest Face Detection Results")
                
                for i, match in enumerate(st.session_state.webrtc_transformer.latest_matches):
                    with st.expander(f"Face #{i+1} - {match['name']} ({match['percentage']:.1f}% confidence)", expanded=True):
                        detection_col1, detection_col2 = st.columns([1, 2])
                        
                        with detection_col1:
                            if 'image_path' in match and os.path.exists(match['image_path']):
                                st.image(match['image_path'], caption="Detected Face", width=150)
                        
                        with detection_col2:
                            st.write(f"**Match:** {match['name']}")
                            st.write(f"**Confidence:** {match['percentage']:.1f}%")
                            
                            if match['name'] != 'No Match':
                                st.success("✅ Face recognized!")
                            else:
                                st.info("ℹ️ Face detected but no match above threshold")
                            
                            # Show all comparison results
                            if 'all_comparisons' in match and match['all_comparisons']:
                                st.write("**Comparison Results:**")
                                for comp in match['all_comparisons']:
                                    confidence_color = "🟢" if comp['percentage'] >= st.session_state.face_engine.settings['confidence_threshold']*100 else "🔴"
                                    st.write(f"{confidence_color} **{comp['reference_name']}**: {comp['percentage']:.1f}%")
            else:
                st.info("👁️ Live monitoring active - No faces detected in recent frames")
    
    else:
        # Network camera option (coming soon)
        st.info("🚧 Network camera streaming feature is coming soon! For now, please use the webcam option above.")
        
        # Show available cameras as preview
        if cameras:
            st.subheader("📹 Available Network Cameras (Preview)")
            for camera in cameras:
                with st.expander(f"📷 {camera['name']}"):
                    status = get_cached_camera_status(camera['url'])
                    if status:
                        frame = st.session_state.camera_manager.capture_frame(camera['url'])
                        if frame is not None:
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            st.image(frame_rgb, caption=f"Static preview - {camera['name']}", use_column_width=True)
                    else:
                        st.error(f"Camera '{camera['name']}' is offline")
    
    # Instructions for users
    with st.expander("💡 How to Use Live Video Streaming", expanded=False):
        st.write("""
        **Live Streaming Instructions:**
        1. Select "Use Webcam" option above
        2. Click the ▶️ play button in the video player to start streaming
        3. Allow camera access when prompted by your browser
        4. Live video streams at 15-30 FPS with real-time face detection
        5. Face recognition analyzes frames every 3 seconds automatically
        6. Click the ⏸️ pause button to stop streaming
        
        **Face Recognition Features:**
        - Green rectangles around recognized faces
        - Red rectangles around unrecognized faces
        - Live confidence scores displayed on video
        - Automatic notifications for recognized individuals
        - Detailed comparison results below the video
        
        **Requirements:**
        - Modern browser with WebRTC support (Chrome, Firefox, Safari)
        - Camera access permissions
        - Stable internet connection
        """)
    
    if not reference_faces:
        st.info("💡 **Tip**: Upload reference faces in the 'Face References' section first to enable face recognition matching during live streaming.")

def show_settings():
    st.header("⚙️ Settings")
    
    st.subheader("Email Notifications")
    
    with st.form("email_settings"):
        email_enabled = st.checkbox("Enable email notifications")
        recipient_email = st.text_input("Recipient email address")
        smtp_server = st.text_input("SMTP server", value="smtp.gmail.com")
        smtp_port = st.number_input("SMTP port", value=587, min_value=1, max_value=65535)
        sender_email = st.text_input("Sender email address")
        sender_password = st.text_input("Sender email password", type="password")
        
        if st.form_submit_button("Save Email Settings"):
            settings = {
                'email_enabled': email_enabled,
                'recipient_email': recipient_email,
                'smtp_server': smtp_server,
                'smtp_port': smtp_port,
                'sender_email': sender_email,
                'sender_password': sender_password
            }
            st.session_state.notification_service.update_settings(settings)
            st.success("Email settings saved!")
    
    st.subheader("Detection Settings")
    
    with st.form("detection_settings"):
        confidence_threshold = st.slider("Face recognition confidence threshold", 0.0, 1.0, 0.6, 0.01)
        detection_frequency = st.number_input("Detection frequency (seconds)", value=5, min_value=1, max_value=3600)
        
        if st.form_submit_button("Save Detection Settings"):
            st.session_state.face_engine.update_settings({
                'confidence_threshold': confidence_threshold,
                'detection_frequency': detection_frequency
            })
            st.success("Detection settings saved!")

if __name__ == "__main__":
    main()
