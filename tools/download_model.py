"""Download and verify the MVSS-Net checkpoint (ml/mvss/ckpt/mvssnet_casia.pt).

Usage (from the project folder, with the virtual environment active):
    python tools/download_model.py

The file (about 562 MB) is accepted only if its SHA-256 matches the value
pinned in forenchain/forensics.py. If it is already present nothing happens.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forenchain.forensics import CHECKPOINT, MODEL_URL, ensure_checkpoint  # noqa: E402

if __name__ == "__main__":
    if CHECKPOINT.exists():
        print(f"Model already present: {CHECKPOINT}")
    else:
        print(f"Downloading MVSS-Net model (about 562 MB) from:\n  {MODEL_URL}")
        ensure_checkpoint()
        print(f"Done. Model verified and saved to: {CHECKPOINT}")
