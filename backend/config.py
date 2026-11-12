import os
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
MODEL_DIR = os.path.join(BASE_DIR)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_DATABASE", "httm")
}

CLOUDINARY_CONFIG = {
    "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    "api_key": os.getenv("CLOUDINARY_API_KEY", ""),
    "api_secret": os.getenv("CLOUDINARY_API_SECRET", "")
}

MODEL_NAME = "antelopev2"
SIMILARITY_THRESHOLD = 0.50
ATTENDANCE_COOLDOWN = 60

LONG_RANGE_PHONE_URL = os.getenv(
    "LONG_RANGE_PHONE_URL", "http://172.22.182.50:8080"
).rstrip("/")