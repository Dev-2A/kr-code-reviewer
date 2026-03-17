# 🧩 KR Code Reviewer

PR diff를 읽고 한국어로 코드 리뷰 코멘트를 자동 생성하는 CLI 도구 + GitHub Action입니다.

## 기능

- 🔍 `git diff` 파싱 및 변경사항 분석
- 🤖 Anthropic Claude API 기반 코드 리뷰 생성
- 🇰🇷 한국어 리뷰 코멘트 출력 (영어도 지원)
- 💻 CLI로 로컬 diff / diff 파일 리뷰
- 🔗 GitHub PR에 자동 코멘트
- ⚡ GitHub Actions 워크플로우 지원
- 📊 심각도별 분류 (치명적 / 경고 / 제안 / 사소)
- 📝 마크다운, 터미널, GitHub 코멘트 3가지 출력 형식

## 기술 스택

- **Language:** Python 3.11+
- **LLM:** Anthropic Claude API
- **CLI:** Click
- **GitHub 연동:** PyGithub
- **테스트:** pytest

## 설치

### 저장소 클론

```bash
git clone https://github.com/Dev-2A/kr-code-reviewer.git
cd kr-code-reviewer
```

### 가상환경 설정

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 의존성 설치

```bash
pip install -r requirements.txt
pip install -e .
```

## 설정

### 1. API 키 발급

- **Anthropic API Key:** [console.anthropic.com](https://console.anthropic.com/)에서 발급
- **GitHub Token:** GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)에서 발급 (repo, workflow 권한 필요)

### 2. 환경변수 설정

프로젝트 루트에 `.env` 파일 생성:

```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
GITHUB_TOKEN=ghp_xxxxx
```

### 3. 설정 확인

```bash
kr-review check
```

## 사용법

### 로컬 diff 리뷰

```bash
# staged 변경사항 리뷰 (기본)
kr-review review

# working directory 변경사항 리뷰
kr-review review --source working

# 브랜치 비교 리뷰
kr-review review --source branch --base main

# 특정 커밋 리뷰
kr-review review --source commit --commit abc1234

# 마크다운 파일로 저장
kr-review review --format markdown -o review.md
```

### diff 파일 리뷰

```bash
kr-review review-file my_changes.diff
kr-review review-file my_changes.patch --format markdown -o review.md
```

### GitHub PR 리뷰

```bash
# PR URL로 리뷰
kr-review pr https://github.com/owner/repo/pull/1

# 축약 형식
kr-review pr owner/repo#1

# 리뷰 후 자동으로 PR에 코멘트 작성
kr-review pr owner/repo#1 --post

# 마크다운으로 저장
kr-review pr owner/repo#1 --format markdown -o review.md
```

### GitHub Actions 사용

리뷰할 레포지토리에 `.github/workflows/review.yml`을 추가:

```yaml
name: Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Dev-2A/kr-code-reviewer@main
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
```

레포지토리의 Settings → Secrets and variables → Actions에서 `ANTHROPIC_API_KEY`를 등록해야 합니다.

## 출력 예시

### 터미널 (compact)

```text
점수: 8/10 🟡 양호
변경: 3개 파일 변경, +45 추가, -12 삭제
코멘트: 🚨0 ⚠️1 💡2

설정 모듈을 추가하고 환경변수 로딩을 구현했습니다.

  ⚠️ src/config.py (L15-L20)
    API 키가 비어있을 때 빈 문자열로 초기화하면 이후 로직에서 문제가 됩니다.
    → api_key = os.getenv("API_KEY") or raise ValueError(...)

  💡 src/config.py (L30)
    max_diff_lines의 기본값 500은 매직 넘버입니다. 상수로 분리하면 좋겠습니다.
```

### GitHub PR 코멘트

PR에 자동으로 작성되는 코멘트는 접이식(`<details>`)으로 깔끔하게 표시됩니다.

## 프로젝트 구조

```text
kr-code-reviewer/
├── .github/workflows/     # GitHub Actions 워크플로우
│   └── review.yml
├── src/kr_code_reviewer/  # 메인 소스 코드
│   ├── cli.py             # CLI 인터페이스
│   ├── config.py          # 설정 관리
│   ├── diff_parser.py     # Git diff 파서
│   ├── formatter.py       # 출력 포매터
│   ├── github_client.py   # GitHub API 연동
│   ├── prompts.py         # LLM 프롬프트
│   └── reviewer.py        # 리뷰 생성기
├── tests/                 # 테스트
│   ├── test_diff_parser.py
│   ├── test_formatter.py
│   └── test_reviewer.py
├── action.yml             # 재사용 가능한 GitHub Action
├── pyproject.toml         # 패키지 설정
└── requirements.txt       # 의존성
```

## 테스트

```bash
pip install pytest
pytest tests/ -v
```

## 라이선스

MIT License
