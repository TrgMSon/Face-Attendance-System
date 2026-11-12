"use strict";
// =====================================================
// CONFIGURATION
// =====================================================
const MAX_CAMERAS = 1;
const MAX_ANALYSIS_DIMENSION = 960;
const JPEG_QUALITY = 0.7;
let ipWebcamUrl = "";
// =====================================================
// CAMERA STATE
// =====================================================
const cameras = {};
for (let i = 1; i <= MAX_CAMERAS; i++) {
    cameras[i] = {
        active: false,
        socket: null,
        interval: null,
        reconnectTimer: null,
        reconnectAttempts: 0,
        videoReconnectTimer: null,
        videoReconnectAttempts: 0,
        videoReady: false,
        frameInFlight: false,
        encodingFrame: false,
        faces: []
    };
}
// =====================================================
// DOM
// =====================================================
const cameraGrid =
    document.getElementById("cameraGrid");
const resultsDiv =
    document.getElementById("results");
// =====================================================
// CAMERA ELEMENTS
// =====================================================
function getCameraElements(id) {
    const card = document.getElementById(`cameraCard${id}`);
    const status = document.getElementById(`status${id}`);
    const video = document.getElementById(`video${id}`);
    const canvas = document.getElementById(`canvas${id}`);
    const overlay = document.getElementById(`overlay${id}`);
    return {
        card,
        status,
        video,
        canvas,
        overlay,
        ctx: canvas.getContext("2d"),
        overlayCtx: overlay.getContext("2d")
    };
}
// =====================================================
// CAMERA LAYOUT
// =====================================================
function updateCameraLayout() {
    const activeCards = [];
    for (let i = 1; i <= MAX_CAMERAS; i++) {
        const elements = getCameraElements(i);
        const camera = cameras[i];
        elements.card.classList.toggle("active", camera.active);
        if (camera.active) {
            activeCards.push(elements.card);
            if (camera.videoReady) {
                elements.status.textContent = "Đang chạy";
            }
        } else {
            elements.status.textContent = "Tắt";
        }
        updateButtonState(i);
    }
    const count = activeCards.length;
    cameraGrid.dataset.count = count;
    // Xóa cấu hình cột cũ
    activeCards.forEach(card => {
        card.style.gridColumn = "";
    });
}
// =====================================================
// VIDEO DIMENSIONS
// =====================================================
function setupCanvas(id, width, height) {
    const elements =
        getCameraElements(id);
    if (!width || !height) {
        return false;
    }
    elements.canvas.width = width;
    elements.canvas.height = height;
    elements.overlay.width = width;
    elements.overlay.height = height;
    return true;
}
// =====================================================
// WEBSOCKET
// =====================================================
function connectWebSocket(id) {
    const camera =
        cameras[id];
    if (camera.socket) {
        return;
    }
    const protocol =
        location.protocol === "https:"
            ? "wss:"
            : "ws:";
    const socket = new WebSocket(
        `${protocol}//${location.host}/ws/recognize?camera_id=${id}`
    );
    camera.socket = socket;
    socket.onopen = () => {
        camera.reconnectAttempts = 0;
        console.log(
            `Camera ${id}: WebSocket connected`
        );
        sendFrame(id);
    };
    socket.onmessage = event => {
        camera.frameInFlight = false;
        try {
            const data =
                JSON.parse(event.data);
            camera.faces =
                Array.isArray(data.faces)
                    ? data.faces
                    : [];
            drawFaces(id, camera.faces);
            renderResults();
            if (data.capture_still) {
                sendStillFrame(id);
                return;
            }
            sendFrame(id);
        } catch (error) {
            console.error(
                `Camera ${id}: Lỗi dữ liệu nhận diện`,
                error
            );
            sendFrame(id);
        }
    };
    socket.onerror = error => {
        console.error(
            `Camera ${id}: WebSocket error`,
            error
        );
    };
    socket.onclose = () => {
        if (camera.socket !== socket) {
            return;
        }
        console.log(
            `Camera ${id}: WebSocket disconnected`
        );
        if (camera.interval) {
            clearInterval(camera.interval);
            camera.interval = null;
        }
        camera.frameInFlight = false;
        camera.encodingFrame = false;
        camera.socket = null;
        if (camera.active && !camera.reconnectTimer) {
            const delay = Math.min(10000, 500 * (2 ** camera.reconnectAttempts));
            camera.reconnectAttempts += 1;
            camera.reconnectTimer = setTimeout(() => {
                camera.reconnectTimer = null;
                if (camera.active) {
                    connectWebSocket(id);
                }
            }, delay);
        }
    };
}
// =====================================================
// SEND FRAME
// =====================================================
function sendFrame(id) {
    const camera =
        cameras[id];
    const elements =
        getCameraElements(id);
    const socket =
        camera.socket;
    if (
        !camera.active ||
        camera.frameInFlight ||
        camera.encodingFrame ||
        !socket ||
        socket.readyState !== WebSocket.OPEN
    ) {
        return;
    }
    const source = elements.video;
    const width = source.naturalWidth;
    const height = source.naturalHeight;
    if (!width || !height) {
        return;
    }
    const scale = Math.min(1, MAX_ANALYSIS_DIMENSION / Math.max(width, height));
    const analysisWidth = Math.max(1, Math.round(width * scale));
    const analysisHeight = Math.max(1, Math.round(height * scale));
    if (elements.canvas.width !== analysisWidth || elements.canvas.height !== analysisHeight) {
        elements.canvas.width = analysisWidth;
        elements.canvas.height = analysisHeight;
    }
    if (elements.overlay.width !== width || elements.overlay.height !== height) {
        elements.overlay.width = width;
        elements.overlay.height = height;
    }
    const ctx =
        elements.ctx;
    ctx.drawImage(source, 0, 0, analysisWidth, analysisHeight);
    camera.encodingFrame = true;
    elements.canvas.toBlob(
        blob => {
            camera.encodingFrame = false;
            if (
                blob &&
                camera.active &&
                camera.socket &&
                camera.socket.readyState === WebSocket.OPEN
            ) {
                camera.frameInFlight = true;
                camera.socket.send(blob);
            }
        },
        "image/jpeg",
        JPEG_QUALITY
    );
}
function sendStillFrame(id) {
    const camera = cameras[id];
    const elements = getCameraElements(id);
    const source = elements.video;
    const width = source.naturalWidth;
    const height = source.naturalHeight;
    const socket = camera.socket;
    if (
        !camera.active ||
        !socket ||
        socket.readyState !== WebSocket.OPEN
    ) {
        return;
    }
    if (!width || !height) {
        socket.send(JSON.stringify({ type: "still_failed" }));
        sendFrame(id);
        return;
    }

    const stillCanvas = document.createElement("canvas");
    stillCanvas.width = width;
    stillCanvas.height = height;
    const stillContext = stillCanvas.getContext("2d");
    if (!stillContext) {
        socket.send(JSON.stringify({ type: "still_failed" }));
        sendFrame(id);
        return;
    }
    try {
        stillContext.drawImage(source, 0, 0, width, height);
        camera.encodingFrame = true;
        stillCanvas.toBlob(blob => {
            camera.encodingFrame = false;
            if (
                !camera.active ||
                !camera.socket ||
                camera.socket.readyState !== WebSocket.OPEN
            ) {
                return;
            }
            if (blob) {
                camera.socket.send(blob);
            } else {
                camera.socket.send(JSON.stringify({ type: "still_failed" }));
            }
            sendFrame(id);
        }, "image/jpeg", 0.85);
    } catch (error) {
        camera.encodingFrame = false;
        console.error(`Camera ${id}: Không thể mã hóa frame độ phân giải gốc`, error);
        if (
            camera.active &&
            camera.socket === socket &&
            socket.readyState === WebSocket.OPEN
        ) {
            socket.send(JSON.stringify({ type: "still_failed" }));
            sendFrame(id);
        }
    }
}
// =====================================================
// DRAW FACES
// =====================================================
function drawFaces(id, faces) {
    const elements =
        getCameraElements(id);
    const overlayCtx =
        elements.overlayCtx;
    const scaleX = elements.overlay.width / Math.max(elements.canvas.width, 1);
    const scaleY = elements.overlay.height / Math.max(elements.canvas.height, 1);
    overlayCtx.clearRect(
        0,
        0,
        elements.overlay.width,
        elements.overlay.height
    );
    faces.forEach(face => {
        if (!face.matched) {
            return;
        }
        const [
            x1,
            y1,
            x2,
            y2
        ] = face.bbox;
        const mirroredX1 = elements.overlay.width - x2 * scaleX;
        const mirroredX2 = elements.overlay.width - x1 * scaleX;
        const scaledY1 = y1 * scaleY;
        const scaledY2 = y2 * scaleY;

        overlayCtx.lineWidth = 3;
        overlayCtx.strokeStyle = face.matched
            ? "lime"
            : face.candidate
                ? "orange"
                : "white";
        overlayCtx.strokeRect(
            mirroredX1,
            scaledY1,
            mirroredX2 - mirroredX1,
            scaledY2 - scaledY1
        );
        const similarity =
            Number(face.similarity || 0);
        const label = face.track_id !== undefined
            ? `#${face.track_id} ${face.name} (${similarity.toFixed(2)})`
            : `${face.name} (${similarity.toFixed(2)})`;
        overlayCtx.font =
            "18px Arial";
        overlayCtx.fillStyle = overlayCtx.strokeStyle;
        overlayCtx.fillText(
            label,
            mirroredX1,
            Math.max(20, y1 - 10)
        );
    });
}
// =====================================================
// RENDER RESULTS
// =====================================================
function renderResults() {
    resultsDiv.innerHTML = "";
    let totalFaces = 0;
    for (let i = 1; i <= MAX_CAMERAS; i++) {
        const camera =
            cameras[i];
        if (!camera.active) {
            continue;
        }
        totalFaces += camera.faces.length;
        camera.faces.forEach(face => {
            if (!face.matched)
                return;
            
            const div =
                document.createElement("div");
            div.className =
                face.matched
                    ? "person matched"
                    : "person unknown";
            let status =
                face.matched
                    ? "Đã nhận diện"
                    : "Không hợp lệ";
            if (face.status === "pending") {
                status = "Đang nhận diện tầm xa";
            } else if (face.candidate) {
                status = "Ứng viên, cần xác nhận";
            }
            if (face.attendance_logged) {
                status = "Đã điểm danh";
            }
            const title =
                document.createElement("h3");
            title.textContent =
                `Camera ${i}: ${face.name}`;
            const similarity =
                document.createElement("p");
            similarity.textContent =
                `Similarity: ${Number(face.similarity || 0).toFixed(3)}`;
            const statusElement =
                document.createElement("p");
            statusElement.textContent =
                `Trạng thái: ${status}`;
            div.appendChild(title);
            div.appendChild(similarity);
            div.appendChild(statusElement);
            resultsDiv.appendChild(div);
        });
    }
    if (totalFaces === 0) {
        resultsDiv.innerHTML =
            "<p>Không phát hiện khuôn mặt.</p>";
    }
}
// =====================================================
// START IP WEBCAM
// =====================================================
async function startIPCamera(id) {
    const camera =
        cameras[id];
    const elements =
        getCameraElements(id);
    stopCamera(id);
    let videoUrl;
    try {
        const response = await fetch("/api/camera-config");
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        ({ video_url: videoUrl } = await response.json());
    } catch (error) {
        alert("Không lấy được địa chỉ video IP Webcam từ backend.");
        console.error("Camera config error:", error);
        return;
    }
    if (!videoUrl) {
        alert("Chưa cấu hình URL video IP Webcam.");
        return;
    }
    ipWebcamUrl = videoUrl.replace(/\/video\/?$/, "");
    camera.active = true;
    camera.videoReady = false;
    updateCameraLayout();
    elements.video.style.display = "block";
    elements.video.onload = () => {
        if (!camera.active) {
            return;
        }
        camera.videoReconnectAttempts = 0;
        if (camera.videoReconnectTimer) {
            clearTimeout(camera.videoReconnectTimer);
            camera.videoReconnectTimer = null;
        }
        const width =
            elements.video.naturalWidth;
        const height =
            elements.video.naturalHeight;
        if (!setupCanvas(id, width, height)) {
            return;
        }
        camera.videoReady = true;
        updateCameraLayout();
        sendFrame(id);
    };
    elements.video.onerror = () => {
        console.error(
            `Camera ${id}: Không thể tải IP Webcam`
        );
        elements.status.textContent = "Lỗi";
    };
    if (camera.videoErrorHandler) {
        elements.video.removeEventListener("error", camera.videoErrorHandler);
    }
    camera.videoErrorHandler = () => {
        if (!camera.active || camera.videoReconnectTimer) {
            return;
        }
        const delay = Math.min(10000, 500 * (2 ** camera.videoReconnectAttempts));
        camera.videoReconnectAttempts += 1;
        camera.videoReconnectTimer = setTimeout(() => {
            camera.videoReconnectTimer = null;
            if (!camera.active) {
                return;
            }
            const retryUrl = new URL(videoUrl, location.href);
            retryUrl.searchParams.set("_reconnect", Date.now());
            elements.video.src = retryUrl.toString();
        }, delay);
    };
    elements.video.addEventListener("error", camera.videoErrorHandler);
    elements.video.src = videoUrl;
    connectWebSocket(id);
}
// =====================================================
// STOP CAMERA
// =====================================================
function stopCamera(id) {
    const camera =
        cameras[id];
    const elements =
        getCameraElements(id);
    camera.active = false;
    camera.videoReady = false;
    camera.frameInFlight = false;
    camera.encodingFrame = false;
    camera.faces = [];
    if (camera.reconnectTimer) {
        clearTimeout(camera.reconnectTimer);
        camera.reconnectTimer = null;
    }
    camera.reconnectAttempts = 0;
    if (camera.videoReconnectTimer) {
        clearTimeout(camera.videoReconnectTimer);
        camera.videoReconnectTimer = null;
    }
    camera.videoReconnectAttempts = 0;
    if (camera.interval) {
        clearInterval(camera.interval);
        camera.interval = null;
    }
    if (camera.socket) {
        camera.socket.close();
        camera.socket = null;
    }
    elements.video.removeAttribute("src");
    elements.overlayCtx.clearRect(
        0,
        0,
        elements.overlay.width,
        elements.overlay.height
    );
    updateCameraLayout();
    renderResults();
}
// =====================================================
// STOP ALL CAMERAS
// =====================================================
function stopAllCameras() {
    for (let i = 1; i <= MAX_CAMERAS; i++) {
        stopCamera(i);
    }
}
// =====================================================
// TOGGLE CAMERA
// =====================================================
async function toggleCamera(id) {
    const camera =
        cameras[id];
    if (camera.active) {
        stopCamera(id);
        return;
    }
    await startIPCamera(id);
}
// =====================================================
// BUTTON STATE
// =====================================================
function updateButtonState(id) {
    const button =
        document.getElementById(
            `toggleCamera${id}`
        );
    if (!button) {
        return;
    }
    const active =
        cameras[id].active;
    button.textContent =
        active ? "Tắt" : "Bật";
    button.classList.toggle(
        "active",
        active
    );
}
// =====================================================
// PATCH LAYOUT STATE
// =====================================================
// =====================================================
// BUTTON EVENTS
// =====================================================
for (let i = 1; i <= MAX_CAMERAS; i++) {
    const button =
        document.getElementById(
            `toggleCamera${i}`
        );
    if (!button) {
        continue;
    }
    button.addEventListener(
        "click",
        async () => {
            await toggleCamera(i);
            updateButtonState(i);
        }
    );
}
document
    .getElementById("stopAll")
    .addEventListener(
        "click",
        () => {
            stopAllCameras();
            for (let i = 1; i <= MAX_CAMERAS; i++) {
                updateButtonState(i);
            }
        }
    );
