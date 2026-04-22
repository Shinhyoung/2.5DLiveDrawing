"""Gradio 웹 데모. 기존 파이프라인을 재사용하여 브라우저에서 실행.

실행:
    conda activate animated_drawings
    python demo/app.py                     # 로컬 + 퍼블릭(gradio.live) URL
    python demo/app.py --no-share          # 로컬 LAN만 공유
    python demo/app.py --port 8000         # 포트 변경
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 sys.path에 추가
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import gradio as gr
import numpy as np

from capture.image_preprocessor import ImagePreprocessor
from pipeline.animation_runner import (
    MOTIONS_WITHOUT_RETARGET,
    run_animation_subprocess,
)
from pipeline.annotation_runner import run_annotation
from pipeline.torchserve_client import TorchServeClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("demo")

# ---- 싱글턴 리소스 ------------------------------------------------
CLIENT = TorchServeClient()
PREPROCESSOR = ImagePreprocessor()
OUTPUT_ROOT = ROOT / "output" / "web"
SAMPLE_IMG = ROOT / "AnimatedDrawings" / "examples" / "drawings" / "garlic.png"


def discover_motions() -> list[str]:
    motion_dir = ROOT / "AnimatedDrawings" / "examples" / "config" / "motion"
    if not motion_dir.exists():
        return ["dab"]
    names = [p.stem for p in motion_dir.glob("*.yaml")
             if p.stem not in MOTIONS_WITHOUT_RETARGET]
    return sorted(names) or ["dab"]


def torchserve_status() -> str:
    return "✅ Healthy" if CLIENT.is_healthy() else "❌ 미응답"


def animate(image: Optional[np.ndarray], motion: str,
            progress: gr.Progress = gr.Progress()) -> tuple[str, str]:
    """이미지 → 전처리 → 주석 → 렌더 파이프라인.
    (프리뷰용, 다운로드용) 두 출력에 동일한 GIF 경로를 반환한다."""
    if image is None:
        raise gr.Error("이미지를 업로드하거나 웹캠으로 촬영하세요.")

    progress(0.05, desc="TorchServe 상태 확인 중…")
    if not CLIENT.is_healthy():
        raise gr.Error(
            "TorchServe가 응답하지 않습니다. 서버 관리자에게 문의하거나 "
            "start_torchserve 스크립트를 먼저 실행하세요."
        )

    session = time.strftime("%Y%m%d_%H%M%S_") + str(int(time.time() * 1000) % 1000)
    session_dir = OUTPUT_ROOT / session
    session_dir.mkdir(parents=True, exist_ok=True)
    raw_path = session_dir / "raw.png"

    progress(0.15, desc="이미지 저장 중…")
    # Gradio는 RGB numpy 배열을 전달 → OpenCV(BGR)로 변환하여 저장
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(raw_path), bgr)

    progress(0.25, desc="전처리 (원근 보정 + 정사각 크롭)…")
    processed = session_dir / "preprocessed.png"
    try:
        PREPROCESSOR.process_file(str(raw_path), str(processed))
    except Exception as e:
        raise gr.Error(f"전처리 실패: {e}")

    progress(0.40, desc="캐릭터 검출 + 포즈 추정 (TorchServe)…")
    annot_dir = session_dir / "char"
    if not run_annotation(str(processed), str(annot_dir)):
        raise gr.Error(
            "주석 생성 실패. 흰 배경에 팔다리가 분명한 단일 사람 캐릭터 "
            "그림인지 확인해주세요."
        )

    progress(0.70, desc=f"애니메이션 렌더 중 ({motion})…")
    out_gif = session_dir / "animation.gif"
    ok = run_animation_subprocess(
        char_annotation_dir=str(annot_dir),
        output_path=str(out_gif),
        motion=motion,
        output_format="gif",
    )
    if not ok or not out_gif.exists():
        raise gr.Error(
            "애니메이션 렌더 실패. 선택한 모션과 캐릭터 스켈레톤이 호환되지 "
            "않을 수 있습니다."
        )

    progress(1.0, desc="완료!")
    logger.info(f"세션 {session} 완료: {out_gif}")
    path = str(out_gif)
    return path, path


def build_ui() -> gr.Blocks:
    motions = discover_motions()
    default_motion = "dab" if "dab" in motions else motions[0]

    with gr.Blocks(
        title="RealSense × AnimatedDrawings Web Demo",
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown(
            """
            # 🎨 AnimatedDrawings Web Demo

            손그림 이미지를 업로드하거나 웹캠으로 촬영하면 **캐릭터 검출 → 포즈 추정
            → BVH 리타겟** 파이프라인을 거쳐 애니메이션으로 변환합니다.

            - **입력 팁**: 흰 배경 위에 팔다리가 분명하게 그려진 **단일 사람 캐릭터**.
            - **모션**: `dab` / `jumping` / `wave_hello` / `zombie` (fair1 스켈레톤),
              `jumping_jacks` (cmu1 스켈레톤).
            - 처리에는 약 15~20초가 소요됩니다.
            """
        )

        with gr.Row():
            with gr.Column(scale=1):
                image_input = gr.Image(
                    label="손그림 이미지",
                    type="numpy",
                    source="upload",
                    height=360,
                )
                motion_input = gr.Dropdown(
                    choices=motions,
                    value=default_motion,
                    label="모션",
                )
                with gr.Row():
                    run_btn = gr.Button("애니메이션 생성", variant="primary")
                    clear_btn = gr.Button("초기화")

                if SAMPLE_IMG.exists():
                    gr.Examples(
                        examples=[[str(SAMPLE_IMG), m] for m in motions],
                        inputs=[image_input, motion_input],
                        label="예제",
                    )

                ts_label = gr.Markdown(f"**TorchServe 상태**: {torchserve_status()}")
                refresh_btn = gr.Button("상태 새로고침", size="sm")

            with gr.Column(scale=1):
                result = gr.Image(
                    label="생성된 애니메이션 (GIF 미리보기)",
                    type="filepath",
                    height=480,
                )
                gr.Markdown(
                    "💡 **다운로드는 아래 파일 영역**에서 받으세요. "
                    "미리보기의 다운로드 아이콘은 PNG 한 프레임만 저장합니다."
                )
                download = gr.File(
                    label="📥 애니메이션 GIF 다운로드",
                    file_count="single",
                    type="file",
                )

        run_btn.click(
            fn=animate,
            inputs=[image_input, motion_input],
            outputs=[result, download],
        )

        clear_btn.click(
            fn=lambda: (None, None, None),
            inputs=[],
            outputs=[image_input, result, download],
        )

        refresh_btn.click(
            fn=lambda: f"**TorchServe 상태**: {torchserve_status()}",
            inputs=[],
            outputs=[ts_label],
        )

    return demo


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0",
                    help="바인딩 호스트 (LAN 공유를 위해 기본 0.0.0.0)")
    ap.add_argument("--port", type=int, default=7860)
    ap.add_argument("--no-share", action="store_true",
                    help="gradio.live 퍼블릭 URL 생성 안 함")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    if not CLIENT.is_healthy():
        logger.warning(
            "TorchServe가 응답하지 않습니다. start_torchserve 스크립트를 "
            "먼저 실행하거나 서버를 확인하세요. (데모 UI는 그대로 뜨지만 "
            "생성 버튼은 오류를 반환합니다.)"
        )

    demo = build_ui()
    demo.queue()
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=not args.no_share,
        inbrowser=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
