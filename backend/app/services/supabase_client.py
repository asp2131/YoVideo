import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Force reload environment variables from .env file, overriding any existing values
load_dotenv(override=True)

# Explicitly set the correct values to ensure we're using the videothingy project
url: str = "https://ghkowjxqwxsikrdivwxl.supabase.co"
key: str = os.environ.get("SUPABASE_ANON_KEY")

print(f" Supabase Client Debug:")
print(f"   URL: {url}")
print(f"   Key: {key[:50]}...{key[-10:] if key else 'None'}")

if not url or not key:
    raise EnvironmentError("Supabase URL and Key must be set in the environment variables.")

supabase: Client = create_client(url, key)
