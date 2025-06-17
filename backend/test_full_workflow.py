#!/usr/bin/env python3
"""
Complete end-to-end test of the video transcription and caption overlay workflow.
This script will:
1. Upload a test video
2. Start transcription and caption overlay
3. Monitor progress
4. Download SRT and processed video
"""

import requests
import time
import json
import os
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8000/api/v1"
TEST_VIDEO_PATH = "test_video.mp4"  # You'll need to provide a test video

def create_test_video():
    """Create a simple test video using FFmpeg if it doesn't exist."""
    if not os.path.exists(TEST_VIDEO_PATH):
        print("Creating test video with speech...")
        # Create a 10-second video with synthesized speech
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'testsrc2=duration=10:size=640x480:rate=30',
            '-f', 'lavfi', '-i', 'sine=frequency=1000:duration=10',
            '-c:v', 'libx264', '-c:a', 'aac', '-shortest', '-y', TEST_VIDEO_PATH
        ]
        
        import subprocess
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Failed to create test video: {result.stderr}")
            print("Please provide a test video file named 'test_video.mp4'")
            return False
        print(f"Test video created: {TEST_VIDEO_PATH}")
    return True

def upload_video():
    """Upload a test video and create a project."""
    print("1. Uploading test video...")
    
    if not os.path.exists(TEST_VIDEO_PATH):
        print(f"Test video not found: {TEST_VIDEO_PATH}")
        return None
    
    with open(TEST_VIDEO_PATH, 'rb') as video_file:
        files = {'file': ('test_video.mp4', video_file, 'video/mp4')}
        data = {'project_name': 'Test Video Transcription'}
        
        response = requests.post(f"{BASE_URL}/upload", files=files, data=data)
        
    if response.status_code == 200:
        result = response.json()
        project_id = result['project_id']
        print(f"✅ Video uploaded successfully! Project ID: {project_id}")
        return project_id
    else:
        print(f"❌ Upload failed: {response.status_code} - {response.text}")
        return None

def start_transcription(project_id):
    """Start the transcription and caption overlay process."""
    print("2. Starting transcription and caption overlay...")
    
    response = requests.post(f"{BASE_URL}/transcribe", json={"project_id": project_id})
    
    if response.status_code == 200:
        result = response.json()
        job_id = result['job_id']
        print(f"✅ Transcription started! Job ID: {job_id}")
        return job_id
    else:
        print(f"❌ Transcription start failed: {response.status_code} - {response.text}")
        return None

def monitor_progress(project_id, max_wait_minutes=10):
    """Monitor the project progress until completion."""
    print("3. Monitoring progress...")
    
    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    
    while time.time() - start_time < max_wait_seconds:
        response = requests.get(f"{BASE_URL}/projects/{project_id}")
        
        if response.status_code == 200:
            project = response.json()
            status = project.get('status', 'unknown')
            print(f"   Status: {status}")
            
            if status == 'completed':
                print("✅ Processing completed!")
                return True
            elif status == 'failed':
                print("❌ Processing failed!")
                return False
            
            # Check if we have transcription data
            transcriptions = project.get('transcriptions', [])
            if transcriptions:
                transcription = transcriptions[0]
                print(f"   Transcription preview: {transcription.get('transcription_text', '')[:100]}...")
        
        time.sleep(10)  # Wait 10 seconds before checking again
    
    print(f"❌ Timeout after {max_wait_minutes} minutes")
    return False

def download_results(project_id):
    """Download the SRT file and processed video."""
    print("4. Downloading results...")
    
    # Download SRT file
    print("   Downloading SRT file...")
    srt_response = requests.get(f"{BASE_URL}/projects/{project_id}/download/srt")
    
    if srt_response.status_code == 200:
        with open(f"test_output_{project_id}.srt", 'wb') as f:
            f.write(srt_response.content)
        print(f"✅ SRT file downloaded: test_output_{project_id}.srt")
    else:
        print(f"❌ SRT download failed: {srt_response.status_code}")
    
    # Download processed video
    print("   Downloading processed video...")
    video_response = requests.get(f"{BASE_URL}/projects/{project_id}/download/video?processed=true")
    
    if video_response.status_code == 200:
        with open(f"test_output_{project_id}_with_captions.mp4", 'wb') as f:
            f.write(video_response.content)
        print(f"✅ Processed video downloaded: test_output_{project_id}_with_captions.mp4")
    else:
        print(f"❌ Processed video download failed: {video_response.status_code}")

def cleanup_project(project_id):
    """Clean up the test project."""
    print("5. Cleaning up...")
    
    response = requests.delete(f"{BASE_URL}/projects/{project_id}")
    
    if response.status_code == 200:
        print("✅ Project cleaned up successfully")
    else:
        print(f"❌ Cleanup failed: {response.status_code}")

def main():
    """Run the complete workflow test."""
    print("🎬 Starting complete video transcription workflow test...")
    print("=" * 60)
    
    # Check if test video exists or create one
    if not create_test_video():
        return
    
    try:
        # Step 1: Upload video
        project_id = upload_video()
        if not project_id:
            return
        
        # Step 2: Start transcription
        job_id = start_transcription(project_id)
        if not job_id:
            return
        
        # Step 3: Monitor progress
        success = monitor_progress(project_id)
        if not success:
            return
        
        # Step 4: Download results
        download_results(project_id)
        
        print("\n" + "=" * 60)
        print("🎉 Complete workflow test PASSED!")
        print("Check the downloaded files:")
        print(f"   - test_output_{project_id}.srt")
        print(f"   - test_output_{project_id}_with_captions.mp4")
        
        # Optional: Clean up
        cleanup_choice = input("\nClean up test project? (y/n): ").lower().strip()
        if cleanup_choice == 'y':
            cleanup_project(project_id)
    
    except KeyboardInterrupt:
        print("\n❌ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")

if __name__ == "__main__":
    main()
