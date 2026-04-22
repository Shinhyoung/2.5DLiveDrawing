네, Docker 없이도 충분히 구현 가능합니다. AnimatedDrawings는 내부적으로 TorchServe REST API만 호출하면 되므로, TorchServe를 로컬 파이썬 패키지로 직접 실행하거나, TorchServe 자체도 생략하고 모델을 PyTorch로 직접 로드하는 두 가지 방식이 있습니다.
아래는 Docker-free 버전의 CLAUDE.md입니다.

markdown# CLAUDE.md — RealSense D455 × AnimatedDrawings (Docker-Free)

## 프로젝트 개요

Intel RealSense D455 카메라로 손그림을 실시간 촬영하여, AnimatedDrawings 파이프라인으로
자동 애니메이션화하는 PC 기반 데스크톱 애플리케이션. **Docker 없이** 순수 Python
환경에서 TorchServe를 로컬 실행하여 ML 모델 추론을 수행한다.

동작 흐름:
1. D455에서 컬러 프레임 캡처
2. 흰 배경 기반 자동 크롭 및 원근 보정
3. 로컬 TorchServe(파이썬 기동)로 캐릭터 감지 · 세그멘테이션 · 포즈 추정
4. BVH 모션으로 리타게팅하여 애니메이션 생성 (GIF/MP4)

---

## 기술 스택 (Docker 제거)

| 구성 요소 | 버전 / 비고 |
|---|---|
| OS | Windows 10/11 64-bit 또는 Ubuntu 20.04+ |
| Python | 3.8.13 (conda 환경) |
| AnimatedDrawings | facebookresearch/AnimatedDrawings (MIT) |
| Intel RealSense SDK 2.0 | librealsense2 2.55+ |
| pyrealsense2 | pip 패키지 |
| OpenCV | 4.8+ |
| Java JDK | 17 (TorchServe 로컬 실행에 필수) |
| TorchServe | 0.9.0 (pip 설치) |
| torch-model-archiver | 0.9.0 (pip) |
| PyTorch | 1.13.1+ (CPU 또는 CUDA) |
| OpenMMLab | mmdet 2.27, mmpose 0.29 |

> ⚠️ **핵심 차이점**: Docker 대신 **Java JDK + 로컬 TorchServe**를 사용.
> TorchServe는 내부적으로 Java 런타임 위에서 동작한다.

---

## 디렉터리 구조
realsense-animated-drawings/
├── CLAUDE.md
├── README.md
├── setup_env.sh / setup_env.bat          ← 자동 환경 설치 스크립트
├── start_torchserve.sh / .bat             ← TorchServe 로컬 기동 스크립트
├── stop_torchserve.sh / .bat              ← TorchServe 정지 스크립트
├── requirements.txt
├── main.py
├── capture/
│   ├── realsense_capture.py
│   └── image_preprocessor.py
├── pipeline/
│   ├── torchserve_launcher.py            ← TorchServe 프로세스 제어
│   ├── torchserve_client.py
│   ├── annotation_runner.py
│   └── animation_runner.py
├── gui/
│   ├── main_window.py
│   ├── camera_preview.py
│   └── result_viewer.py
├── config/
│   ├── app_config.yaml
│   └── torchserve_config.properties       ← 로컬 TorchServe 설정
├── models/                                ← .mar 모델 파일 저장소
│   └── .gitkeep
├── model_store/                           ← TorchServe 로드용 모델 저장소
│   └── .gitkeep
├── output/
│   └── .gitkeep
├── AnimatedDrawings/                      ← git 클론
└── logs/
└── .gitkeep

---

## 환경 설치 (Docker 불필요)

### 사전 요구사항

1. **Git**: `git --version`
2. **Miniconda**: https://docs.conda.io/en/latest/miniconda.html
3. **Java JDK 17** (TorchServe 필수):
   - Windows: https://adoptium.net/temurin/releases/ 에서 JDK 17 다운로드·설치 후 `JAVA_HOME` 설정
   - Ubuntu: `sudo apt-get install openjdk-17-jdk`
   - macOS: `brew install openjdk@17`
4. **Intel RealSense SDK 2.0**:
   - Windows: https://github.com/IntelRealSense/librealsense/releases
   - Ubuntu: `sudo apt-get install librealsense2-dkms librealsense2-utils`
