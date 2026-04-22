# RealSense × AnimatedDrawings (Docker-Free)

Intel RealSense D455 카메라로 손그림을 실시간 촬영하여 [Meta AnimatedDrawings](https://github.com/facebookresearch/AnimatedDrawings) 파이프라인으로 자동 애니메이션화하는 PC 데스크톱 애플리케이션입니다. **Docker 없이** 순수 Python 환경에서 로컬 TorchServe를 구동하여 ML 추론을 수행합니다.

## 주요 특징

- 🎥 **RealSense D455 실시간 프리뷰** — 전용 캡처 스레드로 프레임 스틸링·메인 스레드 블로킹 제거
- ✂️ **자동 전처리** — 흰 배경 기반 원근 보정 및 정사각 크롭(OpenCV)
- 🤖 **로컬 ML 추론** — 캐릭터 검출(MaskR-CNN) + 포즈 추정(HRNet 계열) on TorchServe
- 🦴 **자동 리깅 + BVH 리타겟** — 6종 모션(dab, jumping, wave_hello 등)을 그림에 맞춰 변형
- 🎬 **2D 스킨드 메쉬 렌더** — OpenGL 기반 GIF/MP4 출력
- 🖥️ **tkinter GUI** — 라이브 프리뷰, 모션 선택, TorchServe 상태 표시, 결과 재생

## 동작 흐름

```
┌─ D455 컬러 프레임 ───▶ 전처리(원근 보정·정사각 크롭)
│
│                        ┌─ drawn_humanoid_detector (.mar)
├─ localhost:8080 ◀──────┤
│                        └─ drawn_humanoid_pose_estimator (.mar)
│
├─ mask.png / texture.png / char_cfg.yaml 생성
│
├─ BVH 모션 로드 + PCA 기반 리타겟
│
└─ 자식 프로세스(GLFW/OpenGL)에서 렌더 ─▶ animation.gif
```

## 사전 요구사항

| 항목 | 버전 | 설치 링크 |
|---|---|---|
| Python | 3.8.13 (conda 환경 권장) | [Miniconda](https://docs.conda.io/en/latest/miniconda.html) |
| Java JDK | 17 이상 (TorchServe 실행) | [Adoptium Temurin](https://adoptium.net/temurin/releases/) |
| Intel RealSense SDK | 2.55+ | [librealsense releases](https://github.com/IntelRealSense/librealsense/releases) |
| Git | 최신 | [git-scm](https://git-scm.com/) |
| GPU | 선택 사항 | CPU 빌드로도 동작 |

> **Note**: Java 설치 후 `JAVA_HOME` 환경변수 설정 및 PATH 등록 필수.

## 설치

```bash
# 저장소 클론
git clone https://github.com/Shinhyoung/2.5DLiveDrawing.git
cd 2.5DLiveDrawing

# 자동 설치 (AnimatedDrawings clone + conda 환경 + 의존성 + .mar 모델 다운로드)
setup_env.bat          # Windows
./setup_env.sh         # Linux/Mac
```

설치 스크립트가 수행하는 작업:
1. Meta `AnimatedDrawings` 저장소를 `AnimatedDrawings/`로 클론
2. Conda 환경 `animated_drawings` 생성 (Python 3.8.13)
3. `pip install -e AnimatedDrawings/` + `requirements.txt` 설치 (PyTorch, mmdet/mmpose/mmcv-full, pyrealsense2 등)
4. GitHub Releases에서 `drawn_humanoid_detector.mar` (312 MB) + `drawn_humanoid_pose_estimator.mar` (358 MB) 다운로드

## 실행

```bash
# TorchServe 기동 (최초 1회 또는 재부팅 후)
start_torchserve.bat   # Windows
./start_torchserve.sh  # Linux/Mac

# 헬스체크
curl http://localhost:8080/ping
# → { "status": "Healthy" }

# 환경 활성화 후 앱 실행
conda activate animated_drawings
python main.py                                   # GUI 모드 (D455 필수)
python main.py --dummy-capture                   # 카메라 없이 GUI UI 확인
python main.py --auto-serve                      # TorchServe 자동 기동/정지
python main.py --image path/to/drawing.png \
               --output ./output/my_run \
               --motion wave_hello --headless    # 헤드리스 단일 실행
```

종료:

```bash
stop_torchserve.bat    # Windows
./stop_torchserve.sh   # Linux/Mac
```

## 웹 데모 (Gradio)

TorchServe가 기동된 상태에서 브라우저에서 파이프라인을 실행할 수 있습니다.

```bash
conda activate animated_drawings
python demo/app.py                      # 기본: 0.0.0.0:7860 + gradio.live 공유 시도
python demo/app.py --no-share           # 로컬/LAN 전용
python demo/app.py --port 8000          # 포트 변경
```

- **LAN 공유**: 같은 네트워크의 다른 기기에서 `http://<호스트-IP>:7860` 접속
- **퍼블릭 URL**: `gradio.live` 터널 실패 시 [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/tunnel-guide/) 사용

```bash
# cloudflared 다운로드 (Windows 예시, 1회)
curl -L -o tools/cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# Gradio가 실행 중인 상태에서 별도 터미널
tools/cloudflared.exe tunnel --url http://localhost:7860
# → https://<무작위-이름>.trycloudflare.com URL 출력
```

데모 화면에서 이미지 업로드 또는 웹캠 촬영 → 모션 선택 → **애니메이션 생성** 버튼. 처리에 15~20초 소요되며 GIF가 우측에 재생됩니다.

## 사용 가능한 모션

| 이름 | 설명 | 호환 스켈레톤 |
|---|---|---|
| `dab` | 팔을 얼굴로 접는 댑 춤 (기본값) | fair1 |
| `jumping` | 제자리 점프 | fair1 |
| `wave_hello` | 손 흔들며 인사 | fair1 |
| `zombie` | 좀비 걸음 | fair1 |
| `jumping_jacks` | 팔벌려뛰기 | cmu1 |

모션별 호환 리타겟은 [pipeline/animation_runner.py](pipeline/animation_runner.py)의 `MOTION_RETARGET_MAP`에서 자동으로 결정됩니다.

## 프로젝트 구조

```
2.5DLiveDrawing/
├── main.py                              엔트리포인트 (GUI / 헤드리스)
├── requirements.txt                     Python 의존성
├── setup_env.{bat,sh}                   환경 자동 설치
├── start_torchserve.{bat,sh}            TorchServe 기동
├── stop_torchserve.{bat,sh}             TorchServe 정지
├── capture/
│   ├── realsense_capture.py             D455 캡처 + BG 스레드 프레임 버퍼
│   └── image_preprocessor.py            원근 보정 + 정사각 크롭
├── pipeline/
│   ├── torchserve_launcher.py           TorchServe 프로세스 제어 (Docker 대체)
│   ├── torchserve_client.py             REST 클라이언트
│   ├── annotation_runner.py             image_to_annotations 래퍼
│   └── animation_runner.py              MVC YAML 생성 + 서브프로세스 렌더
├── gui/
│   ├── main_window.py                   tkinter 메인창
│   ├── camera_preview.py                라이브 프리뷰(스레드 분리)
│   └── result_viewer.py                 GIF/MP4 재생
├── scripts/
│   └── render_animation_cli.py          GLFW 렌더 자식 프로세스 진입점
├── config/
│   ├── app_config.yaml                  앱 설정
│   └── torchserve_config.properties     TorchServe 설정
├── tests/                               단위 테스트
├── AnimatedDrawings/                    (gitignore — setup에서 clone)
├── model_store/                         (gitignore — setup에서 .mar 다운로드)
├── output/                              (gitignore — 런타임 산출물)
└── logs/                                (gitignore — TorchServe 로그)
```

## 설계 포인트

### 1. Docker 제거
Meta 공식 AnimatedDrawings는 Docker Compose로 TorchServe를 기동하지만, 본 프로젝트는 [pipeline/torchserve_launcher.py](pipeline/torchserve_launcher.py)가 `torchserve` CLI를 직접 호출합니다. Java JDK 17과 Python 환경만 있으면 동작하므로 Windows에서도 제약 없이 사용 가능합니다.

### 2. GUI 스레드 안전성
- **프레임 수집**: 전용 `rs-capture` 스레드가 `wait_for_frames()`를 독점하고 최신 프레임을 락 보호 버퍼에 저장. 프리뷰와 캡처가 같은 파이프라인을 경합하지 않음.
- **프리뷰 렌더링**: BG 스레드에서 BGR→RGB·리사이즈까지 수행, 메인 스레드는 `PhotoImage` 생성만 담당.
- **TorchServe 헬스체크**: 동기 HTTP 호출을 `ts-health` 데몬 스레드로 분리.

### 3. Windows GLFW 제약 대응
AnimatedDrawings의 `render.start()`는 GLFW로 OpenGL 창을 생성하는데, Windows에서 **GLFW는 메인 스레드 외부에서 창을 만들 수 없습니다**. GUI의 워커 스레드에서 렌더를 직접 호출하면 실패하므로, [scripts/render_animation_cli.py](scripts/render_animation_cli.py)를 자식 프로세스로 실행하여 깨끗한 메인 스레드에서 GLFW가 동작하도록 분리했습니다.

## 오류 해결

| 증상 | 원인 / 해결 |
|---|---|
| `java: command not found` | JDK 17 설치 후 `JAVA_HOME` 설정 및 PATH 등록 |
| `torchserve: command not found` | `conda activate animated_drawings` 먼저 실행 |
| `Empty reply from server` | 모델 로딩 중 — 20~30초 추가 대기 |
| 포트 8080 사용 중 | 기존 프로세스 종료 또는 [config/torchserve_config.properties](config/torchserve_config.properties)에서 포트 변경 |
| GUI에서 "애니메이션 렌더 실패" | 모션-리타겟 불일치 — 5종 표준 모션만 사용 |
| 프리뷰 멈춤 현상 | RealSense USB 3.0 직결 확인, 다른 카메라 앱 종료 |
| `.model_server.pid` PermissionError | 재기동 전 `stop_torchserve` 실행 또는 pid 파일 수동 삭제 |

## 라이선스 / 크레딧

- 이 저장소의 코드는 MIT 라이선스
- [AnimatedDrawings](https://github.com/facebookresearch/AnimatedDrawings) — MIT © Meta Platforms, Inc.
- [Intel RealSense SDK](https://github.com/IntelRealSense/librealsense) — Apache 2.0
- [TorchServe](https://github.com/pytorch/serve) — Apache 2.0
- [OpenMMLab](https://openmmlab.com/) (mmdet / mmpose / mmcv) — Apache 2.0

## 참고

- 원본 명세서: [claude.md](claude.md)
- AnimatedDrawings 저장소는 2025-09부터 유지보수가 중단되어 버전을 고정(`v0.0.1`)하여 사용합니다.
