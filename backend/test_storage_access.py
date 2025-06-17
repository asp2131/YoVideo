#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from app.services.supabase_client import supabase

# Test storage access
def test_storage_access():
    print("=== Testing Supabase Storage Access ===")
    
    # Test video file that we know exists
    video_path = "d76b401d-c2e0-4d46-ac24-6ac0ed4370d7.mp4"
    
    try:
        print(f"Attempting to download: {video_path}")
        
        # Try to download the video file
        video_data = supabase.storage.from_("videos").download(video_path)
        
        print(f"✅ Successfully downloaded video!")
        print(f"   File size: {len(video_data)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to download video: {str(e)}")
        print(f"   Error type: {type(e).__name__}")
        
        # Try to get more info about the error
        if hasattr(e, 'response'):
            print(f"   Response: {e.response}")
        if hasattr(e, 'status_code'):
            print(f"   Status code: {e.status_code}")
            
        return False

def test_bucket_access():
    print("\n=== Testing Bucket Access ===")
    
    try:
        # List files in the videos bucket
        files = supabase.storage.from_("videos").list()
        print(f"✅ Successfully listed files in videos bucket:")
        for file in files:
            print(f"   - {file['name']} ({file.get('metadata', {}).get('size', 'unknown')} bytes)")
            
    except Exception as e:
        print(f"❌ Failed to list files: {str(e)}")

if __name__ == "__main__":
    test_bucket_access()
    test_storage_access()
