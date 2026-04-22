"""tkinter 기반 RealSense 라이브 프리뷰 위젯.

- 백그라운드 스레드에서 프레임 획득 + BGR→RGB + 리사이즈 수행
- 메인 스레드는 PIL→PhotoImage 변환과 Label 업데이트만 수행 (tk API 요구사항)
"""

from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

try:
    import cv2
except Exception:
    cv2 = None


class CameraPreview(tk.Label):
    """RealSense 프레임을 주기적으로 가져와 Label에 표시."""

    def __init__(self, master, get_frame: Callable, width: int = 640, height: int = 360,
                 interval_ms: int = 50):
        super().__init__(master, background="#111")
        self.get_frame = get_frame
        self.preview_w = width
        self.preview_h = height
        self.interval_ms = interval_ms

        self._job: Optional[str] = None
        self._photo = None

        # BG 스레드에서 생성한 최신 (RGB, 리사이즈된) np.ndarray 저장
        self._pending: Optional[np.ndarray] = None
        self._pending_lock = threading.Lock()

        self._stop_evt = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop_evt.clear()
        self._thread = threading.Thread(
            target=self._processing_loop, name="preview-proc", daemon=True
        )
        self._thread.start()
        self._tick()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _processing_loop(self) -> None:
        """BG 스레드: 프레임 → 리사이즈·색변환 → _pending 갱신."""
        period = max(0.02, self.interval_ms / 1000.0)
        while not self._stop_evt.is_set():
            t0 = time.time()
            try:
                frame = self.get_frame()
                if frame is not None and cv2 is not None:
                    # 원본→프리뷰 크기로 먼저 리사이즈 (메모리/CPU 절약)
                    h, w = frame.shape[:2]
                    scale = min(self.preview_w / max(w, 1), self.preview_h / max(h, 1))
                    if scale < 1.0:
                        new_w = max(1, int(w * scale))
                        new_h = max(1, int(h * scale))
                        frame = cv2.resize(frame, (new_w, new_h),
                                           interpolation=cv2.INTER_AREA)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    with self._pending_lock:
                        self._pending = rgb
            except Exception as e:
                logger.debug(f"preview BG loop 오류: {e}")
            elapsed = time.time() - t0
            sleep_for = period - elapsed
            if sleep_for > 0:
                self._stop_evt.wait(sleep_for)

    def _tick(self) -> None:
        """메인 스레드: _pending에서 RGB 배열 꺼내 PhotoImage로 변환 후 표시."""
        try:
            with self._pending_lock:
                rgb = self._pending
                self._pending = None  # 소비
            if rgb is not None and Image is not None and ImageTk is not None:
                img = Image.fromarray(rgb)
                self._photo = ImageTk.PhotoImage(img)
                self.configure(image=self._photo)
        except Exception as e:
            logger.debug(f"preview tick 오류: {e}")
        self._job = self.after(self.interval_ms, self._tick)
