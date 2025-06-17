#!/usr/bin/env python3

import os
from dotenv import load_dotenv

print("=== Environment Variable Debug ===")
print(f"Current working directory: {os.getcwd()}")

# Check if .env file exists
env_file = ".env"
if os.path.exists(env_file):
    print(f"✅ .env file exists at: {os.path.abspath(env_file)}")
    with open(env_file, 'r') as f:
        content = f.read()
        print(f"✅ .env file content preview:")
        for i, line in enumerate(content.split('\n')[:5], 1):
            if line.strip() and not line.startswith('#'):
                if 'SUPABASE_URL' in line:
                    print(f"  Line {i}: {line}")
                elif 'SUPABASE_ANON_KEY' in line:
                    key_part = line.split('=')[1][:50] + "..." if len(line.split('=')[1]) > 50 else line.split('=')[1]
                    print(f"  Line {i}: SUPABASE_ANON_KEY={key_part}")
else:
    print(f"❌ .env file not found at: {os.path.abspath(env_file)}")

# Load environment variables
print("\n=== Loading Environment Variables ===")
load_dotenv()

# Check what was loaded
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")

print(f"SUPABASE_URL: {url}")
if key:
    print(f"SUPABASE_ANON_KEY: {key[:50]}...{key[-10:]}")
else:
    print("SUPABASE_ANON_KEY: None")

# Check if it's the correct project
if url:
    if "ghkowjxqwxsikrdivwxl" in url:
        print("✅ Correct videothingy project URL loaded")
    else:
        print("❌ Wrong project URL loaded")
        
if key:
    if "service_role" in key:
        print("✅ Service role key detected")
    elif "anon" in key:
        print("⚠️  Anon key detected (should be service_role)")
    else:
        print("❓ Unknown key type")
