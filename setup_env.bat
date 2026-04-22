@echo off
setlocal ENABLEDELAYEDEXPANSION

echo === [1/6] AnimatedDrawings ���� ���� Ŭ�� ===
if not exist "AnimatedDrawings" (
    git clone https://github.com/facebookresearch/AnimatedDrawings.git AnimatedDrawings
)

echo === [2/6] Conda ȯ�� ���� (Python 3.8.13) ===
call conda create -y --name animated_drawings python=3.8.13
if errorlevel 1 (
    echo [WARN] conda env ������ ����/�̹� ����
)
call conda activate animated_drawings

echo === [3/6] AnimatedDrawings ��Ű�� ��ġ ===
pushd AnimatedDrawings
pip install -e .
popd

echo === [4/6] �߰� ������ ��ġ ===
pip install -r requirements.txt

echo === [5/6] .mar �� ���� ===
if not exist "model_store" mkdir model_store
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_detector.mar' -OutFile 'model_store\drawn_humanoid_detector.mar'"
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_pose_estimator.mar' -OutFile 'model_store\drawn_humanoid_pose_estimator.mar'"

echo === [6/6] TorchServe ���� ���� Ȯ�� ===
if not exist "config\torchserve_config.properties" (
    echo [ERROR] config\torchserve_config.properties �� �����ϴ�. ���͸��� �ùٸ��� Ȯ���ϼ���.
    exit /b 1
)

echo.
echo ȯ�� ��ġ �Ϸ�. ����: start_torchserve.bat  ^&^&  python main.py
pause
