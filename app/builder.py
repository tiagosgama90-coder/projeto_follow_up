"""Gera executavel UNICO para funcionarios com base de dados embutida."""
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from app.config import (
    APP_NAME, APP_VERSION, EMPLOYEE_EXE,
    get_base_dir, get_db_path, get_runtime_dir, get_icon_path,
)


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _runtime_root() -> Path:
    return get_runtime_dir() if _is_frozen() else Path(__file__).resolve().parent.parent


def _find_python() -> str:
    if not _is_frozen():
        return sys.executable
    for candidate in ("py -3", "python", "python3"):
        parts = candidate.split()
        try:
            r = subprocess.run(parts + ["--version"], capture_output=True)
            if r.returncode == 0:
                return candidate
        except (FileNotFoundError, OSError):
            continue
    raise RuntimeError("Precisa de Python 3 instalado para gerar o executavel.")


def _prepare_source_tree(target: Path) -> None:
    src = get_base_dir() if _is_frozen() else Path(__file__).resolve().parent.parent
    shutil.copy2(src / "main.py", target / "main.py")
    if (target / "app").exists():
        shutil.rmtree(target / "app")
    shutil.copytree(src / "app", target / "app")
    assets = target / "assets"
    assets.mkdir(exist_ok=True)
    for base in (src, _runtime_root()):
        ad = base / "assets"
        if ad.exists():
            for f in ad.iterdir():
                if f.suffix.lower() in (".png", ".ico"):
                    shutil.copy2(f, assets / f.name)


def prepare_bundle(db_source: Path | None = None) -> Path:
    source = db_source or get_db_path()
    if not source.exists():
        raise FileNotFoundError("Importe a base de dados primeiro.")
    bundle = _runtime_root() / "bundle_data"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "data").mkdir(exist_ok=True)
    shutil.copy2(source, bundle / "data" / "sales.db")
    config = {
        "mode": "employee",
        "version": APP_VERSION,
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app_name": APP_NAME,
    }
    (bundle / "build_config.json").write_text(
        json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return bundle


def build_employee_exe(progress_callback=None) -> Path:
    """Gera UM unico .exe com dados embutidos para enviar aos funcionarios."""
    bundle = prepare_bundle()
    runtime = _runtime_root()

    if progress_callback:
        progress_callback("A preparar executavel com dados embutidos...")

    if _is_frozen():
        build_root = Path(tempfile.mkdtemp(prefix="soretrac_build_"))
        _prepare_source_tree(build_root)
        source_root = build_root
    else:
        source_root = Path(__file__).resolve().parent.parent

    dist = runtime / "build_output"
    dist.mkdir(parents=True, exist_ok=True)
    work = runtime / "build_temp"
    work.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d")
    exe_name = Path(EMPLOYEE_EXE).stem + f"_{stamp}"
    sep = ";" if sys.platform == "win32" else ":"

    add_data = [
        f"{bundle / 'data' / 'sales.db'}{sep}data",
        f"{bundle / 'build_config.json'}{sep}.",
    ]
    assets = source_root / "assets"
    if assets.exists():
        for f in assets.iterdir():
            if f.suffix.lower() in (".png", ".ico"):
                add_data.append(f"{f}{sep}assets")

    icon = get_icon_path()
    cmd = _find_python().split() + [
        "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        f"--name={exe_name}",
        f"--distpath={dist}", f"--workpath={work}", f"--specpath={work}",
        "--hidden-import=customtkinter", "--hidden-import=PIL",
        "--hidden-import=PIL._tkinter_finder", "--collect-all=customtkinter",
        "--hidden-import=openpyxl",
    ]
    if icon.exists():
        cmd.append(f"--icon={icon}")
    for item in add_data:
        cmd.extend(["--add-data", item])
    cmd.append(str(source_root / "main.py"))

    if progress_callback:
        progress_callback("A compilar (2-5 min na primeira vez)...")

    r = subprocess.run(cmd, cwd=str(source_root), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"Erro na compilacao:\n{(r.stderr or r.stdout)[-2500:]}")

    exe_path = dist / f"{exe_name}.exe"
    if not exe_path.exists():
        raise FileNotFoundError("Executavel nao foi gerado.")

    final = dist / EMPLOYEE_EXE
    shutil.copy2(exe_path, final)

    if progress_callback:
        progress_callback(f"Pronto: {EMPLOYEE_EXE}")

    return final


def export_employee_package(progress_callback=None) -> Path:
    return build_employee_exe(progress_callback)
