"""ImagePreprocessor 단위 테스트."""

import numpy as np
import pytest


def test_preprocessor_outputs_square():
    cv2 = pytest.importorskip("cv2")
    from capture.image_preprocessor import ImagePreprocessor

    img = (np.ones((600, 800, 3), dtype=np.uint8) * 255)
    # 가운데에 검은 도형
    cv2.rectangle(img, (300, 200), (500, 400), (0, 0, 0), -1)

    pp = ImagePreprocessor(target_size=256)
    out = pp.process(img)
    assert out.shape == (256, 256, 3)
