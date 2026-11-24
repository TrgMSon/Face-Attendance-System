
"""
Install packages for Face Attendance project.

This script uses the Python environment created by create_environment.py.

Project structure:
    HTTM2/
    ├── .venv/
    ├── backend/
    ├── frontend/
    ├── models/
    ├── runtime/
    └── firstRun/
        ├── setup_venv.py
        └── setup_package.py

"""

from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"

MODEL_DIR = PROJECT_ROOT / "models" / "antelopev2"
MODEL_ARCHIVE = PROJECT_ROOT / "models" / "antelopev2.zip"

ANTELOPE_URL = (
    "https://huggingface.co/MonsterMMORPG/tools/resolve/main/"
    "antelopev2.zip"
)


CORE_REQUIREMENTS = [
    "fastapi",
    "uvicorn[standard]",
    "python-dotenv",
    "python-multipart",
    "numpy",
    "opencv-python",
    "scikit-learn",
    "mysql-connector-python",
    "cloudinary",
    "insightface",
    "requests"
]


REQUIRED_MODULES = [
    "fastapi",
    "uvicorn",
    "dotenv",
    "multipart",
    "numpy",
    "cv2",
    "sklearn",
    "mysql.connector",
    "cloudinary",
    "insightface",
    "onnxruntime",
    "requests",
]


MODEL_FILES = [
    "scrfd_10g_bnkps.onnx",
    "glintr100.onnx",
]


# ============================================================
# UTILITIES
# ============================================================

def run(command: list[str], *, check: bool = True) -> None:
    """Run a command and display it."""

    printable_command = " ".join(
        f'"{item}"' if " " in str(item) else str(item)
        for item in command
    )

    print(f"\n> {printable_command}")

    subprocess.run(
        command,
        check=check,
    )


def ensure_venv_exists() -> None:
    """Check whether the project virtual environment exists."""

    if not VENV_PYTHON.exists():
        raise RuntimeError(
            "Không tìm thấy Python trong .venv.\n"
            f"Expected: {VENV_PYTHON}\n\n"
            "Hãy chạy create_environment.py trước."
        )

    print(f"[OK] Virtual environment: {VENV_DIR}")
    print(f"[OK] Python executable: {VENV_PYTHON}")


def download_file(url: str, destination: Path) -> None:
    """Download a file if it does not already exist."""

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        print(f"[SKIP] File đã tồn tại: {destination}")
        return

    print(f"[DOWNLOAD] {url}")

    def reporthook(
        block_number: int,
        block_size: int,
        total_size: int,
    ) -> None:
        downloaded = block_number * block_size

        if total_size > 0:
            percentage = downloaded * 100 / total_size

            print(
                f"\r -> Tiến độ: {percentage:.1f}% "
                f"({downloaded / (1024 * 1024):.1f} MB / "
                f"{total_size / (1024 * 1024):.1f} MB)",
                end="",
                flush=True,
            )

    urllib.request.urlretrieve(
        url,
        destination,
        reporthook,
    )

    print(f"\n[OK] Đã tải: {destination}")


# ============================================================
# PACKAGE INSTALLATION
# ============================================================

def install_core_packages() -> None:
    """Install the core project packages."""

    print("\n" + "=" * 70)
    print("=== CÀI ĐẶT THƯ VIỆN CỐT LÕI ===")
    print("=" * 70)

    run(
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
        ]
    )

    run(
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "--upgrade",
            *CORE_REQUIREMENTS,
        ]
    )

    print("[OK] Đã cài đặt thư viện cốt lõi.")