// =====================================================
// ZOOM
// =====================================================
let currentZoom = 0;
async function setCameraZoom(zoomValue) {
    const url =
        `${ipWebcamUrl}/ptz?zoom=${zoomValue}`;
    if (!ipWebcamUrl) {
        console.warn("Bật IP Webcam trước khi thay đổi zoom.");
        return;
    }
    try {
        const response =
            await fetch(url, {
                method: "GET",
                mode: "cors"
            });
        if (response.ok) {
            console.log(
                `Đã thay đổi zoom thành công: ${zoomValue}`
            );
        } else {
            console.error(
                "Lỗi khi gửi lệnh zoom:",
                response.statusText
            );
        }
    } catch (error) {
        console.error(
            "Không thể kết nối tới IP Webcam để điều chỉnh zoom:",
            error
        );
    }
}
function zoomIn() {
    if (currentZoom < 100) {
        currentZoom += 10;
        setCameraZoom(currentZoom);
    }
}
function zoomOut() {
    if (currentZoom > 0) {
        currentZoom -= 10;
        setCameraZoom(currentZoom);
    }
}
document
    .getElementById("zoomIn")
    .addEventListener(
        "click",
        zoomIn
    );
document
    .getElementById("zoomOut")
    .addEventListener(
        "click",
        zoomOut
    );
// =====================================================
// INITIALIZE
// =====================================================
for (let i = 1; i <= MAX_CAMERAS; i++) {
    updateButtonState(i);
}
updateCameraLayout();