5. **필수 시스템 라이브러리 (Linux)**:
```bash
   sudo apt-get install -y libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev
```

### Java 설치 확인

```bash
java -version
# openjdk version "17.x.x" 출력 확인
echo $JAVA_HOME   # Linux/Mac
echo %JAVA_HOME%  # Windows
```

### 자동 설치 스크립트: `setup_env.sh` (Linux/Mac)

```bash
#!/usr/bin/env bash
set -e

echo "=== [1/6] AnimatedDrawings 저장소 클론 ==="
if [ ! -d "AnimatedDrawings" ]; then
    git clone https://github.com/facebookresearch/AnimatedDrawings.git AnimatedDrawings
fi

echo "=== [2/6] Conda 환경 생성 (Python 3.8.13) ==="
conda create -y --name animated_drawings python=3.8.13
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate animated_drawings

echo "=== [3/6] AnimatedDrawings 패키지 설치 ==="
cd AnimatedDrawings
pip install -e .
cd ..

echo "=== [4/6] 추가 의존성 설치 (TorchServe, RealSense 포함) ==="
pip install -r requirements.txt

echo "=== [5/6] 사전 학습 모델 가중치 다운로드 ==="
mkdir -p model_store
# AnimatedDrawings 공식 릴리즈에서 .mar 파일 다운로드
wget -O model_store/drawn_humanoid_detector.mar \
    https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_detector.mar
wget -O model_store/drawn_humanoid_pose_estimator.mar \
    https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_pose_estimator.mar

echo "=== [6/6] TorchServe 설정 파일 생성 ==="
cat > config/torchserve_config.properties << EOF
inference_address=http://127.0.0.1:8080
management_address=http://127.0.0.1:8081
metrics_address=http://127.0.0.1:8082
model_store=./model_store
load_models=drawn_humanoid_detector.mar,drawn_humanoid_pose_estimator.mar
default_workers_per_model=1
disable_token_authorization=true
enable_envvars_config=true
EOF

echo "✅ 환경 설치 완료! 실행: ./start_torchserve.sh && python main.py"
```

### 자동 설치 스크립트: `setup_env.bat` (Windows)

```batch
@echo off
setlocal

echo === [1/6] AnimatedDrawings 저장소 클론 ===
if not exist "AnimatedDrawings" (
    git clone https://github.com/facebookresearch/AnimatedDrawings.git AnimatedDrawings
)

echo === [2/6] Conda 환경 생성 ===
call conda create -y --name animated_drawings python=3.8.13
call conda activate animated_drawings

echo === [3/6] AnimatedDrawings 패키지 설치 ===
cd AnimatedDrawings
pip install -e .
cd ..

echo === [4/6] 추가 의존성 설치 ===
pip install -r requirements.txt

echo === [5/6] 모델 가중치 다운로드 ===
if not exist "model_store" mkdir model_store
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_detector.mar' -OutFile 'model_store\drawn_humanoid_detector.mar'"
powershell -Command "Invoke-WebRequest -Uri 'https://github.com/facebookresearch/AnimatedDrawings/releases/download/v0.0.1/drawn_humanoid_pose_estimator.mar' -OutFile 'model_store\drawn_humanoid_pose_estimator.mar'"

echo === [6/6] TorchServe 설정 파일 생성 ===
(
    echo inference_address=http://127.0.0.1:8080
    echo management_address=http://127.0.0.1:8081
    echo metrics_address=http://127.0.0.1:8082
    echo model_store=./model_store
    echo load_models=drawn_humanoid_detector.mar,drawn_humanoid_pose_estimator.mar
    echo default_workers_per_model=1
    echo disable_token_authorization=true
    echo enable_envvars_config=true
) > config\torchserve_config.properties

echo 환경 설치 완료!
pause
```

### `requirements.txt`
RealSense
pyrealsense2>=2.55.0
Image & GUI
opencv-python>=4.8.0
Pillow>=9.0.0
numpy>=1.23.0,<1.24
pyyaml>=6.0
requests>=2.28.0
TorchServe (로컬 실행)
torch==1.13.1
torchvision==0.14.1
torchserve==0.9.0
torch-model-archiver==0.9.0
torch-workflow-archiver==0.2.11
OpenMMLab (포즈 추정용)
mmcv-full==1.7.0
mmdet==2.27.0
mmpose==0.29.0
유틸
scikit-image>=0.19.0
scipy>=1.9.0