def install_gpu_runtime() -> None:
    """
    Install ONNX Runtime GPU only when CUDA Provider is missing.
    """

    print("\n" + "=" * 70)
    print("=== KIỂM TRA ONNX RUNTIME GPU ===")
    print("=" * 70)

    check_code = r"""
import sys

try:
    import onnxruntime as ort

    try:
        ort.preload_dlls(directory="")
    except Exception:
        pass

    providers = ort.get_available_providers()

    print("ONNX Runtime:", ort.__version__)
    print("Providers:", providers)

    if "CUDAExecutionProvider" in providers:
        sys.exit(0)

    sys.exit(2)

except Exception:
    sys.exit(2)
"""

    result = subprocess.run(
        [
            str(VENV_PYTHON),
            "-c",
            check_code,
        ],
        capture_output=True,
        text=True,
    )

    print(result.stdout)

    if result.returncode == 0:
        print(
            "[OK] CUDA Provider đã hoạt động."
        )
        print(
            "[INFO] Bỏ qua việc cài lại ONNX Runtime."
        )
        return

    print(
        "[INFO] CUDA Provider chưa hoạt động."
    )

    print(
        "[INFO] Gỡ ONNX Runtime để tránh xung đột..."
    )

    run(
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "uninstall",
            "-y",
            "onnxruntime",
            "onnxruntime-gpu",
        ]
    )

    print(
        "[INFO] Cài ONNX Runtime GPU..."
    )

    run(
        [
            str(VENV_PYTHON),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "onnxruntime-gpu[cuda,cudnn]",
        ]
    )

    print(
        "[OK] Đã hoàn thành cài đặt ONNX Runtime GPU."
    )


# ============================================================
# PACKAGE VERIFICATION
# ============================================================

def verify_dependencies() -> None:
    """Verify that required Python modules are installed."""

    print("\n" + "=" * 70)
    print("=== KIỂM TRA CÁC THƯ VIỆN ĐÃ CÀI ===")
    print("=" * 70)

    verification_code = f"""
import importlib.util
import sys

required_modules = {REQUIRED_MODULES!r}

missing_modules = []

for module_name in required_modules:
    try:
        module_spec = importlib.util.find_spec(module_name)

        if module_spec is None:
            missing_modules.append(module_name)

    except Exception:
        missing_modules.append(module_name)

if missing_modules:
    print("[FAIL] Các module bị thiếu:")

    for module_name in missing_modules:
        print(" -", module_name)

    sys.exit(1)

print("[OK] Tất cả module cần thiết đã được cài đặt.")
"""

    run(
        [
            str(VENV_PYTHON),
            "-c",
            verification_code,
        ]
    )


def verify_runtime_packages() -> None:
    """
    Verify ONNX Runtime packages.

    The CPU and GPU distributions should not be installed together.
    """

    print("\n" + "=" * 70)
    print("=== KIỂM TRA ONNX RUNTIME PACKAGES ===")
    print("=" * 70)

    verification_code = r"""
from importlib.metadata import version, PackageNotFoundError
import sys

def get_version(package_name):
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None

cpu_version = get_version("onnxruntime")
gpu_version = get_version("onnxruntime-gpu")

print("onnxruntime:", cpu_version or "NOT INSTALLED")
print("onnxruntime-gpu:", gpu_version or "NOT INSTALLED")

if cpu_version is not None:
    print("[WARNING] CPU onnxruntime is installed.")
    print("[INFO] CPU and GPU packages may conflict.")

if gpu_version is None:
    print("[FAIL] onnxruntime-gpu is not installed.")
    sys.exit(1)

print("[OK] onnxruntime-gpu is installed.")
"""

    run(
        [
            str(VENV_PYTHON),
            "-c",
            verification_code,
        ]
    )


def verify_cuda_provider() -> None:
    """Verify CUDAExecutionProvider availability."""

    print("\n" + "=" * 70)
    print("=== KIỂM TRA CUDA EXECUTION PROVIDER ===")
    print("=" * 70)

    verification_code = r"""
import sys

try:
    import onnxruntime as ort

    print("ONNX Runtime version:", ort.__version__)
    print("ONNX Runtime location:", ort.__file__)

    print("\n[INFO] Đang nạp CUDA/cuDNN DLL...")

    try:
        ort.preload_dlls(directory="")
        print("[OK] preload_dlls() hoàn tất.")

    except Exception as error:
        print("[WARNING] preload_dlls() thất bại:")
        print(" ", repr(error))

    providers = ort.get_available_providers()

    print("\nAvailable providers:")
    print(providers)

    if "CUDAExecutionProvider" not in providers:
        print("\n[FAIL] CUDAExecutionProvider không tồn tại.")
        print("[INFO] GPU chưa được xác nhận.")
        sys.exit(1)

    print("\n[OK] CUDAExecutionProvider đã được tìm thấy.")

    try:
        print("ONNX Runtime device:", ort.get_device())
    except Exception as error:
        print("[WARNING] Không thể kiểm tra device:")
        print(" ", repr(error))

except Exception as error:
    print("[FAIL] Lỗi kiểm tra ONNX Runtime:")
    print(repr(error))
    sys.exit(1)
"""

    try:
        run(
            [
                str(VENV_PYTHON),
                "-c",
                verification_code,
            ]
        )

    except subprocess.CalledProcessError as error:
        print(
            "\n[WARNING] CUDA Provider chưa được xác nhận."
        )
        print(
            f"[WARNING] Exit code: {error.returncode}"
        )


