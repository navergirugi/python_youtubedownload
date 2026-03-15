# 유튜브 트로트 MP3 추출기 (YouTube Trot MP3 Extractor)

본 프로젝트는 유튜브의 트로트 모음 영상이나 재생목록으로부터 오디오를 추출하여, 메타데이터(가수, 곡제목)를 보정하고 MP3 파일로 저장하는 도구입니다.

## 주요 기능

### 1. 세 가지 영상 처리 케이스 완벽 지원
본 추출기는 다음 세 가지 경우를 자동으로 감지하여 처리합니다:
- **Case 1: 긴 영상 + 본문 타임스탬프**: 영상 설명란에 `01:23 곡제목` 형식의 타임스탬프가 있는 경우, 이를 기준으로 자동 분할합니다.
- **Case 2: 긴 영상 + 유튜브 챕터**: 영상 자체에 유튜브 챕터 기능이 적용된 경우, 챕터 정보를 읽어 분할합니다.
- **Case 3: 짧은 영상 재생목록**: 여러 개의 짧은 영상이 담긴 재생목록 URL을 입력하면, 각 영상을 개별 곡으로 순차 다운로드합니다.

### 2. 메타데이터 자동 보정 (`metadata.json`)
- 유튜브 제목에 가수 이름이 없더라도 약 400곡 이상의 데이터가 축적된 `metadata.json`을 참조하여 원곡 가수를 자동으로 찾아 파일명에 반영합니다.
- `update_meta.py`를 통해 이 데이터베이스를 지속적으로 확장할 수 있습니다.

### 3. 스마트 인덱싱 (번호 공백 채우기)
- 파일을 다운로드할 때 `0001. 가수 - 제목.mp3` 형식을 사용합니다.
- 만약 사용자가 중간 번호(예: 0011번)를 삭제하면, 다음 다운로드 시 빈 번호를 찾아 우선적으로 채워줍니다.

### 4. 볼륨 평준화 (Loudness Normalization)
- 여러 영상에서 추출한 곡들의 볼륨이 제각각인 문제를 해결하기 위해 표준 레벨(EBU R128)로 볼륨을 자동 조절합니다.

## 사용 방법

### 🍎 macOS
맥에서는 파이썬만 설치되어 있다면 바로 생성이 가능합니다.
1. 생성: python3 -m venv .venv
2. 활성화: source .venv/bin/activate

### 🐧 Ubuntu
우분투는 시스템 파이썬 외에 가상환경 모듈을 수동으로 추가해야 합니다.
1. 패키지 설치: sudo apt update && sudo apt install python3-venv -y
2. 생성: python3 -m venv .venv
3. 활성화: source .venv/bin/activate

### 🏛️ CentOS / RHEL
CentOS는 파이썬 개발 도구(devel)에 포함되어 있는 경우가 많습니다.
1. 패키지 설치: sudo dnf install python3 -y
2. 생성: python3 -m venv .venv
3. 활성화: source .venv/bin/activate

## 가상 환경 확인
python3 -c "import sys; print(sys.executable)"

## 잘못된 버전이 설치 되었을때
# 1. 활성화되어 있다면 종료
deactivate

# 2. 기존 가상환경 폴더 삭제 (주의: 소스 코드가 아닌 .venv 폴더만 삭제)
rm -rf .venv

# 3. 시스템의 3.14 버전을 지정해서 다시 생성
python3.14 -m venv .venv

# 4. 가상환경 재활성화
source .venv/bin/activate

# 5. 버전 확인
python --version

## ffmege 설치 - pip 와 별도로 설치 해야 함
- mac => brew install ffmpeg
- ubuntu => sudo apt update && sudo apt install ffmpeg -y
- sudo dnf install epel-release -y && sudo dnf install ffmpeg -y

1. **환경 설정**:
   - Python 3.14.3 설치 (추천 버전)
   - FFmpeg 설치 (시스템 경로에 등록 필요)
   - 의존성 패키지 설치:
     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```

2. **추출 실행**:
   ```bash
   python mp3Extract/extractor.py
   ```
   - 안내에 따라 유튜브 URL을 입력합니다.

3. **메타데이터 업데이트**:
   - `update_meta.py`의 `raw_data` 또는 `combined_hits`에 새로운 곡 정보를 추가한 후 실행하면 `metadata.json`이 갱신됩니다.

## 파일 구성
- `extractor.py`: 핵심 추출 및 분할 로직.
- `metadata.json`: 곡명-가수 매핑 데이터베이스 (추출기가 참조함).
- `update_meta.py`: `metadata.json`을 대량으로 생성/관리하기 위한 도구.
- `data/`: 추출된 MP3 파일이 저장되는 폴더.
