"""
AnimatedDrawings의 `image_to_annotations`를 호출해 mask/texture/char_cfg 생성.

AnimatedDrawings/examples/image_to_annotations.py 함수가
http://localhost:8080의 TorchServe에 REST 요청을 보내 결과물을 만든다.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _add_examples_to_path() -> None:
    here = Path(__file__).resolve().parent.parent
    examples = here / "AnimatedDrawings" / "examples"
    if examples.exists() and str(examples) not in sys.path:
        sys.path.insert(0, str(examples))


def run_annotation(image_path: str, output_dir: str) -> bool:
    """
    AnimatedDrawings 공식 예제 함수로 주석 생성.

    output_dir 하위에 다음 결과물이 생성된다:
      - mask.png
      - texture.png
      - char_cfg.yaml
    """
    _add_examples_to_path()
    try:
        from image_to_annotations import image_to_annotations  # type: ignore
    except Exception as e:
        logger.error(f"image_to_annotations import 실패: {e}")
        return False

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        image_to_annotations(str(image_path), str(output_dir))
        logger.info(f"annotation 생성 완료: {output_dir}")
        return True
    except Exception as e:
        logger.exception(f"annotation 실행 실패: {e}")
        return False