# ============================================================
# MODEL DOWNLOAD
# ============================================================

def ensure_antelopev2_models() -> None:
    """Download and prepare AntelopeV2 models."""

    print("\n" + "=" * 70)
    print("=== KIỂM TRA MODEL ANTELOPEV2 ===")
    print("=" * 70)

    MODEL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    required_paths = [
        MODEL_DIR / file_name
        for file_name in MODEL_FILES
    ]

    if all(path.exists() for path in required_paths):
        print("[OK] Bộ model AntelopeV2 đã tồn tại.")
        return

    print("[INFO] Chưa có đủ model AntelopeV2.")

    download_file(
        ANTELOPE_URL,
        MODEL_ARCHIVE,
    )

    extraction_dir = PROJECT_ROOT / "_model_extracted"

    if extraction_dir.exists():
        shutil.rmtree(extraction_dir)

    extraction_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("[INFO] Đang giải nén AntelopeV2...")

    with zipfile.ZipFile(
        MODEL_ARCHIVE,
        "r",
    ) as archive:
        archive.extractall(extraction_dir)

    print("[INFO] Đang tìm và đưa model về đúng thư mục...")

    for model_file in MODEL_FILES:
        found_files = list(
            extraction_dir.rglob(model_file)
        )

        if not found_files:
            raise RuntimeError(
                f"Không tìm thấy model: {model_file}"
            )

        source_file = found_files[0]
        destination_file = MODEL_DIR / model_file

        shutil.copy2(
            source_file,
            destination_file,
        )

        print(
            f"[OK] {model_file} -> {destination_file}"
        )

    shutil.rmtree(extraction_dir)

    missing_files = [
        str(path)
        for path in required_paths
        if not path.exists()
    ]

    if missing_files:
        raise RuntimeError(
            "Các model sau vẫn bị thiếu:\n"
            + "\n".join(missing_files)
        )

    print("[OK] Bộ model AntelopeV2 đã sẵn sàng.")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Main installation workflow."""

    if os.name != "nt":
        raise OSError(
            "Script này chỉ hỗ trợ Windows."
        )

    print("=" * 70)
    print("FACE ATTENDANCE - INSTALL PACKAGES")
    print("=" * 70)

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Virtual environment: {VENV_DIR}")
    print(f"Python executable: {VENV_PYTHON}")
    print(f"Model directory: {MODEL_DIR}")

    # 1. Kiểm tra .venv
    ensure_venv_exists()

    # 2. Cài thư viện cốt lõi.
    # InsightFace được cài trước ONNX Runtime GPU.
    install_core_packages()

    # 3. Cài GPU Runtime sau InsightFace.
    install_gpu_runtime()

    # 4. Kiểm tra các package.
    verify_dependencies()

    verify_runtime_packages()

    # 5. Kiểm tra CUDA Provider.
    verify_cuda_provider()

    # 6. Tải model.
    ensure_antelopev2_models()

    print("\n" + "=" * 70)
    print("SETUP PACKAGE COMPLETED")
    print("=" * 70)

    print("\nChạy FastAPI:")
    print(
        ".venv\\Scripts\\python.exe "
        "-m uvicorn backend.main:app --reload"
    )


if __name__ == "__main__":
    try:
        main()

    except subprocess.CalledProcessError as error:
        print(
            "\n[ERROR] Lệnh cài đặt thất bại."
        )
        print(
            f"[ERROR] Exit code: {error.returncode}"
        )
        sys.exit(error.returncode)

    except Exception as error:
        print(
            f"\n[ERROR] {error}"
        )
        sys.exit(1)
