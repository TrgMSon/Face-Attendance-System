"""Face-first long-range tracking and recognition pipeline."""

import math
import queue
import threading
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from backend.config import SIMILARITY_THRESHOLD
from backend.face_service import compute_cosine_similarity


STREAM_FACE_CONF = 0.35
MIN_STREAM_FACE_PX = 8
MIN_TRACK_CONFIRMATIONS = 2
ANALYZE_EVERY_N_FRAMES = 2
TRACK_HOLD_FRAMES = 5
RETRY_COOLDOWN = 2.0
MAX_ATTEMPTS = 6
MAX_REJECTS = 10
MAX_TARGETS_PER_SHOT = 2
MIN_STILL_REQUEST_INTERVAL = 1.0
FACE_CROP_SCALE_X = 2.5
FACE_CROP_SCALE_Y = 3.0
MIN_FACE_PX = 40
MIN_SHARPNESS = 30.0
POSSIBLE_MARGIN = 0.08
TRACK_TTL = 60.0
CLEANUP_EVERY = 10.0


@dataclass
class TrackState:
    embs: list = field(default_factory=list)
    weights: list = field(default_factory=list)
    attempts: int = 0
    rejects: int = 0
    last_try: float = 0.0
    last_seen: float = field(default_factory=time.time)
    status: str = "pending"
    name: str = ""
    user_id: object = None
    similarity: float = 0.0
    face_px: int = 0
    last_box: object = None
    missed_frames: int = 0
    seen_frames: int = 0


def compute_iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
    area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
    union = area_a + area_b - intersection
    return intersection / union if union else 0.0


def centroid_distance(a, b):
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return math.hypot(ax - bx, ay - by)


def assign_face_tracks(detections, states):
    """Greedily associate current face boxes with recently seen face tracks."""
    pairs = []
    for detection_index, detection in enumerate(detections):
        width = max(detection[2] - detection[0], 1.0)
        height = max(detection[3] - detection[1], 1.0)
        diagonal = max(math.hypot(width, height), 1.0)
        for track_id, state in states.items():
            if state.last_box is None or state.missed_frames > TRACK_HOLD_FRAMES:
                continue
            previous = state.last_box
            previous_width = max(previous[2] - previous[0], 1.0)
            previous_height = max(previous[3] - previous[1], 1.0)
            size_ratio = (width * height) / (previous_width * previous_height)
            if not 0.25 <= size_ratio <= 4.0:
                continue
            distance = centroid_distance(detection, previous) / diagonal
            iou = compute_iou(detection, previous)
            if iou < 0.01 and distance > 2.5:
                continue
            pairs.append((iou - 0.15 * distance, detection_index, track_id))

    assignments = {}
    used_tracks = set()
    for _, detection_index, track_id in sorted(pairs, reverse=True):
        if detection_index in assignments or track_id in used_tracks:
            continue
        assignments[detection_index] = track_id
        used_tracks.add(track_id)
    return assignments


def sharpness(gray_face):
    resized = cv2.resize(gray_face, (112, 112), interpolation=cv2.INTER_AREA)
    return float(cv2.Laplacian(resized, cv2.CV_64F).var())


