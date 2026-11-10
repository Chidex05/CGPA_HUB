from pathlib import Path
import shutil


project_root = Path(__file__).resolve().parent
source = project_root / "static"
destination = project_root / "public" / "static"

if not source.is_dir():
    raise FileNotFoundError(f"Static asset directory not found: {source}")

shutil.copytree(source, destination, dirs_exist_ok=True)
