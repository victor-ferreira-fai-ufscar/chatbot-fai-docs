import hashlib
from pathlib import Path

def get_file_hash(filepath: Path) -> str:
    """Computes the MD5 hash and appends the file size for robust lightweight syncing."""
    if not filepath.exists():
        return ""
    
    file_size = filepath.stat().st_size
    hasher = hashlib.md5()
    
    # Read the file in chunks to handle potentially large PDFs
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
            
    md5_hash = hasher.hexdigest()
    return f"{md5_hash}_{file_size}"
