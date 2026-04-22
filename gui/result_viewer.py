"""결과 애니메이션(GIF) 재생 위젯."""

from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None


class ResultViewer(tk.Label):
    """애니메이션 GIF를 프레임 단위로 재생."""

    def __init__(self, master, width: int = 512, height: int = 512):
        super().__init__(master, background="#222")
        self.preview_w = width
        self.preview_h = height
        self._frames: List = []
        self._durations: List[int] = []
        self._idx = 0
        self._job: Optional[str] = None
        self._current_photo = None

    def load(self, path: str) -> bool:
        if Image is None:
            logger.error("Pillow 미설치 - GIF 재생 불가")
            return False
        p = Path(path)
        if not p.exists():
            logger.error(f"결과 파일이 존재하지 않음: {p}")
            return False

        self.stop()
        self._frames.clear()
        self._durations.clear()

        if p.suffix.lower() == ".gif":
            img = Image.open(p)
            try:
                while True:
                    frame = img.copy().convert("RGBA")
                    frame.thumbnail((self.preview_w, self.preview_h))
                    self._frames.append(frame)
                    self._durations.append(int(img.info.get("duration", 80)))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        else:
            # mp4 등은 OpenCV로 프레임 추출
            try:
                import cv2
                cap = cv2.VideoCapture(str(p))
                while True:
                    ok, frame = cap.read()
                    if not ok:
                        break
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb)
                    img.thumbnail((self.preview_w, self.preview_h))
                    self._frames.append(img)
                    self._durations.append(int(1000 / max(cap.get(cv2.CAP_PROP_FPS), 24)))
                cap.release()
            except Exception as e:
                logger.error(f"비디오 로드 실패: {e}")
                return False

        self._idx = 0
        if self._frames:
            self._play()
            return True
        return False

    def _play(self) -> None:
        if not self._frames:
            return
        frame = self._frames[self._idx]
        self._current_photo = ImageTk.PhotoImage(frame)
        self.configure(image=self._current_photo)
        delay = self._durations[self._idx] if self._idx < len(self._durations) else 80
        self._idx = (self._idx + 1) % len(self._frames)
        self._job = self.after(max(20, delay), self._play)

    def stop(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
