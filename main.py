"""RealSense × AnimatedDrawings 엔트리 포인트.

사용 예:
    python main.py                                   # GUI 모드
    python main.py --auto-serve                       # TorchServe 자동 기동/정지
    python main.py --image path.png --motion dab --headless
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

from capture.image_preprocessor import ImagePreprocessor
from capture.realsense_capture import DummyCapture, RealSenseCapture
from pipeline.animation_runner import run_animation
from pipeline.annotation_runner import run_annotation
from pipeline.torchserve_client import TorchServeClient
from pipeline.torchserve_launcher import TorchServeLauncher

LOG_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT)
logger = logging.getLogger("main")


def load_config(path: str = "config/app_config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        logger.warning(f"설정 파일 없음({p}). 기본값 사용.")
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="RealSense × AnimatedDrawings")
    ap.add_argument("--config", default="config/app_config.yaml")
    ap.add_argument("--auto-serve", action="store_true",
                    help="TorchServe를 자동 기동/정지")
    ap.add_argument("--image", help="단일 이미지로 헤드리스 실행")
    ap.add_argument("--output", default="./output/headless")
    ap.add_argument("--motion", default=None)
    ap.add_argument("--retarget", default=None)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--dummy-capture", action="store_true",
                    help="RealSense가 없을 때 더미 캡처 사용")
    return ap.parse_args()


def run_headless(config: dict, image_path: str, output_dir: str,
                 motion: str, retarget: str) -> int:
    client = TorchServeClient(
        base_url=config.get("torchserve", {}).get("base_url", "http://localhost:8080")
    )
    if not client.wait_for_ready(max_wait=config.get("torchserve", {}).get("ready_timeout", 60)):
        logger.error("TorchServe 헬스체크 실패. start_torchserve 스크립트 또는 --auto-serve 사용")
        return 2

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("이미지 전처리 중…")
    pp = ImagePreprocessor(
        target_size=config.get("preprocessor", {}).get("target_size", 512),
        white_threshold=config.get("preprocessor", {}).get("white_threshold", 200),
        margin_ratio=config.get("preprocessor", {}).get("margin_ratio", 0.05),
    )
    processed = out_dir / "preprocessed.png"
    pp.process_file(image_path, str(processed))

    logger.info("주석 생성 중…")
    annot_dir = out_dir / "char"
    if not run_annotation(str(processed), str(annot_dir)):
        return 3

    logger.info("애니메이션 렌더링 중…")
    fmt = config.get("animation", {}).get("output_format", "gif")
    out_file = out_dir / f"animation.{fmt}"
    ok = run_animation(
        char_annotation_dir=str(annot_dir),
        output_path=str(out_file),
        motion=motion or config.get("animation", {}).get("default_motion", "dab"),
        retarget=retarget or config.get("animation", {}).get("default_retarget", "fair1_ppf"),
        output_format=fmt,
    )
    if not ok:
        return 4
    logger.info(f"완료: {out_file}")
    return 0


def run_gui(config: dict, capture, launcher) -> int:
    from gui.main_window import MainWindow
    win = MainWindow(config=config, capture=capture, launcher=launcher)
    win.run()
    return 0


def make_capture(config: dict, use_dummy: bool):
    cam = config.get("camera", {})
    if use_dummy:
        return DummyCapture()
    try:
        cap = RealSenseCapture(
            width=cam.get("width", 1280),
            height=cam.get("height", 720),
            fps=cam.get("fps", 30),
            warmup_frames=cam.get("warmup_frames", 30),
        )
        cap.start()
        return cap
    except Exception as e:
        logger.warning(f"RealSense 실패 → 더미 캡처 사용: {e}")
        return DummyCapture()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    launcher: TorchServeLauncher | None = None
    if args.auto_serve:
        ts_cfg = config.get("torchserve", {})
        launcher = TorchServeLauncher(
            config_path=ts_cfg.get("config_path", "./config/torchserve_config.properties"),
            model_store=ts_cfg.get("model_store", "./model_store"),
        )
        logger.info("TorchServe 자동 기동 시도…")
        if not launcher.start(wait_ready=True, timeout=ts_cfg.get("ready_timeout", 60)):
            logger.error("TorchServe 기동 실패")
            return 2

    exit_code = 0
    try:
        if args.image:
            exit_code = run_headless(
                config=config,
                image_path=args.image,
                output_dir=args.output,
                motion=args.motion,
                retarget=args.retarget,
            )
        else:
            capture = make_capture(config, use_dummy=args.dummy_capture)
            try:
                exit_code = run_gui(config, capture, launcher)
            finally:
                try:
                    capture.stop()
                except Exception:
                    pass
    finally:
        if launcher:
            logger.info("TorchServe 종료 중…")
            launcher.stop()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
