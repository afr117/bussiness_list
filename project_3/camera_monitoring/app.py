import streamlit as st
import cv2
import json
import os
import numpy as np
from PIL import Image
import datetime
from camera_manager import CameraManager
from face_recognition_engine import FaceRecognitionEngine
from notification_service import NotificationService

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

def show_camera_feeds():
    st.header("Camera Feeds Overview")
    
    cameras = st.session_state.camera_manager.get_cameras()
    
    if not cameras:
        st.info("No cameras configured. Add cameras in Camera Management.")
        return
    
    # Auto-refresh option
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader(f"Active Cameras ({len(cameras)})")
    with col2:
        auto_refresh = st.checkbox("Auto-refresh feeds", value=False)
        if auto_refresh:
            import time
            # Use controlled refresh to avoid excessive polling
            if 'feeds_last_refresh' not in st.session_state:
                st.session_state.feeds_last_refresh = time.time()
            
            # Only refresh every 5 seconds for camera feeds
            if time.time() - st.session_state.feeds_last_refresh > 5:
                st.session_state.feeds_last_refresh = time.time()
                st.rerun()
    
    # Display camera feeds in grid
    cols_per_row = 2
    for i in range(0, len(cameras), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, camera in enumerate(cameras[i:i+cols_per_row]):
            with cols[j]:
                # Camera status check with caching
                status = get_cached_camera_status(camera['url'])
                
                # Camera card
                with st.container():
                    # Header with status
                    if status:
                        st.success(f"🟢 {camera['name']}")
                    else:
                        st.error(f"🔴 {camera['name']}")
                    
                    # Camera feed thumbnail
                    if status:
                        frame = st.session_state.camera_manager.capture_frame(camera['url'])
                        if frame is not None:
                            # Resize for thumbnail
                            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            st.image(frame_rgb, use_column_width=True)
                        else:
                            st.error("Failed to capture frame")
                    else:
                        st.image("https://via.placeholder.com/400x300?text=Camera+Offline", use_column_width=True)
                    
                    # Camera info
                    st.caption(f"Added: {camera['added_date'][:10]}")
                    st.caption(f"URL: {camera['url'][:40]}...")
                    
                    # Quick action buttons
                    button_col1, button_col2 = st.columns(2)
                    with button_col1:
                        if st.button("🔍 Analyze", key=f"analyze_{i}_{j}"):
                            if status:
                                frame = st.session_state.camera_manager.capture_frame(camera['url'])
                                if frame is not None:
                                    matches = st.session_state.face_engine.detect_faces_in_frame(frame, camera['name'])
                                    if matches:
                                        valid_matches = [m for m in matches if m['name'] != 'No Match']
                                        if valid_matches:
                                            st.success(f"✅ {len(valid_matches)} face(s) detected!")
                                        else:
                                            st.info("👤 Face detected but no matches")
                                    else:
                                        st.info("No faces detected")
                                else:
                                    st.error("Failed to capture frame")
                            else:
                                st.error("Camera offline")
                    
                    with button_col2:
                        if st.button("🔧 Test", key=f"test_{i}_{j}"):
                            with st.spinner("Testing connection..."):
                                new_status = st.session_state.camera_manager.check_camera_status(camera['url'])
                                if new_status:
                                    st.success("✅ Connection OK")
                                else:
                                    st.error("❌ Connection failed")
                    
                    st.markdown("---")

def show_dashboard():
    st.header("Dashboard")
    
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
    st.header("Camera Management")
    
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

def show_face_references():
    st.header("Face References")
    
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
    st.header("Live Monitoring")
    
    cameras = st.session_state.camera_manager.get_cameras()
    reference_faces = st.session_state.face_engine.get_reference_faces()
    
    if not cameras:
        st.warning("No cameras configured. Please add cameras first.")
        return
    
    if not reference_faces:
        st.warning("No reference faces uploaded. Please upload reference faces first.")
        return
    
    # Monitoring controls
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Start Monitoring"):
            st.session_state.monitoring_active = True
            st.success("Monitoring started!")
    
    with col2:
        if st.button("Stop Monitoring"):
            st.session_state.monitoring_active = False
            st.info("Monitoring stopped.")
    
    with col3:
        auto_refresh = st.checkbox("Auto-refresh (10s)", value=False)
        if auto_refresh and st.session_state.monitoring_active:
            import time
            import threading
            
            # Use a more controlled refresh mechanism
            if 'last_refresh' not in st.session_state:
                st.session_state.last_refresh = time.time()
            
            # Only refresh every 10 seconds
            if time.time() - st.session_state.last_refresh > 10:
                st.session_state.last_refresh = time.time()
                st.rerun()
    
    # Camera Status Overview
    st.subheader("Camera Status Overview")
    status_cols = st.columns(min(len(cameras), 4))
    
    for i, camera in enumerate(cameras):
        with status_cols[i % 4]:
            status = get_cached_camera_status(camera['url'])
            if status:
                st.success(f"✅ {camera['name']}")
                st.caption("Online")
            else:
                st.error(f"❌ {camera['name']}")
                st.caption("Offline")
    
    if st.session_state.monitoring_active:
        st.info("🟢 Monitoring is active")
        
        # Camera selection and live feed
        st.subheader("Live Camera Feed")
        selected_camera = st.selectbox("Select camera to view", [cam['name'] for cam in cameras])
        
        if selected_camera:
            camera_data = next(cam for cam in cameras if cam['name'] == selected_camera)
            
            # Check camera connection before proceeding
            camera_online = get_cached_camera_status(camera_data['url'])
            
            if not camera_online:
                st.error(f"❌ Camera '{selected_camera}' is offline. Please check the connection.")
                return
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Live feed section
                feed_placeholder = st.empty()
                
                # Capture and display frame
                frame = st.session_state.camera_manager.capture_frame(camera_data['url'])
                if frame is not None:
                    # Convert BGR to RGB for display
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    feed_placeholder.image(frame_rgb, caption=f"Live Feed - {selected_camera}", width=600)
                    
                    # Auto-analyze frame if monitoring is active
                    matches = st.session_state.face_engine.detect_faces_in_frame(frame, camera_data['name'])
                    
                    if matches:
                        st.subheader("🎯 Face Detection Results")
                        for i, match in enumerate(matches):
                            with st.expander(f"Face #{i+1} - {match['name']} ({match['percentage']:.1f}% match)", expanded=True):
                                detection_col1, detection_col2 = st.columns([1, 2])
                                
                                with detection_col1:
                                    # Show detected face if image exists
                                    if 'image_path' in match and os.path.exists(match['image_path']):
                                        st.image(match['image_path'], caption="Detected Face", width=150)
                                
                                with detection_col2:
                                    st.write(f"**Best Match:** {match['name']}")
                                    st.write(f"**Confidence:** {match['percentage']:.1f}%")
                                    st.write(f"**Threshold:** {st.session_state.face_engine.settings['confidence_threshold']*100:.1f}%")
                                    
                                    if match['name'] != 'No Match':
                                        # Send notification with debouncing to prevent spam
                                        if should_send_notification(match['name'], camera_data['name']):
                                            st.session_state.notification_service.send_notification(
                                                f"Face Detection Alert: {match['name']} detected at {camera_data['name']} with {match['percentage']:.1f}% confidence"
                                            )
                                            st.success("✅ Match found - Notification sent!")
                                        else:
                                            st.success("✅ Match found - Recent notification already sent")
                                    else:
                                        st.info("ℹ️ Face detected but no match above threshold")
                                
                                # Show all comparison results
                                if 'all_comparisons' in match and match['all_comparisons']:
                                    st.write("**Comparison with all reference faces:**")
                                    for comp in match['all_comparisons']:
                                        confidence_color = "🟢" if comp['percentage'] >= st.session_state.face_engine.settings['confidence_threshold']*100 else "🔴"
                                        st.write(f"{confidence_color} {comp['reference_name']}: {comp['percentage']:.1f}%")
                    
                else:
                    feed_placeholder.error("❌ Failed to capture frame from camera")
            
            with col2:
                st.subheader("Reference Faces")
                # Show reference faces for comparison
                for name, info in reference_faces.items():
                    if os.path.exists(info['image_path']):
                        st.image(info['image_path'], caption=name, width=120)
                    else:
                        st.write(f"📷 {name}")
                
                st.subheader("Detection Settings")
                current_threshold = st.session_state.face_engine.settings['confidence_threshold']
                st.write(f"**Threshold:** {current_threshold*100:.1f}%")
                st.write(f"**Detection Method:** Template Matching")
                st.write(f"**Active References:** {len(reference_faces)}")
            
            # Manual controls
            st.subheader("Manual Controls")
            button_col1, button_col2 = st.columns(2)
            
            with button_col1:
                if st.button("🔍 Analyze Current Frame", type="primary"):
                    st.rerun()  # This will re-run the analysis
            
            with button_col2:
                if st.button("📷 Capture & Save Frame"):
                    frame = st.session_state.camera_manager.capture_frame(camera_data['url'])
                    if frame is not None:
                        # Save frame with timestamp
                        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = f"manual_capture_{selected_camera}_{timestamp}.jpg"
                        filepath = os.path.join("data/detections", filename)
                        cv2.imwrite(filepath, frame)
                        st.success(f"Frame saved: {filename}")
    
    else:
        st.info("🔴 Monitoring is inactive - Click 'Start Monitoring' to begin")

def show_settings():
    st.header("Settings")
    
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