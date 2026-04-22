"""TorchServe REST 클라이언트. 헬스체크와 추론 요청."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


class TorchServeClient:
    """TorchServe 추론/관리 API 래퍼."""

    BASE_URL = "http://localhost:8080"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or self.BASE_URL).rstrip("/")

    def is_healthy(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/ping", timeout=3)
            return r.status_code == 200 and "Healthy" in r.text
        except Exception:
            return False

    def wait_for_ready(self, max_wait: int = 60, interval: float = 2.0) -> bool:
        start = time.time()
        while time.time() - start < max_wait:
            if self.is_healthy():
                return True
            time.sleep(interval)
        return False

    def predict(self, model_name: str, image_path: str) -> Any:
        with open(image_path, "rb") as f:
            data = f.read()
        url = f"{self.base_url}/predictions/{model_name}"
        r = requests.post(url, data=data, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(
                f"{model_name} 추론 실패: HTTP {r.status_code} — {r.text[:200]}"
            )
        try:
            return r.json()
        except Exception:
            return r.text

    def predict_detector(self, image_path: str) -> Dict[str, Any]:
        return self.predict("drawn_humanoid_detector", image_path)

    def predict_pose(self, image_path: str) -> Dict[str, Any]:
        return self.predict("drawn_humanoid_pose_estimator", image_path)
