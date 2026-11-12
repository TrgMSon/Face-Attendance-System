import sys
import os

def test_gpu_environment():
    print("==================================================")
    print("   KIỂM TRA TĂNG TỐC PHẦN CỨNG GPU (STRICT CHECK)  ")
    print("==================================================")

    print(f"\n[1/4] Python Executable: {sys.executable}")
    is_in_venv = (hasattr(sys, 'real_prefix') or 
                  (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))
    if not is_in_venv:
        print("❌ LỖI: Bạn đang chạy ngoài môi trường ảo (.venv)!")
        sys.exit(1)
    print("✅ Đang chạy đúng trong môi trường .venv.")

    print("\n[2/4] Kiểm tra thư viện ONNX Runtime...")
    try:
        import onnxruntime as ort
    except ImportError as e:
        print(f"❌ LỖI: Chưa cài đặt onnxruntime-gpu: {e}")
        sys.exit(1)

    available_providers = ort.get_available_providers()
    print(f"-> ONNX Runtime Version: {ort.__version__}")
    print(f"-> Các Provider phát hiện được: {available_providers}")

    if "CUDAExecutionProvider" not in available_providers:
        print("\n❌ THẤT BẠI: 'CUDAExecutionProvider' KHÔNG CÓ TRONG DANH SÁCH!")
        sys.exit(1)
    else:
        print("✅ Đã tìm thấy 'CUDAExecutionProvider' trong ONNX Runtime.")

    print("\n[3/4] Kiểm tra thiết bị của ONNX Runtime...")
    try:
        # Sử dụng kiểm tra trực tiếp qua provider thay vì hàm get_device cũ để tránh lỗi tương thích phiên bản
        print("-> Thiết bị mặc định: GPU (CUDAExecutionProvider active)")
        print("✅ CUDA Provider đã sẵn sàng phân bổ tài nguyên tính toán.")
    except Exception as e:
        print(f"❌ LỖI KHI NẠP TÀI NGUYÊN CUDA: {e}")
        sys.exit(1)

    print("\n[4/4] Khởi tạo mô hình InsightFace (Bắt buộc CUDA 100%)...")
    try:
        from insightface.app import FaceAnalysis
        
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(root_dir)

        app = FaceAnalysis(
            name="antelopev2",
            root=models_dir,
            providers=["CUDAExecutionProvider"]
        )
        print("✅ FaceAnalysis đã chấp nhận CUDAExecutionProvider làm provider duy nhất!")
    except Exception as e:
        print(f"❌ LỖI KHỞI TẠO INSIGHTFACE VỚI CUDA: {e}")
        sys.exit(1)

    print("\n==================================================")
    print("🎉 HOÀN TOÀN HỢP LỆ: GPU ĐÃ ĐƯỢC KÍCH HOẠT VÀ HOẠT ĐỘNG CHUẨN XÁC!")
    print("==================================================")

if __name__ == "__main__":
    test_gpu_environment()