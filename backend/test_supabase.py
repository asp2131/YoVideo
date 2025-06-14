#!/usr/bin/env python3

import os
import sys
sys.path.append('/Users/akinpound/Documents/experiments/videothingy/backend')

from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_ANON_KEY")

print(f"SUPABASE_URL: {url}")
print(f"SUPABASE_ANON_KEY: {'***' + key[-10:] if key else 'None'}")

if not url or not key:
    print("ERROR: Missing environment variables!")
    sys.exit(1)

try:
    # Create Supabase client
    supabase = create_client(url, key)
    
    # Test connection by querying the projects table
    result = supabase.table("projects").select("id").limit(1).execute()
    print(f"✅ Supabase connection successful! Found {len(result.data)} projects.")
    
except Exception as e:
    print(f"❌ Supabase connection failed: {e}")
    sys.exit(1)
