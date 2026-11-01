from app import app
from inference import warmup
# Load one shared CPU model per worker before accepting requests.
warmup()
