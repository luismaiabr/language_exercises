import sys
from pathlib import Path

# Ensure project root is in sys.path for Vercel serverless environment
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

# Vercel entrypoint
app = app

