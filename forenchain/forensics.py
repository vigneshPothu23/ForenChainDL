
from pathlib import Path
import hashlib
import os
import sys
import urllib.request

import numpy as np
import torch
from PIL import Image
import torchvision.transforms as transforms

ROOT = Path(__file__).resolve().parent.parent
MVSS_DIR = ROOT / "ml" / "mvss"
CHECKPOINT = MVSS_DIR / "ckpt" / "mvssnet_casia.pt"

# The 562 MB checkpoint is not stored in Git. If it is missing it is downloaded
# once from MODEL_URL (override with the FORENCHAIN_MODEL_URL environment
# variable or Streamlit secret) and accepted only if its SHA-256 matches.
MODEL_URL = os.environ.get(
    "FORENCHAIN_MODEL_URL",
    "https://github.com/vigneshPothu23/ForenChainDL/releases/download/model-v1/mvssnet_casia.pt",
)
MODEL_SHA256 = "080bc6c3aae59f748b547dbf090786fe9d31a6e50749daaa40871e298d6a7e50"

if str(MVSS_DIR) not in sys.path:
    sys.path.insert(0, str(MVSS_DIR))

from models.mvssnet import get_mvss


def ensure_checkpoint(path: Path = CHECKPOINT, url: str = None) -> Path:
    """Return the checkpoint path, downloading and verifying it if missing."""
    path = Path(path)
    if path.exists():
        return path
    url = url or MODEL_URL
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(url, timeout=60) as response, open(partial, "wb") as out:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(chunk)
                out.write(chunk)
        if digest.hexdigest() != MODEL_SHA256:
            raise RuntimeError(
                "Downloaded MVSS-Net checkpoint failed SHA-256 verification; it was discarded."
            )
        os.replace(partial, path)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"MVSS-Net checkpoint is missing and could not be downloaded from {url}. "
            f"Place mvssnet_casia.pt in {path.parent} (see README). Details: {exc}"
        ) from exc
    return path


class MVSSForensics:
    def __init__(self):
        self.device = torch.device("cpu")

        self.model = get_mvss(
            backbone="resnet50",
            pretrained_base=False,
            nclass=1,
            sobel=True,
            constrain=True,
            n_input=3,
        )

        checkpoint = torch.load(
            ensure_checkpoint(),
            map_location=self.device,
            weights_only=True,
        )
        self.model.load_state_dict(checkpoint)
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

    def analyze(self, image: Image.Image):
        image = image.convert("RGB")
        tensor = self.transform(image).unsqueeze(0).to(self.device)

        with torch.inference_mode():
            output = self.model(tensor)

        localization = output[-1] if isinstance(output, (tuple, list)) else output
        response = torch.sigmoid(localization)[0, 0].cpu().numpy()

        screening_score = float(response.max())

        return {
            "screening_score": screening_score,
            "localization_map": response,
            "device": str(self.device),
        }