---

## TorchServe 로컬 기동 (Docker 대신)

### `start_torchserve.sh` (Linux/Mac)

```bash
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

echo "❌ TorchServe 기동 실패. logs/ 디렉터리 확인 필요"
exit 1
```

### `start_torchserve.bat` (Windows)

```batch
@echo off
call conda activate animated_drawings

echo TorchServe 기동 중...
start /B torchserve --start ^
    --ts-config .\config\torchserve_config.properties ^
    --model-store .\model_store ^
    --models drawn_humanoid_detector=drawn_humanoid_detector.mar drawn_humanoid_pose_estimator=drawn_humanoid_pose_estimator.mar ^
    --disable-token-auth ^
    --ncs

echo 초기화 대기 중 (약 30초)...
timeout /t 30 /nobreak
curl -s http://localhost:8080/ping
echo.
echo TorchServe 준비 완료
```

### `stop_torchserve.sh` / `.bat`

```bash
#!/usr/bin/env bash
torchserve --stop
echo "🛑 TorchServe 정지됨"
```

```batch
@echo off
torchserve --stop
echo TorchServe 정지됨
```

---

## 실행 방법

```bash
# 1. 환경 활성화
conda activate animated_drawings

# 2. TorchServe 기동 (최초 1회 또는 재부팅 후)
./start_torchserve.sh       # Linux/Mac
start_torchserve.bat        # Windows

# 3. 정상 동작 확인
curl http://localhost:8080/ping
# 응답: { "status": "Healthy" }

# 4. 메인 프로그램 실행
python main.py

# 5. 종료 시
./stop_torchserve.sh
```

### 앱이 TorchServe를 자동 관리하도록 하는 옵션

`main.py`의 `--auto-serve` 플래그를 사용하면, 앱 시작 시 TorchServe를
자동 기동하고 종료 시 자동 정지한다.

```bash
python main.py --auto-serve
```

---

## 모듈별 구현 명세

### `pipeline/torchserve_launcher.py` ⭐ (Docker 대체 핵심 모듈)

```python
import subprocess
import time
import requests
import os
import signal

class TorchServeLauncher:
    """
    Docker 없이 로컬 파이썬 프로세스로 TorchServe를 제어한다.
    """

    def __init__(self, config_path: str = "./config/torchserve_config.properties",
                 model_store: str = "./model_store"):
        self.config_path = config_path
        self.model_store = model_store
        self.process = None

    def is_running(self) -> bool:
        """TorchServe가 응답하는지 확인."""
        try:
            r = requests.get("http://localhost:8080/ping", timeout=2)
            return r.status_code == 200 and "Healthy" in r.text
        except Exception:
            return False

    def start(self, wait_ready: bool = True, timeout: int = 60) -> bool:
        """
        TorchServe 기동. Java JDK 설치 확인 후 torchserve CLI 호출.
        """
        if self.is_running():
            print("ℹ️ TorchServe 이미 실행 중")
            return True

        # Java 설치 확인
        try:
            subprocess.run(["java", "-version"], check=True,
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        except Exception:
            raise RuntimeError(
                "Java JDK 17이 설치되어 있지 않습니다. "
                "https://adoptium.net/ 에서 설치 후 JAVA_HOME을 설정하세요."
            )

        cmd = [
            "torchserve", "--start",
            "--ts-config", self.config_path,
            "--model-store", self.model_store,
            "--models",
                "drawn_humanoid_detector=drawn_humanoid_detector.mar",
                "drawn_humanoid_pose_estimator=drawn_humanoid_pose_estimator.mar",
            "--disable-token-auth",
            "--ncs"
        ]
        self.process = subprocess.Popen(cmd)

        if wait_ready:
            return self._wait_for_ready(timeout)
        return True

    def _wait_for_ready(self, timeout: int) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.is_running():
                return True
            time.sleep(2)
        return False

    def stop(self) -> None:
        """TorchServe 정상 종료."""
        try:
            subprocess.run(["torchserve", "--stop"], check=False)
        except Exception:
            pass
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
```

