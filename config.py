import os

# Try to load from .env file first
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Loaded .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, using environment variables only")

# -----------------------------
# 🔑 API CREDENTIALS
# -----------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")