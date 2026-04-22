#!/usr/bin/env bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate animated_drawings

echo "🚀 TorchServe 기동 중..."
torchserve --start \
    --ts-config ./config/torchserve_config.properties \
    --model-store ./model_store \
    --models \
        drawn_humanoid_detector=drawn_humanoid_detector.mar \
        drawn_humanoid_pose_estimator=drawn_humanoid_pose_estimator.mar \
    --disable-token-auth \
    --ncs

echo "⏳ 초기화 대기 중..."
for i in {1..30}; do
    if curl -s http://localhost:8080/ping | grep -q "Healthy"; then
        echo "✅ TorchServe 준비 완료 (http://localhost:8080)"
        exit 0
    fi
    sleep 2
done

echo "❌ TorchServe 기동 실패. logs/ 확인 필요"
exit 1