**사용 예:**
```python
with TorchServeLauncher() as server:
    # 이 블록 안에서 TorchServe가 실행됨
    client = TorchServeClient()
    result = client.predict_annotations("drawing.png")
# 블록 종료 시 자동 정지
```

---

### `capture/realsense_capture.py`

이전 명세와 동일. `pyrealsense2` 기반 컬러 스트림.

```python
class RealSenseCapture:
    def __init__(self, width=1280, height=720, fps=30): ...
    def start(self) -> None: ...
    def get_color_frame(self) -> np.ndarray | None: ...
    def stop(self) -> None: ...
    def capture_still(self, save_path: str) -> str: ...
```

### `capture/image_preprocessor.py`

흰 배경에서 손그림을 감지·크롭하여 AnimatedDrawings가 기대하는 정사각
이미지로 변환. 이전 명세와 동일.

### `pipeline/torchserve_client.py`

REST API 호출. Docker 버전과 동일하며 엔드포인트 URL만 localhost 유지.

```python
class TorchServeClient:
    BASE_URL = "http://localhost:8080"

    def is_healthy(self) -> bool: ...
    def predict_annotations(self, image_path: str) -> dict: ...
    def wait_for_ready(self, max_wait: int = 60) -> bool: ...
```

### `pipeline/annotation_runner.py`

`AnimatedDrawings/examples/image_to_annotations.py`의 `image_to_annotations()`를
import하여 그대로 호출. 해당 함수는 내부에서 `http://localhost:8080`으로
REST 요청을 보내므로 Docker/로컬 어느 쪽이든 투명하게 동작한다.

```python
import sys
from pathlib import Path

# AnimatedDrawings/examples 디렉터리를 파이썬 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "AnimatedDrawings" / "examples"))
from image_to_annotations import image_to_annotations

def run_annotation(image_path: str, output_dir: str) -> bool:
    try:
        image_to_annotations(image_path, output_dir)
        return True
    except Exception as e:
        logging.error(f"Annotation 실패: {e}")
        return False
```

### `pipeline/animation_runner.py`

MVC YAML config를 동적으로 생성하고 `render.start()` 호출.
(Docker 여부와 무관하게 동일)

### `gui/main_window.py`

tkinter 기반 GUI. 이전 명세와 동일하되, 시작 시 `TorchServeLauncher`로
서버 기동 여부를 표시.

### `main.py`

```python
def main():
    """
    실행 흐름:
    1. app_config.yaml 로드
    2. --auto-serve 플래그가 있으면 TorchServeLauncher로 서버 자동 기동
    3. TorchServe 헬스체크 (미실행 시 `./start_torchserve.sh` 안내)
    4. RealSenseCapture 초기화
    5. GUI 실행 또는 CLI 모드 실행
    6. 종료 시 자원 해제 (+ auto-serve면 TorchServe 정지)
    """
```

---

## 전체 처리 파이프라인 (Docker-Free)
[사전 1회] setup_env.sh 실행
├─ conda 환경 생성
├─ AnimatedDrawings git clone + pip install -e .
├─ requirements.txt로 torchserve, pyrealsense2 설치
└─ GitHub Releases에서 .mar 모델 파일 다운로드
[실행 시] start_torchserve.sh 실행
└─ torchserve --start ... (로컬 Java 프로세스로 구동, 포트 8080)
[실행 시] python main.py
├─ TorchServe ping 확인
├─ D455 카메라 스트림 시작
├─ [캡처 버튼] → 프레임 → 전처리 → localhost:8080 추론 요청
├─ mask/texture/char_cfg 생성
├─ render.start(mvc_cfg.yaml) → 애니메이션 렌더링
└─ GIF/MP4 결과 재생 및 저장

---

## 대안 아키텍처 (TorchServe도 완전히 제거하고 싶다면)

TorchServe 자체도 부담스럽다면, **직접 PyTorch로 모델 추론**하는 방식도
가능하다. 단, AnimatedDrawings 공식 저장소는 `.mar` 포맷 모델만 배포하므로
다음 추가 작업이 필요하다.

