import cloudinary
import cloudinary.uploader
from backend.config import CLOUDINARY_CONFIG
from urllib.parse import unquote
# Khởi tạo Cloudinary
cloudinary.config(**CLOUDINARY_CONFIG)
def upload_avatar(file_bytes, filename: str) -> str:
    """Upload ảnh đại diện lên Cloudinary và trả về URL ảnh"""
    try:
        response = cloudinary.uploader.upload(
            file_bytes,
            folder="user_avatars",
            public_id=f"avatar_{filename}"
        )
        return response.get("secure_url")
    except Exception as e:
        print(f"⚠️ Lỗi Upload Cloudinary: {e}")
        return None
def delete_avatar(avatar_url: str):
    """Xóa ảnh đại diện khỏi Cloudinary bằng URL"""
    if not avatar_url:
        return
    try:
        # Tách public_id từ URL
        encode_public_id = "user_avatars/" + avatar_url.split("/")[-1].split(".")[0]
        public_id=unquote(encode_public_id)
        cloudinary.uploader.destroy(public_id)
        print(public_id)
    except Exception as e:
        print(f"⚠️ Lỗi Xóa Cloudinary: {e}")