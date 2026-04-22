"""tkinter 기반 메인 윈도우. 캡처/파이프라인 제어 버튼 포함."""

from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from capture.image_preprocessor import ImagePreprocessor
from gui.camera_preview import CameraPreview
from gui.result_viewer import ResultViewer
from pipeline.animation_runner import (
    MOTIONS_WITHOUT_RETARGET,
    run_animation_subprocess,
)
from pipeline.annotation_runner import run_annotation
from pipeline.torchserve_client import TorchServeClient

logger = logging.getLogger(__name__)


class MainWindow:
    """GUI 컨트롤러."""

    def __init__(self, config: dict, capture, launcher=None):
        self.config = config
        self.capture = capture
        self.launcher = launcher
        self.client = TorchServeClient(
            base_url=config.get("torchserve", {}).get("base_url", "http://localhost:8080")
        )
        self.preprocessor = ImagePreprocessor(
            target_size=config.get("preprocessor", {}).get("target_size", 512),
            white_threshold=config.get("preprocessor", {}).get("white_threshold", 200),
            margin_ratio=config.get("preprocessor", {}).get("margin_ratio", 0.05),
        )
        self.output_dir = Path(config.get("app", {}).get("output_dir", "./output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._build_ui()

    # ---- UI ------------------------------------------------------------
    def _build_ui(self) -> None:
        self.root = tk.Tk()
        self.root.title("RealSense × AnimatedDrawings")
        self.root.geometry("1200x720")

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.LabelFrame(main, text="Camera Preview", padding=6)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.preview = CameraPreview(
            left,
            get_frame=self._safe_get_frame,
            width=640, height=400,
        )
        self.preview.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(main, padding=6)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        result_frame = ttk.LabelFrame(right, text="Animation Result", padding=6)
        result_frame.pack(fill=tk.BOTH, expand=True)
        self.result_viewer = ResultViewer(result_frame, width=480, height=480)
        self.result_viewer.pack(fill=tk.BOTH, expand=True)

        controls = ttk.LabelFrame(right, text="Controls", padding=6)
        controls.pack(fill=tk.X, pady=(6, 0))

        self.motion_var = tk.StringVar(
            value=self.config.get("animation", {}).get("default_motion", "dab")
        )
        ttk.Label(controls, text="Motion").grid(row=0, column=0, sticky="w")
        motion_combo = ttk.Combobox(
            controls,
            textvariable=self.motion_var,
            values=self._discover_motions(),
            width=22,
            state="readonly",
        )
        motion_combo.grid(row=0, column=1, padx=4)

        self.capture_btn = ttk.Button(controls, text="캡처 & 애니메이션 생성", command=self._on_capture)
        self.capture_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)

        self.load_btn = ttk.Button(controls, text="이미지 파일로 실행", command=self._on_load_image)
        self.load_btn.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)

        self.status_var = tk.StringVar(value="준비됨")
        ttk.Label(controls, textvariable=self.status_var, foreground="#08a").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )

        # TorchServe 상태 표시
        self.ts_var = tk.StringVar(value="TorchServe: 점검 중…")
        ttk.Label(controls, textvariable=self.ts_var).grid(
            row=4, column=0, columnspan=2, sticky="w"
        )

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _discover_motions(self) -> list[str]:
        """AnimatedDrawings/examples/config/motion/*.yaml 중 리타겟 호환 모션만 반환."""
        motion_dir = Path(__file__).resolve().parent.parent / "AnimatedDrawings" / "examples" / "config" / "motion"
        if not motion_dir.exists():
            return ["dab"]
        names = [p.stem for p in motion_dir.glob("*.yaml")
                 if p.stem not in MOTIONS_WITHOUT_RETARGET]
        return sorted(names) or ["dab"]

    def _safe_get_frame(self):
        try:
            return self.capture.get_color_frame()
        except Exception:
            return None

    # ---- actions -------------------------------------------------------
    def _on_capture(self) -> None:
        self.capture_btn.config(state=tk.DISABLED)
        self.status_var.set("캡처 중…")
        threading.Thread(target=self._run_pipeline_from_camera, daemon=True).start()

    def _on_load_image(self) -> None:
        path = filedialog.askopenfilename(
            title="이미지 선택",
            filetypes=[("Image", "*.png *.jpg *.jpeg *.bmp"), ("All", "*.*")],
        )
        if not path:
            return
        self.capture_btn.config(state=tk.DISABLED)
        self.status_var.set("이미지 로드…")
        threading.Thread(target=self._run_pipeline_from_file, args=(path,), daemon=True).start()

    def _run_pipeline_from_camera(self) -> None:
        try:
            session = time.strftime("%Y%m%d_%H%M%S")
            session_dir = self.output_dir / session
            session_dir.mkdir(parents=True, exist_ok=True)
            raw_path = session_dir / "raw.png"
            self.capture.capture_still(str(raw_path))
            self._run_pipeline(str(raw_path), session_dir)
        except Exception as e:
            logger.exception("camera pipeline 실패")
            self._set_status(f"실패: {e}")
        finally:
            self._enable_buttons()

    def _run_pipeline_from_file(self, image_path: str) -> None:
        try:
            session = time.strftime("%Y%m%d_%H%M%S")
            session_dir = self.output_dir / session
            session_dir.mkdir(parents=True, exist_ok=True)
            self._run_pipeline(image_path, session_dir)
        except Exception as e:
            logger.exception("file pipeline 실패")
            self._set_status(f"실패: {e}")
        finally:
            self._enable_buttons()

    def _run_pipeline(self, image_path: str, session_dir: Path) -> None:
        self._set_status("전처리 중…")
        processed = session_dir / "preprocessed.png"
        self.preprocessor.process_file(image_path, str(processed))

        self._set_status("TorchServe 헬스체크…")
        if not self.client.wait_for_ready(max_wait=10):
            raise RuntimeError("TorchServe에 연결할 수 없습니다")

        self._set_status("주석 생성 중…")
        annot_dir = session_dir / "char"
        ok = run_annotation(str(processed), str(annot_dir))
        if not ok:
            raise RuntimeError("annotation 실패")

        self._set_status("애니메이션 렌더링 중…")
        fmt = self.config.get("animation", {}).get("output_format", "gif")
        out_file = session_dir / f"animation.{fmt}"
        motion = self.motion_var.get().strip() or "dab"
        # 자식 프로세스에서 render.start() 실행: Windows GLFW는 메인 스레드 필수.
        # retarget은 animation_runner가 motion에 맞춰 자동 결정.
        ok = run_animation_subprocess(
            char_annotation_dir=str(annot_dir),
            output_path=str(out_file),
            motion=motion,
            output_format=fmt,
        )
        if not ok:
            raise RuntimeError("애니메이션 렌더 실패")

        self._set_status(f"완료: {out_file}")
        self.root.after(0, lambda: self.result_viewer.load(str(out_file)))

    # ---- helpers ------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    def _enable_buttons(self) -> None:
        self.root.after(0, lambda: self.capture_btn.config(state=tk.NORMAL))

    def _refresh_ts_status(self) -> None:
        """백그라운드 스레드에서 주기적으로 ping → 결과만 UI 스레드로 전달."""
        if getattr(self, "_ts_thread", None) is not None:
            return
        self._ts_stop = threading.Event()

        def loop():
            while not self._ts_stop.is_set():
                try:
                    ok = self.client.is_healthy()
                except Exception:
                    ok = False
                label = "TorchServe: ✅ Healthy" if ok else "TorchServe: ❌ 미응답"
                try:
                    self.root.after(0, lambda s=label: self.ts_var.set(s))
                except Exception:
                    break
                self._ts_stop.wait(3.0)

        self._ts_thread = threading.Thread(target=loop, name="ts-health", daemon=True)
        self._ts_thread.start()

    # ---- main loop -----------------------------------------------------
    def run(self) -> None:
        self.preview.start()
        self._refresh_ts_status()
        try:
            self.root.mainloop()
        finally:
            self.preview.stop()

    def _on_close(self) -> None:
        # 헬스체크 스레드 정지 먼저
        stop_evt = getattr(self, "_ts_stop", None)
        if stop_evt is not None:
            stop_evt.set()
        ts_thread = getattr(self, "_ts_thread", None)
        if ts_thread is not None:
            ts_thread.join(timeout=1.0)

        try:
            self.preview.stop()
            self.result_viewer.stop()
        except Exception:
            pass
        try:
            self.capture.stop()
        except Exception:
            pass
        self.root.destroy()