1. `.mar` 파일을 `unzip`하여 `.pth` 가중치와 핸들러 스크립트 추출
2. OpenMMLab의 `mmdet.apis.init_detector / inference_detector`로 감지 수행
3. `mmpose.apis.init_pose_model / inference_top_down_pose_model`로 포즈 추정
4. AnimatedDrawings의 REST 응답 포맷으로 결과 변환

**구현 난이도가 높으므로 1차 버전은 로컬 TorchServe 방식을 권장한다.**
대안 구현은 `pipeline/direct_inference.py`로 분리하여 선택 옵션으로 제공.

---

## 오류 처리 가이드 (Docker-Free 특화)

| 상황 | 해결 방법 |
|---|---|
| `java: command not found` | JDK 17 설치 및 `JAVA_HOME` 환경변수 설정 |
| `torchserve: command not found` | `pip install torchserve torch-model-archiver` 재실행 |
| TorchServe 기동 후 모델 로드 실패 | `model_store/` 디렉터리에 `.mar` 파일 존재 확인, `logs/ts_log.log` 점검 |
| 포트 8080 이미 사용 중 | 기존 프로세스 종료 또는 `torchserve_config.properties`에서 포트 변경 |
| `Empty reply from server` | 10~30초 추가 대기 (초기 모델 로딩 시간) |
| Windows 방화벽 차단 | 최초 실행 시 방화벽 허용 팝업에서 "허용" 선택 |
| Out of Memory | 시스템 RAM 16GB+ 권장. 불필요한 앱 종료 |

---

## 테스트

```bash
# 1. TorchServe 기동
./start_torchserve.sh

# 2. 헬스체크
curl http://localhost:8080/ping
# { "status": "Healthy" }

# 3. 샘플 이미지로 전체 파이프라인 테스트
python main.py --image AnimatedDrawings/examples/drawings/garlic.png \
               --output ./output/test_garlic \
               --motion dab \
               --headless

# 4. 단위 테스트
python -m pytest tests/ -v
```

---

## 개발 시 주의사항

1. **Java 17 필수**: TorchServe는 Java 런타임 기반. 환경변수 `JAVA_HOME` 설정 필수.
2. **.mar 파일 다운로드 경로**: AnimatedDrawings GitHub Releases v0.0.1에서 제공.
3. **첫 실행 지연**: TorchServe 최초 기동 시 모델 로딩에 20~30초 소요.
4. **메모리 사용량**: 로컬 TorchServe는 약 3~5GB RAM 사용 (모델 포함).
5. **포트 충돌 회피**: 8080/8081/8082 포트를 사용하는 다른 서비스 종료.
6. **Python 3.8.13 고정**: OpenMMLab, AnimatedDrawings 호환성.
7. **Windows 경로**: 경로 구분자 `\` vs `/` 혼용 주의. `pathlib.Path` 사용 권장.
8. **AnimatedDrawings 아카이브 상태**: 2025년 9월부터 유지보수 중단, 버전 고정 사용.

---

## Docker 버전 대비 장단점

| 항목 | Docker 버전 | 로컬 TorchServe (본 문서) |
|---|---|---|
| 설치 난이도 | 중간 (Docker Desktop 필요) | 중상 (Java + pip 다수) |
| 초기 빌드 시간 | 5~7분 (이미지 빌드) | 3~5분 (pip install) |
| 실행 시간 메모리 | 격리된 컨테이너 RAM | 호스트 RAM 직접 사용 (약간 더 적음) |
| 재현성 | 매우 높음 | OS별 차이 존재 |
| 디버깅 | 컨테이너 로그 분리 | 로컬 로그 직접 확인 쉬움 |
| Windows 지원 | Docker Desktop 라이선스 이슈 | 문제 없음 |
| CPU/GPU 전환 | 이미지 재빌드 필요 | `pip install torch==...` 만 재실행 |

---

## 참고 자료

- AnimatedDrawings: https://github.com/facebookresearch/AnimatedDrawings
- TorchServe 공식 문서: https://pytorch.org/serve/
- TorchServe 로컬 설치: https://github.com/pytorch/serve#install-torchserve
- AnimatedDrawings 로컬 macOS 설정: https://github.com/facebookresearch/AnimatedDrawings/tree/main/torchserve
- Intel RealSense SDK: https://github.com/IntelRealSense/librealsense
- OpenJDK 17 다운로드: https://adoptium.net/