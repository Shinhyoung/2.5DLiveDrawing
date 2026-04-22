"""손그림(흰 배경) 자동 감지 · 크롭 · 원근 보정 전처리."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2
except Exception:
    cv2 = None


class ImagePreprocessor:
    """
    흰 배경에서 손그림 영역을 감지하여 정사각 이미지로 정리.

    AnimatedDrawings는 대략 정사각에 가까운 이미지를 기대하므로
    (1) 그레이스케일 이진화 → (2) 외곽 사각형 검출 → (3) 원근 보정 → (4) 정사각 크롭.
    """

    def __init__(self, target_size: int = 512, white_threshold: int = 200,
                 margin_ratio: float = 0.05):
        if cv2 is None:
            raise RuntimeError("opencv-python이 설치되어 있지 않습니다")
        self.target_size = target_size
        self.white_threshold = white_threshold
        self.margin_ratio = margin_ratio

    def process(self, image: np.ndarray) -> np.ndarray:
        """전체 파이프라인: 검출 → 원근 보정 → 정사각 리사이즈."""
        quad = self._detect_paper_quad(image)
        if quad is not None:
            warped = self._warp_perspective(image, quad)
        else:
            warped = self._crop_by_contour(image)
        return self._to_square(warped)

    def process_file(self, in_path: str, out_path: str) -> str:
        img = cv2.imread(str(in_path))
        if img is None:
            raise FileNotFoundError(f"이미지 로드 실패: {in_path}")
        processed = self.process(img)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), processed)
        logger.info(f"전처리 완료: {out_path}")
        return str(out_path)

    # ---- internal ------------------------------------------------------
    def _detect_paper_quad(self, image: np.ndarray) -> Optional[np.ndarray]:
        """용지(사각형) 코너 4개를 찾는다. 실패하면 None."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(
            blurred, self.white_threshold, 255, cv2.THRESH_BINARY
        )
        # 흰 영역 검출을 위해 반전
        edges = cv2.Canny(thresh, 50, 150)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        for c in contours:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if len(approx) == 4 and cv2.contourArea(approx) > 0.1 * image.shape[0] * image.shape[1]:
                return approx.reshape(4, 2).astype(np.float32)
        return None

    def _warp_perspective(self, image: np.ndarray, quad: np.ndarray) -> np.ndarray:
        pts = self._order_points(quad)
        (tl, tr, br, bl) = pts
        widthA = np.linalg.norm(br - bl)
        widthB = np.linalg.norm(tr - tl)
        maxW = int(max(widthA, widthB))
        heightA = np.linalg.norm(tr - br)
        heightB = np.linalg.norm(tl - bl)
        maxH = int(max(heightA, heightB))
        maxW = max(maxW, 1)
        maxH = max(maxH, 1)
        dst = np.array([[0, 0], [maxW - 1, 0], [maxW - 1, maxH - 1], [0, maxH - 1]],
                       dtype=np.float32)
        M = cv2.getPerspectiveTransform(pts, dst)
        return cv2.warpPerspective(image, M, (maxW, maxH))

    @staticmethod
    def _order_points(pts: np.ndarray) -> np.ndarray:
        """4개 점을 TL, TR, BR, BL 순서로 정렬."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1).flatten()
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def _crop_by_contour(self, image: np.ndarray) -> np.ndarray:
        """사각형 검출에 실패한 경우 비흰색 영역의 bbox로 크롭."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, self.white_threshold, 255,
                                  cv2.THRESH_BINARY_INV)
        ys, xs = np.where(thresh > 0)
        if len(xs) == 0 or len(ys) == 0:
            return image
        x0, x1 = xs.min(), xs.max()
        y0, y1 = ys.min(), ys.max()
        mx = int((x1 - x0) * self.margin_ratio)
        my = int((y1 - y0) * self.margin_ratio)
        x0 = max(0, x0 - mx)
        y0 = max(0, y0 - my)
        x1 = min(image.shape[1], x1 + mx)
        y1 = min(image.shape[0], y1 + my)
        return image[y0:y1, x0:x1]

    def _to_square(self, image: np.ndarray) -> np.ndarray:
        h, w = image.shape[:2]
        size = max(h, w)
        canvas = np.full((size, size, 3), 255, dtype=np.uint8)
        y_off = (size - h) // 2
        x_off = (size - w) // 2
        canvas[y_off:y_off + h, x_off:x_off + w] = image
        return cv2.resize(canvas, (self.target_size, self.target_size),
                          interpolation=cv2.INTER_AREA)
