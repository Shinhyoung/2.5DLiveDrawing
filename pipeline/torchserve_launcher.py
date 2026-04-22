"""Docker 대신 로컬 파이썬 프로세스로 TorchServe를 제어."""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class TorchServeLauncher:
    """로컬 TorchServe 프로세스 관리자. with 블록에서 자동 시작/종료."""

    PING_URL = "http://localhost:8080/ping"

    def __init__(self,
                 config_path: str = "./config/torchserve_config.properties",
                 model_store: str = "./model_store"):
        self.config_path = str(Path(config_path).resolve())
        self.model_store = str(Path(model_store).resolve())
        self.process: subprocess.Popen | None = None

    def is_running(self) -> bool:
        try:
            r = requests.get(self.PING_URL, timeout=2)
            return r.status_code == 200 and "Healthy" in r.text
        except Exception:
            return False

    def start(self, wait_ready: bool = True, timeout: int = 60) -> bool:
        if self.is_running():
            logger.info("TorchServe 이미 실행 중")
            return True

        self._ensure_java_available()
        self._ensure_models_available()

        cmd = [
            "torchserve", "--start",
            "--ts-config", self.config_path,
            "--model-store", self.model_store,
            "--models",
            "drawn_humanoid_detector=drawn_humanoid_detector.mar",
            "drawn_humanoid_pose_estimator=drawn_humanoid_pose_estimator.mar",
            "--disable-token-auth",
            "--ncs",
        ]
        logger.info(f"TorchServe 기동: {' '.join(cmd)}")
        self.process = subprocess.Popen(cmd)

        if wait_ready:
            ok = self._wait_for_ready(timeout)
            if not ok:
                logger.error("TorchServe 기동 시간 초과")
            return ok
        return True

    def _wait_for_ready(self, timeout: int) -> bool:
        start = time.time()
        while time.time() - start < timeout:
            if self.is_running():
                logger.info("TorchServe 준비 완료")
                return True
            time.sleep(2)
        return False

    def stop(self) -> None:
        try:
            subprocess.run(["torchserve", "--stop"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            logger.warning(f"torchserve --stop 실패: {e}")
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass
        self.process = None
        logger.info("TorchServe 종료 완료")

    # ---- preconditions ------------------------------------------------
    @staticmethod
    def _ensure_java_available() -> None:
        try:
            subprocess.run(["java", "-version"], check=True,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            raise RuntimeError(
                "Java JDK 17이 설치되어 있지 않습니다. "
                "https://adoptium.net/ 에서 설치하고 JAVA_HOME을 설정하세요."
            )

    def _ensure_models_available(self) -> None:
        store = Path(self.model_store)
        required = [
            "drawn_humanoid_detector.mar",
            "drawn_humanoid_pose_estimator.mar",
        ]
        missing = [m for m in required if not (store / m).exists()]
        if missing:
            raise RuntimeError(
                f"model_store({store})에 다음 .mar 파일이 없습니다: {missing}. "
                "setup_env 스크립트로 다운로드하세요."
            )

    # ---- context manager ---------------------------------------------
    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
