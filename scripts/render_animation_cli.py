"""자식 프로세스로 AnimatedDrawings render.start()를 실행하는 CLI.

GUI 모드에서 tkinter 워커 스레드가 직접 render.start()를 호출하면
Windows GLFW가 비-메인 스레드에서 창을 열지 못해 실패한다.
이 스크립트는 프로젝트 가상환경의 독립 프로세스(메인 스레드)에서 호출된다.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def _setup_paths() -> None:
    here = Path(__file__).resolve().parent.parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))


def _hide_glfw_window() -> None:
    """AnimatedDrawings가 create_window 전에 VISIBLE 힌트를 지정하지 않아
    video_render 모드에서도 창이 잠시 노출된다. create_window를 감싸
    호출 직전에 VISIBLE=False 힌트를 추가하여 완전히 숨긴다."""
    try:
        import glfw  # AnimatedDrawings 의존성
    except Exception:
        return
    _orig = glfw.create_window

    def _hidden_create_window(width, height, title, monitor, share):
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        return _orig(width, height, title, monitor, share)

    glfw.create_window = _hidden_create_window


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    _setup_paths()
    _hide_glfw_window()
    from pipeline.animation_runner import run_animation

    ap = argparse.ArgumentParser()
    ap.add_argument("--char-dir", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--motion", default="dab")
    ap.add_argument("--retarget", default="fair1_ppf")
    ap.add_argument("--format", default="gif")
    args = ap.parse_args()

    ok = run_animation(
        char_annotation_dir=args.char_dir,
        output_path=args.output,
        motion=args.motion,
        retarget=args.retarget,
        output_format=args.format,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
