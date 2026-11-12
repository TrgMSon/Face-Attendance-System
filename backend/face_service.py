import cv2
import numpy as np
import threading
import queue
from insightface.app import FaceAnalysis
from backend.config import (
    MODEL_DIR,
    MODEL_NAME,
    SIMILARITY_THRESHOLD
)
from backend.database import load_embeddings
MIN_FACE_SIZE = 50
def compute_cosine_similarity(embedding, known_matrix):
    """
    Tính Cosine Similarity giữa 1 vector embedding (512,) và Ma trận CSDL (N, 512).
    Trả về mảng 1D độ tương đồng shape (N,)
    """
    # Ép phẳng embedding thành vector 1D (512,)
    emb = embedding.flatten()
    # Tính Norm (Độ dài Euclid)
    norm_emb = np.linalg.norm(emb)
    norm_matrix = np.linalg.norm(known_matrix, axis=1)
    # Tính tích vô hướng và chia cho tích các norm
    dot_product = np.dot(known_matrix, emb)
    # Tránh chia cho 0 bằng np.maximum
    denominator = np.maximum(norm_matrix * norm_emb, 1e-10)
    return dot_product / denominator
class AsyncImageViewer:
    def __init__(self, window_name="Detected Face"):
        self.window_name = window_name
        self.queue = queue.Queue(maxsize=1)  # Chỉ giữ 1 ảnh mới nhất để tránh trễ (lag)
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
    def _run(self):
        """Luồng riêng biệt chỉ làm nhiệm vụ hiển thị GUI"""
        while self.is_running:
            try:
                # Chờ lấy ảnh từ hàng đợi (timeout 0.1s để không bị block vô hạn)
                frame = self.queue.get(timeout=0.1)
                if frame is not None:
                    cv2.imshow(self.window_name, frame)
                    cv2.waitKey(1)
            except queue.Empty:
                # Nếu không có ảnh mới, vẫn duy trì sự kiện GUI
                cv2.waitKey(1)
    def show(self, frame):
        """Hàm đẩy ảnh mới vào luồng hiển thị mà không bắt luồng chính phải chờ"""
        if not self.queue.empty():
            try:
                self.queue.get_nowait()  # Bỏ ảnh cũ nếu chưa kịp vẽ
            except queue.Empty:
                pass
        self.queue.put(frame)
    def stop(self):
        self.is_running = False
        cv2.destroyAllWindows()
class FaceService:
    def __init__(self):
        print("[INFO] Đang khởi tạo InsightFace...")
        self._lock = threading.Lock()
        self.app = FaceAnalysis(
            name=MODEL_NAME,
            root=MODEL_DIR,
            providers=[
                "CUDAExecutionProvider",
                "CPUExecutionProvider"
            ]
        )
        self.app.prepare(
            ctx_id=0,
            det_size=(640,640)
        )
        print("[INFO] InsightFace đã sẵn sàng.")
        self.reload_embeddings()
    # =====================================================
    # LOAD DATABASE EMBEDDINGS
    # =====================================================
    def reload_embeddings(self):
        (
            embeddings,
            names,
            user_ids
        ) = load_embeddings()
        with self._lock:
            self.known_embeddings = embeddings
            self.known_names = names
            self.known_user_ids = user_ids
            if len(embeddings) > 0:
                self.known_matrix = np.asarray(
                    embeddings,
                    dtype=np.float32
                )
            else:
                self.known_matrix = None
        print(
            f"[INFO] Đã load {len(embeddings)} embedding."
        )
    def enhance_face(self, crop_img):
        if crop_img is None or not isinstance(crop_img, np.ndarray) or crop_img.size == 0:
            return crop_img
        # Keep the original dimensions and aspect ratio so face/person boxes remain valid.
        lab = cv2.cvtColor(crop_img, cv2.COLOR_BGR2LAB)
        luminance, a, b = cv2.split(lab)
        mean_brightness = float(np.mean(luminance))

        # Gamma > 1 darkens highlights; gamma < 1 lifts underexposed areas.
        if mean_brightness < 85:
            gamma = 0.65
        elif mean_brightness > 185:
            gamma = 1.35
        else:
            gamma = 1.0
        if gamma != 1.0:
            values = np.arange(256, dtype=np.float32) / 255.0
            table = np.clip(np.power(values, gamma) * 255.0, 0, 255).astype(np.uint8)
            luminance = cv2.LUT(luminance, table)

        # Local contrast enhancement helps faces in uneven light without changing geometry.
        clip_limit = 2.0 if mean_brightness < 85 else 1.5
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        luminance = clahe.apply(luminance)
        enhanced = cv2.cvtColor(cv2.merge((luminance, a, b)), cv2.COLOR_LAB2BGR)

        if mean_brightness < 85:
            enhanced = cv2.bilateralFilter(enhanced, d=5, sigmaColor=25, sigmaSpace=25)

        # Mild unsharp masking can improve soft focus; severe blur is still rejected downstream.
        softened = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
        enhanced = cv2.addWeighted(enhanced, 1.2, softened, -0.2, 0)
        return enhanced
    # =====================================================
    # MATCH EMBEDDING WITH DATABASE
    # =====================================================
    def match_face(self, face, abs_bbox):
        #So sánh embedding của face với Database
        target_embedding = face.embedding.reshape(1, -1)
        with self._lock:
            if self.known_matrix is None or len(self.known_matrix) == 0:
                return {
                    "name": "unknown",
                    "user_id": None,
                    "similarity": 0.0,
                    "bbox": abs_bbox,
                    "matched": False
                }
            similarities = compute_cosine_similarity(target_embedding, self.known_matrix)
            best_idx = np.argmax(similarities)
            max_similarity = float(similarities[best_idx])
            if max_similarity >= SIMILARITY_THRESHOLD:
                name = self.known_names[best_idx]
                user_id = self.known_user_ids[best_idx]
                matched = True
            else:
                name = "unknown"
                user_id = None
                matched = False
        return {
            "name": name,
            "user_id": user_id,
            "similarity": max_similarity,
            "bbox": abs_bbox,
            "matched": matched
        }
    # =====================================================
    # DIRECT FACE DETECTION AND RECOGNITION
    # =====================================================
    def recognize(self, frame):
        results = []
        # Không xử lý frame rỗng
        if frame is None or frame.size == 0:
            return results
        # Phát hiện khuôn mặt trực tiếp bằng InsightFace
        enhanced_frame = self.enhance_face(frame)
        faces = self.app.get(enhanced_frame)
        for face in faces:
            bbox = face.bbox.astype(int).tolist()
            # So sánh embedding với database
            res = self.match_face(
                face,
                bbox
            )
            results.append(res)
        return results
