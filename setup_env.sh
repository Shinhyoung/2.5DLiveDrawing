#!/usr/bin/env bash
set -e

echo "=== [1/6] AnimatedDrawings 저장소 클론 ==="
if [ ! -d "AnimatedDrawings" ]; then
    git clone https://github.com/facebookresearch/AnimatedDrawings.git AnimatedDrawings
fi

echo "=== [2/6] Conda 환경 생성 (Python 3.8.13) ==="
conda create -y --name animated_drawings python=3.8.13 || echo "[WARN] env may exist"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate animated_drawings

echo "=== [3/6] AnimatedDrawings 패키지 설치 ==="
pushd AnimatedDrawings
pip install -e .
popd

echo "=== [4/6] 추가 의존성 설치 ==="
pip install -r requirements.txt

echo "=== [5/6] .mar 모델 다운로드 ==="
mkdir -p model_store
if [ ! -f model_store/drawn_humanoid_detector.mar ]; then
    wget -O model_store/drawn_humanoid_detector.mar \
        https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_detector.mar
fi
if [ ! -f model_store/drawn_humanoid_pose_estimator.mar ]; then
    wget -O model_store/drawn_humanoid_pose_estimator.mar \
        https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_pose_estimator.mar
fi

echo "=== [6/6] TorchServe 설정 확인 ==="
if [ ! -f config/torchserve_config.properties ]; then
    echo "[ERROR] config/torchserve_config.properties missing"
    exit 1
fi

echo "✅ 환경 설치 완료. 실행: ./start_torchserve.sh && python main.py"
