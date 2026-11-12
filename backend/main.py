import os
import asyncio
# =========================================================================
# IMPORT ONNXRUNTIME VÀ INSIGHTFACE
# =========================================================================
import cv2
import onnxruntime as ort
from insightface.app import FaceAnalysis
# Kiểm tra xem ONNX Runtime có nhìn thấy GPU dựa trên DLL bạn vừa cấu hình không
print("Các Provider khả dụng:", ort.get_available_providers())
import cv2
import numpy as np
from datetime import datetime
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    Form
)
from fastapi.responses import (
    FileResponse,
    JSONResponse
)
from fastapi.staticfiles import StaticFiles
from backend.database import (
    get_user,
    init_db,
    create_user,
    update_user,
    get_user,
    update_user_embedding,
    update_user_avatar,
    save_embedding,
    log_attendance,
    get_attendance_history,
    get_all_users
)
from backend.face_service import FaceService
from backend.config import (
    ATTENDANCE_COOLDOWN,
    LONG_RANGE_PHONE_URL,
)
from backend.cloudinary import upload_avatar, delete_avatar
from backend.database import delete_user
# =========================================================
# FASTAPI
# =========================================================
app = FastAPI(
    title="Face Attendance System"
)
# =========================================================
# FRONTEND
# =========================================================
BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)
FRONTEND_DIR = os.path.join(
    BASE_DIR,
    "frontend"
)
app.mount(
    "/static/css",
    StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")),
    name="css"
)
app.mount(
    "/static/js",
    StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")),
    name="js"
)
# =========================================================
# GLOBAL
# =========================================================
face_service = None
long_range_pipeline = None
last_attendance = {}
# =========================================================
# STARTUP
# =========================================================
@app.on_event("startup")
def startup():
    global face_service, long_range_pipeline
    print(
        "[INFO] Khởi tạo database..."
    )
    init_db()
    print(
        "[INFO] Khởi tạo Face Service..."
    )
    face_service = FaceService()
    from backend.long_range_pipeline import LongRangePipeline
    print("[INFO] Khởi tạo pipeline nhận diện tầm xa...")
    long_range_pipeline = LongRangePipeline(face_service)
# =========================================================
# HOME
# =========================================================
@app.get("/")
def home():
    return FileResponse(
        os.path.join(
            FRONTEND_DIR,
            "index.html"
        )
    )
@app.get("/register")
def register_page():
    return FileResponse(
        os.path.join(
            FRONTEND_DIR,
            "register.html"
        )
    )
@app.get("/history")
def history_page():
    return FileResponse(
        os.path.join(
            FRONTEND_DIR,
            "history.html"
        )
    )
@app.get("/api/users")
def list_users():
    return get_all_users()


@app.get("/api/camera-config")
def camera_config():
    return {"video_url": f"{LONG_RANGE_PHONE_URL}/video"}
# =========================================================
# REGISTER FACE
# =========================================================
@app.post("/api/register")
async def register_face(
    name: str = Form(...),
    file: UploadFile = File(...)
):
    image_bytes = await file.read()
    # 1. Giải mã ảnh để InsightFace nhận diện
    image = cv2.imdecode(
        np.frombuffer(image_bytes, np.uint8),
        cv2.IMREAD_COLOR
    )
    if image is None:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Ảnh không hợp lệ."}
        )
    # 2. Kiểm tra khuôn mặt
    enhanced_image = face_service.enhance_face(image)
    with face_service._lock:
        faces = face_service.app.get(enhanced_image)
    if len(faces) == 0:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Không tìm thấy khuôn mặt."}
        )
    if len(faces) > 1:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "Ảnh phải chỉ có một khuôn mặt."}
        )
    embedding = faces[0].embedding
    try:
        # 3. Upload ảnh đại diện lên Cloudinary
        avatar_url = upload_avatar(image_bytes, name)
        # 4. Lưu User cùng avatar_url vào DB
        user_id = create_user(name, avatar_url=avatar_url)
        # 5. Lưu Embedding
        save_embedding(user_id, embedding)
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": str(e)}
        )
    # Reload embedding vào RAM
    face_service.reload_embeddings()
    return {
        "success": True,
        "message": f"Đăng ký {name} thành công.",
        "user_id": user_id,
        "avatar_url": avatar_url
    }
#DELETE
@app.delete("/api/users/{user_id}")
def remove_user(user_id: int):
    try:
        # Hàm delete_user trong DB trả về success và avatar_url
        success, avatar_url = delete_user(user_id)
        if not success:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Không tìm thấy người dùng."}
            )
        # Xóa ảnh trên Cloudinary nếu có
        if avatar_url:
            delete_avatar(avatar_url)
        # Reload lại RAM
        face_service.reload_embeddings()
        return {"success": True, "message": "Xóa người dùng thành công."}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": str(e)}
        )
