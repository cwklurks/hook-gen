import re
from pathlib import Path
from typing import Optional


def build_zip_name(upload_name: Optional[str]) -> str:
    """Create a clean download filename based on the uploaded loop."""
    if not upload_name:
        return "hooks.zip"
    stem = Path(upload_name).stem.strip()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", " ", stem).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.replace(" ", "-")
    return f"hooks - {cleaned}.zip" if cleaned else "hooks.zip"
