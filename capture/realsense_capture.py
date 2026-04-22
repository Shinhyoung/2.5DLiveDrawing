"""Intel RealSense D455 컬러 스트림 캡처 모듈.

파이프라인의 `wait_for_frames()`를 단일 백그라운드 스레드가 전담하여
메인 스레드 블로킹과 프레임 스틸링을 모두 제거한다.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import pyrealsense2 as rs
    _REALSENSE_AVAILABLE = True
except Exception as e:
    rs = None
    _REALSENSE_AVAILABLE = False
    logger.warning(f"pyrealsense2 import 실패: {e}")

try:
    import cv2
except Exception:
    cv2 = None


class RealSenseCapture:
    """D455 컬러 프레임 캡처. 내부 스레드가 최신 프레임을 버퍼에 유지."""

    def __init__(self, width: int = 1280, height: int = 720, fps: int = 30,
                 warmup_frames: int = 30):
        self.width = width
        self.height = height
        self.fps = fps
        self.warmup_frames = warmup_frames
        self._pipeline = None
        self._config = None
        self._started = False

        # 최신 프레임 공유 버퍼 + 잠금
        self._latest: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not _REALSENSE_AVAILABLE:
            raise RuntimeError(
                "pyrealsense2 패키지가 설치되어 있지 않습니다. "
                "`pip install pyrealsense2`를 실행하고 Intel RealSense SDK를 설치하세요."
            )

        self._pipeline = rs.pipeline()
        self._config = rs.config()
        self._config.enable_stream(
            rs.stream.color, self.width, self.height, rs.format.bgr8, self.fps
        )
        self._pipeline.start(self._config)
        self._started = True
        logger.info(f"RealSense 시작: {self.width}x{self.height}@{self.fps}")

        # AE 안정화를 위해 초기 프레임 버리기
        for _ in range(self.warmup_frames):
            try:
                self._pipeline.wait_for_frames(timeout_ms=2000)
            except Exception:
                break

        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._capture_loop, name="rs-capture", daemon=True
        )
        self._thread.start()

    def _capture_loop(self) -> None:
        """백그라운드 스레드: 프레임을 계속 가져와 최신 버퍼 갱신."""
        while not self._stop_evt.is_set():
            try:
                frames = self._pipeline.wait_for_frames(timeout_ms=1000)
                color = frames.get_color_frame()
                if not color:
                    continue
                arr = np.asanyarray(color.get_data())
                with self._lock:
                    self._latest = arr
            except Exception as e:
                # 타임아웃/일시적 오류는 로그 없이 재시도
                if self._stop_evt.is_set():
                    break
                logger.debug(f"capture loop 일시 오류: {e}")
                time.sleep(0.05)

    def get_color_frame(self, timeout_ms: int = 1000) -> Optional[np.ndarray]:
        """
        버퍼에서 최신 프레임 복사본을 즉시 반환 (비블로킹).
        timeout_ms는 버퍼가 아직 채워지지 않았을 때만 의미.
        """
        deadline = time.time() + (timeout_ms / 1000.0)
        while True:
            with self._lock:
                if self._latest is not None:
                    return self._latest.copy()
            if time.time() >= deadline:
                return None
            time.sleep(0.01)

    def capture_still(self, save_path: str) -> str:
        frame = self.get_color_frame(timeout_ms=2000)
        if frame is None:
            raise RuntimeError("RealSense 프레임 캡처 실패 (버퍼가 채워지지 않음)")
        if cv2 is None:
            raise RuntimeError("opencv-python이 필요합니다")
        save_path = str(save_path)
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(save_path, frame)
        logger.info(f"정지 영상 저장: {save_path}")
        return save_path

    def stop(self) -> None:
        # 스레드 먼저 정지 → 파이프라인 정리
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._started and self._pipeline is not None:
            try:
                self._pipeline.stop()
            except Exception as e:
                logger.warning(f"RealSense 종료 오류: {e}")

        self._started = False
        self._pipeline = None
        with self._lock:
            self._latest = None
        logger.info("RealSense 종료")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


class DummyCapture:
    """RealSense 하드웨어가 없는 환경에서 테스트용 더미 캡처."""

    def __init__(self, sample_image: Optional[str] = None, **kwargs):
        self.sample_image = sample_image
        self._frame = None

    def start(self) -> None:
        if self.sample_image and Path(self.sample_image).exists():
            if cv2 is not None:
                self._frame = cv2.imread(self.sample_image)
        if self._frame is None:
            # 512x512 흰 배경 더미
            self._frame = (np.ones((512, 512, 3), dtype=np.uint8) * 255)
        logger.info("DummyCapture 시작")

    def get_color_frame(self, timeout_ms: int = 1000) -> Optional[np.ndarray]:
        return None if self._frame is None else self._frame.copy()

    def capture_still(self, save_path: str) -> str:
        if cv2 is None:
            raise RuntimeError("opencv-python이 필요합니다")
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(save_path, self._frame)
        return save_path

    def stop(self) -> None:
        self._frame = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *a):
        self.stop()
