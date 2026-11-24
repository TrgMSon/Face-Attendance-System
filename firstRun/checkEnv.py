import sys
import os
import importlib.util
from importlib.metadata import version, PackageNotFoundError
import traceback

def check_environment():
    print("=" * 65)
    print("=== KIỂM TRA MÔI TRƯỜNG FACE ATTENDANCE ===")
    print("=" * 65)

    # =========================================================
    # [1/4] KIỂM TRA VIRTUALENV
    # =========================================================

    print("\n" + "=" * 65)
    print("=== [1/4] KIỂM TRA MÔI TRƯỜNG THỰC THI (VIRTUALENV) ===")
    print("=" * 65)

    current_python = sys.executable

    is_in_venv = (
        hasattr(sys, "real_prefix")
        or (
            hasattr(sys, "base_prefix")
            and sys.base_prefix != sys.prefix
        )
    )

    if not is_in_venv:
        print("[CẢNH BÁO] Bạn chưa chạy trong môi trường ảo (.venv)!")
        print(f"[-] Python hiện tại: {current_python}")
        sys.exit(1)

    print(f"[OK] Đang chạy trong .venv: {sys.prefix}")
    print(f"[OK] Python executable: {current_python}")
    print(f"[OK] Python version: {sys.version.split()[0]}")

    # =========================================================
    # [2/4] KIỂM TRA THƯ VIỆN
    # =========================================================

    print("\n" + "=" * 65)
    print("=== [2/4] KIỂM TRA DANH SÁCH THƯ VIỆN CỐT LÕI ===")
    print("=" * 65)

    packages_to_check = [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("python-dotenv", "dotenv"),
        ("python-multipart", "multipart"),
        ("numpy", "numpy"),
        ("opencv-python", "cv2"),
        ("scikit-learn", "sklearn"),
        ("mysql-connector-python", "mysql.connector"),
        ("cloudinary", "cloudinary"),
        ("insightface", "insightface"),
        ("onnxruntime-gpu", "onnxruntime"),
    ]

    missing_count = 0

    for package_name, module_name in packages_to_check:
        try:
            module_spec = importlib.util.find_spec(module_name)

            if module_spec is None:
                print(
                    f"[-] THIẾU: {package_name} "
                    f"(Module: {module_name})"
                )
                missing_count += 1
            else:
                try:
                    package_version = version(package_name)
                    print(
                        f"[+] ĐÃ SẴN SÀNG: "
                        f"{package_name} ({package_version})"
                    )
                except PackageNotFoundError:
                    print(f"[+] ĐÃ SẴN SÀNG: {package_name}")

        except Exception as error:
            print(f"[-] LỖI kiểm tra {package_name}: {error}")
            missing_count += 1

    if missing_count > 0:
        print(
            f"\n[CẢNH BÁO] Có "
            f"{missing_count} thư viện chưa được cài đặt!"
        )
    else:
        print(
            "\n[OK] Toàn bộ thư viện cốt lõi "
            "đã được tìm thấy."
        )

    # =========================================================
    # KIỂM TRA CÁC GÓI NVIDIA
    # =========================================================

    print("\n" + "-" * 65)
    print("=== KIỂM TRA NVIDIA CUDA/cuDNN PACKAGES ===")
    print("-" * 65)

    nvidia_packages = [
        "nvidia-cuda-runtime-cu12",
        "nvidia-cuda-runtime-cu13",
        "nvidia-cudnn-cu12",
        "nvidia-cudnn-cu13",
        "nvidia-cublas-cu12",
        "nvidia-cublas-cu13",
        "nvidia-cuda-nvrtc-cu12",
        "nvidia-cuda-nvrtc-cu13",
    ]

    for package_name in nvidia_packages:
        try:
            package_version = version(package_name)
            print(f"[+] {package_name}: {package_version}")
        except PackageNotFoundError:
            print(f"[-] Không có: {package_name}")

    # =========================================================
    # [3/4] KIỂM TRA MODEL ANTELOPEV2
    # =========================================================

    print("\n" + "=" * 65)
    print("=== [3/4] KIỂM TRA MODEL (ANTELOPEV2) ===")
    print("=" * 65)

    project_dir = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
    model_dir = os.path.join(
        project_dir,
        "models",
        "antelopev2"
    )

    detector = os.path.join(
        model_dir,
        "scrfd_10g_bnkps.onnx"
    )

    recognizer = os.path.join(
        model_dir,
        "glintr100.onnx"
    )

    print(f"[*] Thư mục model: {model_dir}")

    if os.path.exists(detector):
        detector_size = os.path.getsize(detector) / (1024 * 1024)

        print(
            f"[+] Detector: scrfd_10g_bnkps.onnx "
            f"({detector_size:.1f} MB)"
        )
    else:
        print(
            "[-] THIẾU DETECTOR: "
            "models/antelopev2/scrfd_10g_bnkps.onnx"
        )

    if os.path.exists(recognizer):
        recognizer_size = os.path.getsize(recognizer) / (1024 * 1024)

        print(
            f"[+] Recognizer: glintr100.onnx "
            f"({recognizer_size:.1f} MB)"
        )
    else:
        print(
            "[-] THIẾU RECOGNIZER: "
            "models/antelopev2/glintr100.onnx"
        )

    # =========================================================
    # [4/4] KIỂM TRA CUDA RUNTIME VÀ ONNX RUNTIME
    # =========================================================

    print("\n" + "=" * 65)
    print("=== [4/4] KIỂM TRA CUDA RUNTIME CHO ONNX RUNTIME ===")
    print("=" * 65)

    try:
        import onnxruntime as ort

        print(f"[*] ONNX Runtime version: {ort.__version__}")
        print(f"[*] ONNX Runtime location: {ort.__file__}")
        print(f"[*] Python đang sử dụng: {sys.executable}")

        # -----------------------------------------------------
        # Kiểm tra preload DLL
        # -----------------------------------------------------

        print("\n[*] Đang nạp DLL CUDA/cuDNN...")

        try:
            ort.preload_dlls(directory="")

            print("[+] preload_dlls() đã được gọi thành công.")

        except Exception as error:
            print(
                "[CẢNH BÁO] Không thể preload DLL CUDA/cuDNN:"
            )
            print(f"[-] Chi tiết: {error}")

        # -----------------------------------------------------
        # Kiểm tra Execution Providers
        # -----------------------------------------------------

        print("\n[*] Đang kiểm tra Execution Providers...")

        available_providers = ort.get_available_providers()

        print(
            f"[*] Providers hiện có: "
            f"{available_providers}"
        )

        if "CUDAExecutionProvider" in available_providers:
            print(
                "[OK] Đã tìm thấy CUDAExecutionProvider "
                "trong ONNX Runtime."
            )
        else:
            print(
                "[FAIL] Không tìm thấy CUDAExecutionProvider."
            )

            print(
                "[INFO] ONNX Runtime hiện tại "
                "chưa nhận diện được CUDA."
            )

            print(
                "[INFO] Kiểm tra lại phiên bản CUDA, "
                "cuDNN và ONNX Runtime."
            )

            print(
                "[INFO] Có thể môi trường đang sử dụng "
                "bản ONNX Runtime CPU."
            )

            sys.exit(1)

        # -----------------------------------------------------
        # Kiểm tra thiết bị mặc định
        # -----------------------------------------------------

        print("\n[*] Kiểm tra thiết bị ONNX Runtime...")

        try:
            device = ort.get_device()
            print(f"[+] Thiết bị ONNX Runtime: {device}")

        except Exception as error:
            print(
                f"[CẢNH BÁO] Không thể kiểm tra thiết bị: "
                f"{error}"
            )

        # -----------------------------------------------------
        # Kiểm tra khởi tạo InsightFace
        # -----------------------------------------------------

        print("\n" + "-" * 65)
        print("=== KIỂM TRA KHỞI TẠO INSIGHTFACE VỚI CUDA ===")
        print("-" * 65)

        try:
            from insightface.app import FaceAnalysis

            print("[*] Đang khởi tạo FaceAnalysis...")

            app = FaceAnalysis(
                name="antelopev2",
                root=os.path.join(
                    project_dir,
                ),
                providers=[
                    "CUDAExecutionProvider"
                ]
            )

            print(
                "[+] FaceAnalysis đã được khởi tạo "
                "với CUDAExecutionProvider."
            )

            print(
                "[INFO] Lưu ý: Khởi tạo FaceAnalysis "
                "chưa đảm bảo model đã chạy trên GPU."
            )

            # -------------------------------------------------
            # Chuẩn bị model trên GPU
            # -------------------------------------------------

            print("\n[*] Đang prepare InsightFace trên GPU...")

            app.prepare(
                ctx_id=0,
                det_size=(640, 640)
            )

            print(
                "[OK] InsightFace đã prepare thành công "
                "với ctx_id=0."
            )

        except Exception as error:
            print(
        "[-] LỖI KHỞI TẠO HOẶC PREPARE INSIGHTFACE:")
            print(f"[-] Loại lỗi: {type(error).__name__}")
            print(f"[-] Chi tiết: {error}")

            print("\n[TRACEBACK CHI TIẾT]")
            traceback.print_exc()

            sys.exit(1)

    except ImportError as error:
        print(
            "[-] Không thể import onnxruntime."
        )
        print(f"[-] Chi tiết: {error}")

        sys.exit(1)

    except Exception as error:
        print(
            "[-] LỖI KHI KIỂM TRA ONNX RUNTIME:"
        )
        print(f"[-] Chi tiết: {error}")

        sys.exit(1)

    # =========================================================
    # KẾT QUẢ CUỐI CÙNG
    # =========================================================

    print("\n" + "=" * 65)
    print("HOÀN TẤT KIỂM TRA MÔI TRƯỜNG")
    print("=" * 65)

    print("[OK] Virtualenv hợp lệ.")
    print("[OK] Thư viện đã được kiểm tra.")
    print("[OK] Model AntelopeV2 đã được kiểm tra.")
    print("[OK] CUDAExecutionProvider đã được tìm thấy.")
    print("[OK] InsightFace đã prepare thành công trên GPU.")

    print("\nGPU CUDA đã sẵn sàng cho Face Attendance.")
    print("=" * 65)


if __name__ == "__main__":
    check_environment()