#UPDATE
@app.put("/api/users/{user_id}")
async def edit_user(
    user_id: int,
    name: str = Form(...),
    file: UploadFile = File(None)  # File ảnh mới (nếu có)
):
    try:
        # 1. Lấy thông tin user hiện tại trong DB để lấy avatar_url cũ
        current_user = get_user(user_id)
        if not current_user:
            return JSONResponse(
                status_code=404, 
                content={"success": False, "message": "Không tìm thấy người dùng."}
            )
        # 2. Cập nhật tên trong DB
        update_user(user_id, name)
        # 3. Nếu người dùng có upload ảnh mới
        if file and file.filename:
            image_bytes = await file.read()
            image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return JSONResponse(
                    status_code=400, 
                    content={"success": False, "message": "File ảnh không hợp lệ."}
                )
            # Kiểm tra khuôn mặt với InsightFace
            enhanced_image = face_service.enhance_face(image)
            with face_service._lock:
                faces = face_service.app.get(enhanced_image)
            if len(faces) == 0:
                return JSONResponse(
                    status_code=400, 
                    content={"success": False, "message": "Không tìm thấy khuôn mặt trong ảnh mới."}
                )
            if len(faces) > 1:
                return JSONResponse(
                    status_code=400, 
                    content={"success": False, "message": "Ảnh mới phải chỉ có đúng 1 khuôn mặt."}
                )
            # Cập nhật Vector Embedding mới vào DB
            update_user_embedding(user_id, faces[0].embedding)
            # Upload ảnh mới lên Cloudinary
            new_avatar_url = upload_avatar(image_bytes, name)
            # XÓA ẢNH CŨ TRÊN CLOUDINARY
            old_avatar_url = current_user.get("avatar_url")
            if old_avatar_url:
                delete_avatar(old_avatar_url)
            # Cập nhật avatar_url mới vào DB
            update_user_avatar(user_id, new_avatar_url)
        # 4. Reload lại danh sách Embedding trên RAM
        face_service.reload_embeddings()
        return {"success": True, "message": "Cập nhật thông tin thành công."}
    except Exception as e:
        return JSONResponse(
            status_code=500, 
            content={"success": False, "message": str(e)}
        )
# =========================================================
# WEBSOCKET RECOGNITION
# =========================================================
@app.websocket("/ws/recognize")
async def recognize_websocket(
    websocket: WebSocket
):
    await websocket.accept()
    camera_id = websocket.query_params.get("camera_id", "unknown")
    print(
        f"[INFO] Camera {camera_id} đã kết nối."
    )
    awaiting_still = False
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(code=message.get("code", 1000))
            data = message.get("bytes")
            if awaiting_still:
                if data is None:
                    long_range_pipeline.cancel_pending_still()
                    awaiting_still = False
                    continue
                still = cv2.imdecode(
                    np.frombuffer(data, np.uint8),
                    cv2.IMREAD_COLOR
                )
                if still is None:
                    long_range_pipeline.cancel_pending_still()
                    awaiting_still = False
                    continue
                long_range_pipeline.provide_still(still)
                awaiting_still = False
                continue

            if data is None:
                await websocket.send_json({
                    "camera_id": camera_id,
                    "faces": [],
                    "capture_still": False,
                })
                continue
            try:
                frame = cv2.imdecode(
                    np.frombuffer(data, np.uint8),
                    cv2.IMREAD_COLOR
                )
                if frame is None:
                    print(f"[WARN] Camera {camera_id}: Không giải mã được frame JPEG.")
                    await websocket.send_json({"camera_id": camera_id, "faces": []})
                    continue

                loop = asyncio.get_running_loop()
                results = await loop.run_in_executor(
                    None, long_range_pipeline.process, frame
                )
                now = datetime.now()
                current_time = now.timestamp()
                for result in results:
                    if not result["matched"]:
                        result["attendance_logged"] = False
                        continue
                    user_id = result["user_id"]
                    name = result["name"]
                    last_time = last_attendance.get(user_id, 0)
                    if current_time - last_time >= ATTENDANCE_COOLDOWN:
                        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                        date = now.strftime("%Y-%m-%d")
                        log_attendance(user_id, name, timestamp, date)
                        last_attendance[user_id] = current_time
                        result["attendance_logged"] = True
                    else:
                        result["attendance_logged"] = False
            except Exception as error:
                print(f"[WARN] Camera {camera_id}: Lỗi xử lý frame: {error}")
                results = []
                now = datetime.now()
            capture_still = long_range_pipeline.has_pending_still()
            await websocket.send_json({
                "camera_id": camera_id,
                "faces": results,
                "capture_still": capture_still,
                "server_time": now.strftime("%H:%M:%S")
            })
            awaiting_still = capture_still
    except WebSocketDisconnect:
        if awaiting_still:
            long_range_pipeline.cancel_pending_still()
        print(
            f"[INFO] Camera {camera_id} đã ngắt kết nối."
        )
# =========================================================
# HISTORY API
# =========================================================
@app.get("/api/history")
def history():
    rows = get_attendance_history()
    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "user_id": row["user_id"],
            "name": row["name"],
            "timestamp": row["timestamp"],
            "date": row["log_date"]
        })
    return result