class StillWorker(threading.Thread):
    """Recognize tracked faces in high-resolution frames supplied by the frontend."""

    def __init__(self, service, states, lock):
        super().__init__(daemon=True)
        self.service = service
        self.states = states
        self.lock = lock
        self.jobs = queue.Queue(maxsize=1)
        self.busy = threading.Event()
        self.submit_lock = threading.Lock()
        self.pending_job = None
        self.last_submit_at = 0.0
        self.warned_ratio = False

    def submit(self, targets, stream_shape):
        with self.submit_lock:
            now = time.monotonic()
            if (
                self.busy.is_set()
                or now - self.last_submit_at < MIN_STILL_REQUEST_INTERVAL
            ):
                return False
            self.busy.set()
            self.pending_job = (targets, stream_shape)
            self.last_submit_at = now
            return True

    def has_pending_still(self):
        with self.submit_lock:
            return self.pending_job is not None

    def provide_still(self, still):
        with self.submit_lock:
            if self.pending_job is None:
                return False
            targets, stream_shape = self.pending_job
            self.pending_job = None
            self.jobs.put_nowait((targets, stream_shape, still))
            return True

    def cancel_pending_still(self):
        with self.submit_lock:
            if self.pending_job is None:
                return False
            self.pending_job = None
            self.busy.clear()
            return True

    def run(self):
        while True:
            job = self.jobs.get()
            try:
                self.process_job(*job)
            except Exception as error:
                print(f"[WARN] Long-range still worker failed: {error}")
            finally:
                self.busy.clear()

    def process_job(self, targets, stream_shape, still):
        still_h, still_w = still.shape[:2]
        stream_h, stream_w = stream_shape[:2]
        if not self.warned_ratio and abs(still_w / still_h - stream_w / stream_h) > 0.05:
            print("[WARN] Tỷ lệ frame video và frame gốc khác nhau; ghép khuôn mặt có thể kém chính xác.")
            self.warned_ratio = True
        scale_x, scale_y = still_w / stream_w, still_h / stream_h

        for track_id, stream_box in targets:
            box = np.asarray(stream_box, dtype=np.float32)
            center_x = (box[0] + box[2]) * 0.5 * scale_x
            center_y = (box[1] + box[3]) * 0.5 * scale_y
            face_width = max((box[2] - box[0]) * scale_x, 1.0)
            face_height = max((box[3] - box[1]) * scale_y, 1.0)
            half_width = face_width * FACE_CROP_SCALE_X
            half_height = face_height * FACE_CROP_SCALE_Y
            x1 = max(0, int(center_x - half_width))
            y1 = max(0, int(center_y - half_height))
            x2 = min(still_w, int(center_x + half_width))
            y2 = min(still_h, int(center_y + half_height))
            crop = still[y1:y2, x1:x2]
            if crop.size == 0:
                self.record(track_id, "rejected")
                continue
            crop = self.service.enhance_face(crop)

            with self.service._lock:
                faces = self.service.app.get(crop)
            faces = [face for face in faces if float(face.det_score) >= STREAM_FACE_CONF]
            if not faces:
                self.record(track_id, "rejected")
                continue

            center_x, center_y = crop.shape[1] / 2, crop.shape[0] / 2
            face = min(
                faces,
                key=lambda item: (
                    ((item.bbox[0] + item.bbox[2]) / 2 - center_x) ** 2
                    + ((item.bbox[1] + item.bbox[3]) / 2 - center_y) ** 2
                ),
            )
            self.record(track_id, self.update(track_id, crop, face))

    def record(self, track_id, outcome):
        with self.lock:
            state = self.states.get(track_id)
            if state is None:
                return
            if outcome == "rejected":
                state.rejects += 1
            else:
                state.attempts += 1
            if state.status == "pending" and (
                state.attempts >= MAX_ATTEMPTS or state.rejects >= MAX_REJECTS
            ):
                state.status = "unknown"

    def update(self, track_id, crop, face):
        face_x1, face_y1, face_x2, face_y2 = [int(value) for value in face.bbox]
        face_width = face_x2 - face_x1
        face_crop = crop[max(0, face_y1):face_y2, max(0, face_x1):face_x2]
        if face_crop.size == 0:
            return "rejected"
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        face_sharpness = sharpness(gray)
        if face_sharpness < MIN_SHARPNESS:
            return "rejected"

        weight = (
            float(face.det_score)
            * min(face_width, 100) / 100
            * min(face_sharpness, 100) / 100
            + 1e-3
        )
        embedding = face.normed_embedding.astype(np.float32)
        with self.lock:
            state = self.states.get(track_id)
            if state is None:
                return "ok"
            state.embs.append(embedding)
            state.weights.append(weight)
            state.face_px = max(state.face_px, face_width)
            mean_embedding = np.average(np.stack(state.embs), axis=0, weights=state.weights)
            mean_embedding /= max(np.linalg.norm(mean_embedding), 1e-10)

        with self.service._lock:
            matrix = self.service.known_matrix
            if matrix is None or len(matrix) == 0:
                return "ok"
            similarities = compute_cosine_similarity(mean_embedding, matrix)
            best_index = int(np.argmax(similarities))
            similarity = float(similarities[best_index])
            name = self.service.known_names[best_index]
            user_id = self.service.known_user_ids[best_index]

        with self.lock:
            state = self.states.get(track_id)
            if state is None:
                return "ok"
            state.similarity = similarity
            if similarity >= SIMILARITY_THRESHOLD and state.face_px >= MIN_FACE_PX:
                state.status, state.name, state.user_id = "match", name, user_id
            elif similarity >= SIMILARITY_THRESHOLD - POSSIBLE_MARGIN:
                state.status, state.name, state.user_id = "candidate", name, user_id
            else:
                state.status, state.name, state.user_id = "pending", "", None
        return "ok"


