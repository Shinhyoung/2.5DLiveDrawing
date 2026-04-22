@echo off
call conda activate animated_drawings

echo TorchServe �⵿ ��...
start /B torchserve --start ^
    --ts-config .\config\torchserve_config.properties ^
    --model-store .\model_store ^
    --models drawn_humanoid_detector=drawn_humanoid_detector.mar drawn_humanoid_pose_estimator=drawn_humanoid_pose_estimator.mar ^
    --disable-token-auth ^
    --ncs

echo �ʱ�ȭ ��� (�� 30��)...
timeout /t 30 /nobreak >nul

echo.
curl -s http://localhost:8080/ping
echo.
echo Ȯ�� �Ϸ�
