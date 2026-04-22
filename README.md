# RealSense × AnimatedDrawings (Docker-Free)

Intel RealSense D455 카메라로 손그림을 촬영하여 자동으로 애니메이션화하는 데스크톱 앱.
Docker 없이 로컬 TorchServe로 동작합니다.

## 빠른 시작

```bash
# 1) 환경 설치 (최초 1회) — JDK 17 + Conda + Git 필요
setup_env.bat          # Windows
./setup_env.sh         # Linux/Mac

# 2) TorchServe 기동
start_torchserve.bat   # Windows
./start_torchserve.sh  # Linux/Mac

# 3) 메인 앱 실행
conda activate animated_drawings
python main.py                 # GUI 모드
python main.py --auto-serve    # TorchServe 자동 기동
python main.py --image samples/garlic.png --headless   # 헤드리스
```

## 사전 요구사항

- Python 3.8.13 (conda 환경 권장)
- Java JDK 17 (TorchServe 실행용) — https://adoptium.net/
- Intel RealSense SDK 2.0
- Git

## 디렉터리 구조

자세한 내용은 [claude.md](claude.md) 참조.