class LongRangePipeline:
    """Detect and track faces in video, then identify them from full-resolution frames."""

    def __init__(self, face_service):
        self.service = face_service
        self.states = {}
        self.lock = threading.Lock()
        self.worker = StillWorker(face_service, self.states, self.lock)
        self.worker.start()
        self.next_track_id = 1
        self.last_cleanup = time.time()
        self.frame_counter = 0

    def process(self, frame):
        self.frame_counter += 1
        if (self.frame_counter - 1) % ANALYZE_EVERY_N_FRAMES:
            return self._current_results()

        enhanced_frame = self.service.enhance_face(frame)
        if not self.service._lock.acquire(blocking=False):
            return self._current_results()
        try:
            detected_faces = self.service.app.get(enhanced_frame)
        finally:
            self.service._lock.release()
        detections = []
        for face in detected_faces:
            if float(face.det_score) < STREAM_FACE_CONF:
                continue
            box = np.asarray(face.bbox, dtype=np.float32)
            if min(box[2] - box[0], box[3] - box[1]) < MIN_STREAM_FACE_PX:
                continue
            detections.append(box)

        now = time.time()
        candidates = []
        with self.lock:
            assignments = assign_face_tracks(detections, self.states)
            for track_id, state in self.states.items():
                if state.last_box is not None:
                    state.missed_frames += 1

            for detection_index, box in enumerate(detections):
                track_id = assignments.get(detection_index)
                if track_id is None:
                    track_id = self.next_track_id
                    self.next_track_id += 1
                    self.states[track_id] = TrackState()
                state = self.states[track_id]
                state.last_seen = now
                state.last_box = box.copy()
                state.missed_frames = 0
                state.seen_frames += 1
                if (
                    state.seen_frames >= MIN_TRACK_CONFIRMATIONS
                    and state.status not in ("match", "unknown")
                    and state.attempts < MAX_ATTEMPTS
                    and state.rejects < MAX_REJECTS
                    and now - state.last_try >= RETRY_COOLDOWN
                ):
                    candidates.append((state.attempts + state.rejects, track_id, box))

            if now - self.last_cleanup >= CLEANUP_EVERY:
                self.last_cleanup = now
                expired = [
                    track_id for track_id, state in self.states.items()
                    if now - state.last_seen > TRACK_TTL
                ]
                for track_id in expired:
                    del self.states[track_id]

        if candidates:
            candidates.sort(key=lambda item: item[0])
            chosen = candidates[:MAX_TARGETS_PER_SHOT]
            submitted = self.worker.submit(
                [(track_id, box.tolist()) for _, track_id, box in chosen],
                enhanced_frame.shape,
            )
            if submitted:
                with self.lock:
                    for _, track_id, _ in chosen:
                        if track_id in self.states:
                            self.states[track_id].last_try = now

        return self._current_results()

    def _current_results(self):
        results = []
        with self.lock:
            for track_id, state in self.states.items():
                if state.last_box is None or state.missed_frames > TRACK_HOLD_FRAMES:
                    continue
                results.append({
                    "track_id": track_id,
                    "name": state.name or "unknown",
                    "user_id": state.user_id,
                    "similarity": state.similarity,
                    "bbox": state.last_box.astype(int).tolist(),
                    "matched": state.status == "match",
                    "candidate": state.status == "candidate",
                    "status": state.status,
                    "face_px": state.face_px,
                })
        return results

    def has_pending_still(self):
        return self.worker.has_pending_still()

    def provide_still(self, frame):
        return self.worker.provide_still(frame)

    def cancel_pending_still(self):
        return self.worker.cancel_pending_still()
