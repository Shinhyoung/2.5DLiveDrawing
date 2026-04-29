"""
MVC YAML config를 동적으로 생성하고 AnimatedDrawings의 render.start()를 호출.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


def _add_animated_drawings_to_path() -> None:
    here = Path(__file__).resolve().parent.parent
    ad_root = here / "AnimatedDrawings"
    if ad_root.exists() and str(ad_root) not in sys.path:
        sys.path.insert(0, str(ad_root))


def _find_motion_cfg(motion_name: str) -> Optional[Path]:
    here = Path(__file__).resolve().parent.parent
    candidates = [
        here / "AnimatedDrawings" / "examples" / "config" / "motion" / f"{motion_name}.yaml",
        here / "AnimatedDrawings" / "examples" / "config" / "motion" / motion_name / "config.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _find_retarget_cfg(name: str) -> Optional[Path]:
    here = Path(__file__).resolve().parent.parent
    candidates = [
        here / "AnimatedDrawings" / "examples" / "config" / "retarget" / f"{name}.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def run_animation(char_annotation_dir: str,
                  output_path: str,
                  motion: str = "dab",
                  retarget: str = "fair1_ppf",
                  output_format: str = "gif") -> bool:
    """
    render 구성 파일을 임시로 만들고 AnimatedDrawings.render.start()를 호출.
    """
    _add_animated_drawings_to_path()

    char_dir = Path(char_annotation_dir).resolve()
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    char_cfg = char_dir / "char_cfg.yaml"
    if not char_cfg.exists():
        logger.error(f"char_cfg.yaml을 찾을 수 없음: {char_cfg}")
        return False

    motion_cfg = _find_motion_cfg(motion)
    retarget_cfg = _find_retarget_cfg(retarget)
    if motion_cfg is None or retarget_cfg is None:
        logger.error(f"motion/retarget 설정을 찾을 수 없음: motion={motion}, retarget={retarget}")
        return False

    mvc = {
        "scene": {
            "ANIMATED_CHARACTERS": [{
                "character_cfg": str(char_cfg),
                "motion_cfg": str(motion_cfg),
                "retarget_cfg": str(retarget_cfg),
            }],
        },
        "controller": {
            "MODE": "video_render",
            "OUTPUT_VIDEO_PATH": str(out_path),
        },
        "view": {
            "USE_MESH_TEXTURE": True,
        },
    }

    mvc_path = char_dir / "mvc_cfg.yaml"
    with open(mvc_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(mvc, f, allow_unicode=True)

    try:
        from animated_drawings import render  # type: ignore
    except Exception as e:
        logger.error(f"animated_drawings 모듈 import 실패: {e}")
        return False

    try:
        render.start(str(mvc_path))
        logger.info(f"애니메이션 렌더 완료: {out_path}")
        return True
    except Exception as e:
        logger.exception(f"애니메이션 렌더 실패: {e}")
        return False


# 모션 → 호환 리타겟 매핑. BVH 스켈레톤이 다르면 retargeter에서 KeyError 발생.
MOTION_RETARGET_MAP: dict[str, str] = {
    "dab": "fair1_ppf",
    "jumping": "fair1_ppf",
    "wave_hello": "fair1_ppf",
    "zombie": "fair1_ppf",
    "jumping_jacks": "cmu1_pfp",
    # jesse_dance는 rokoko 스켈레톤(LeftShoulder/LeftArm 등 Mixamo 호환 본 이름)을 쓰므로
    # mixamo_fff 리타겟과 호환된다 (공식 rokoko_motion_example.yaml 참조).
    "jesse_dance": "mixamo_fff",
}

# 리타겟이 매핑되지 않은 모션 (현재 모든 6개 모션이 매핑됨).
MOTIONS_WITHOUT_RETARGET: set[str] = set()


def resolve_retarget(motion: str, fallback: str = "fair1_ppf") -> str:
    """모션 이름으로부터 호환 리타겟 이름을 결정."""
    return MOTION_RETARGET_MAP.get(motion, fallback)


def run_animation_subprocess(char_annotation_dir: str,
                             output_path: str,
                             motion: str = "dab",
                             retarget: str | None = None,
                             output_format: str = "gif",
                             timeout: int = 300) -> bool:
    """
    render.start()를 자식 프로세스에서 실행.

    AnimatedDrawings의 render.start()는 내부적으로 glfw로 OpenGL 창을 생성하는데,
    Windows에서 GLFW는 메인 스레드 외부(tkinter worker thread)에서 호출하면 실패한다.
    자식 프로세스의 메인 스레드에서 깨끗하게 실행하기 위해 subprocess로 분리한다.
    """
    project_root = Path(__file__).resolve().parent.parent
    script = project_root / "scripts" / "render_animation_cli.py"
    if not script.exists():
        logger.error(f"렌더 CLI 스크립트 없음: {script}")
        return False

    effective_retarget = retarget or resolve_retarget(motion)

    # 서브프로세스 결과의 '파일 존재 여부'로 성공 판정하기 위해 기존 산출물 제거
    out_p = Path(output_path)
    if out_p.exists():
        try:
            out_p.unlink()
        except Exception as e:
            logger.warning(f"기존 출력 파일 제거 실패: {e}")

    cmd = [
        sys.executable, str(script),
        "--char-dir", str(char_annotation_dir),
        "--output", str(output_path),
        "--motion", motion,
        "--retarget", effective_retarget,
        "--format", output_format,
    ]
    logger.info(f"렌더 서브프로세스 기동: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if result.stdout:
            logger.info(f"[render stdout tail]\n...{result.stdout[-2000:]}")
        if result.stderr:
            logger.info(f"[render stderr tail]\n...{result.stderr[-2000:]}")
        output_exists = Path(output_path).exists()
        if result.returncode != 0:
            logger.error(
                f"렌더 서브프로세스 실패 exit={result.returncode}, "
                f"file_exists={output_exists}"
            )
            # Windows GLFW가 종료 시 비정상 exit code를 남기더라도
            # 파일이 성공적으로 생성되었으면 성공으로 간주
            return output_exists
        return output_exists
    except subprocess.TimeoutExpired as e:
        logger.error(f"렌더 서브프로세스 타임아웃 (stderr={getattr(e, 'stderr', None)})")
        return Path(output_path).exists()
    except Exception as e:
        logger.exception(f"렌더 서브프로세스 예외: {e}")
        return Path(output_path).exists()
