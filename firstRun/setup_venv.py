"""
Create portable Python 3.14 and project virtual environment.

Project structure:
    HTTM2/
    ├── .venv/
    ├── backend/
    ├── frontend/
    ├── models/
    ├── runtime/
    └── firstRun/
        ├── create_environment.py
        └── install_packages.py

Run:
    cd E:\HTTM2\firstRun
    py create_environment.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

PYTHON_VERSION = "3.14.7"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

RUNTIME_DIR = PROJECT_ROOT / "runtime"
PYTHON_DIR = RUNTIME_DIR / "python314"

PYTHON_EXE = PYTHON_DIR / "tools" / "python.exe"

PYTHON_PACKAGE = (
    RUNTIME_DIR / f"python-{PYTHON_VERSION}-nuget.zip"
)

PYTHON_PACKAGE_URL = (
    f"https://www.nuget.org/api/v2/package/python/{PYTHON_VERSION}"
)

GET_PIP_FILE = RUNTIME_DIR / "get-pip.py"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

VENV_DIR = PROJECT_ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"


# ============================================================
# UTILITIES
# ============================================================

def run(command: list[str], *, check: bool = True) -> None:
    """Run a command and display it in the terminal."""

    printable_command = " ".join(
        f'"{item}"' if " " in str(item) else str(item)
        for item in command
    )

    print(f"\n> {printable_command}")

    subprocess.run(
        command,
        check=check,
    )


def download_file(
    url: str,
    destination: Path,
) -> None:
    """Download a file if it does not already exist."""

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if destination.exists():
        print(f"[SKIP] File already exists: {destination}")
        return

    print(f"[DOWNLOAD] {url}")

    urllib.request.urlretrieve(
        url,
        destination,
    )

    print(f"[OK] Downloaded: {destination}")


def remove_directory(path: Path) -> None:
    """Remove a directory if it exists."""

    if path.exists():
        print(f"[INFO] Removing: {path}")
        shutil.rmtree(path)


# ============================================================
# PORTABLE PYTHON
# ============================================================

def configure_python_path_file() -> None:
    """
    Enable site-packages for the Python NuGet distribution.

    The NuGet distribution contains a *_._pth file.
    Python needs 'import site' to load installed packages.
    """

    if not PYTHON_DIR.exists():
        return

    pth_files = list(
        PYTHON_DIR.rglob("*._pth")
    )

    if not pth_files:
        print("[WARNING] No *_._pth file found.")
        return

    for pth_file in pth_files:
        lines = pth_file.read_text(
            encoding="utf-8"
        ).splitlines()

        if any(
            line.strip() == "import site"
            for line in lines
        ):
            print(
                f"[OK] site-packages already enabled: "
                f"{pth_file}"
            )
            continue

        updated_lines = []
        inserted = False

        for line in lines:
            if line.strip() == "# import site":
                updated_lines.append("import site")
                inserted = True
            else:
                updated_lines.append(line)

        if not inserted:
            updated_lines.append("import site")

        pth_file.write_text(
            "\n".join(updated_lines) + "\n",
            encoding="utf-8",
        )

        print(
            f"[OK] Enabled site-packages in: "
            f"{pth_file}"
        )


def find_runtime_python() -> Path | None:
    """Find python.exe in the extracted NuGet package."""

    candidates = [
        PYTHON_DIR / "python.exe",
        PYTHON_DIR / "tools" / "python.exe",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return None


def install_local_python() -> Path:
    """
    Download and extract portable Python.

    Destination:
        HTTM2/runtime/python314
    """

    if PYTHON_EXE.exists():
        print(
            f"[OK] Portable Python found: "
            f"{PYTHON_EXE}"
        )

        configure_python_path_file()

        return PYTHON_EXE

    print(
        f"[INFO] Portable Python {PYTHON_VERSION} "
        "was not found."
    )

    download_file(
        PYTHON_PACKAGE_URL,
        PYTHON_PACKAGE,
    )

    if PYTHON_DIR.exists():
        print(
            "[INFO] Removing incomplete Python runtime..."
        )

        remove_directory(PYTHON_DIR)

    PYTHON_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "[INFO] Extracting portable Python package..."
    )

    with zipfile.ZipFile(
        PYTHON_PACKAGE,
        "r",
    ) as archive:
        archive.extractall(PYTHON_DIR)

    configure_python_path_file()

    discovered_python = find_runtime_python()

    if discovered_python is None:
        raise RuntimeError(
            "Python executable was not found after extraction:\n"
            f"{PYTHON_DIR}"
        )

    if discovered_python != PYTHON_EXE:
        raise RuntimeError(
            "Python executable was found in an unexpected location:\n"
            f"Expected: {PYTHON_EXE}\n"
            f"Found: {discovered_python}"
        )

    print(
        f"[OK] Portable Python installed: "
        f"{PYTHON_EXE}"
    )

    return PYTHON_EXE


# ============================================================
# PIP
# ============================================================

def install_pip(local_python: Path) -> None:
    """Install pip into portable Python."""

    print("[INFO] Checking pip...")

    pip_check = subprocess.run(
        [
            str(local_python),
            "-m",
            "pip",
            "--version",
        ],
        capture_output=True,
        text=True,
    )

    if pip_check.returncode == 0:
        print("[OK] pip is already installed.")
        return

    download_file(
        GET_PIP_URL,
        GET_PIP_FILE,
    )

    print(
        "[INFO] Installing pip into portable Python..."
    )

    run(
        [
            str(local_python),
            str(GET_PIP_FILE),
            "--disable-pip-version-check",
        ]
    )

    print("[OK] pip installed.")


# ============================================================
# VIRTUAL ENVIRONMENT
# ============================================================

def create_venv(local_python: Path) -> Path:
    """
    Create the project virtual environment.

    virtualenv is used instead of the standard venv module.
    """

    if VENV_PYTHON.exists():
        print(
            f"[OK] Existing venv found: "
            f"{VENV_PYTHON}"
        )

        return VENV_PYTHON

    if VENV_DIR.exists():
        raise RuntimeError(
            "The .venv directory exists but is incomplete:\n"
            f"{VENV_DIR}\n\n"
            "Delete the incomplete .venv and run again."
        )

    print(
        "[INFO] Installing virtualenv into portable Python..."
    )

    run(
        [
            str(local_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "virtualenv",
        ]
    )

    print(
        "[INFO] Creating project virtual environment..."
    )

    run(
        [
            str(local_python),
            "-m",
            "virtualenv",
            str(VENV_DIR),
            "--python",
            str(local_python),
        ]
    )

    if not VENV_PYTHON.exists():
        raise RuntimeError(
            "The virtual environment was not created:\n"
            f"{VENV_DIR}"
        )

    print(
        f"[OK] Virtual environment created: "
        f"{VENV_PYTHON}"
    )

    return VENV_PYTHON


# ============================================================
# VERIFICATION
# ============================================================

def verify_python(venv_python: Path) -> None:
    """Verify Python inside the virtual environment."""

    run(
        [
            str(venv_python),
            "--version",
        ]
    )

    run(
        [
            str(venv_python),
            "-c",
            (
                "import sys; "
                "print('Executable:', sys.executable); "
                "print('Prefix:', sys.prefix); "
                "print('Version:', sys.version)"
            ),
        ]
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    if os.name != "nt":
        raise OSError(
            "This script supports Windows only."
        )

    print("=" * 70)
    print(
        "Face Attendance - Create Portable Python Environment"
    )
    print("=" * 70)

    print(f"Project root:        {PROJECT_ROOT}")
    print(f"Runtime directory:   {RUNTIME_DIR}")
    print(f"Python version:      {PYTHON_VERSION}")
    print(f"Portable Python:     {PYTHON_DIR}")
    print(f"Virtual environment: {VENV_DIR}")

    local_python = install_local_python()

    install_pip(local_python)

    venv_python = create_venv(local_python)

    verify_python(venv_python)

    print("\n" + "=" * 70)
    print("ENVIRONMENT CREATION COMPLETED")
    print("=" * 70)

    print("\nActivate venv from HTTM2:")
    print("  .venv\\Scripts\\Activate.ps1")

    print("\nActivate venv from firstRun:")
    print("  ..\\.venv\\Scripts\\Activate.ps1")

    print("\nNext step:")
    print("  py install_packages.py")


if __name__ == "__main__":
    try:
        main()

    except subprocess.CalledProcessError as error:
        print(
            f"\n[ERROR] Command failed with exit code "
            f"{error.returncode}"
        )

        raise SystemExit(error.returncode)

    except Exception as error:
        print(f"\n[ERROR] {error}")

        raise SystemExit(1)