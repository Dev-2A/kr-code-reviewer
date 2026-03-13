"""LLM 기반 코드 리뷰 생성 모듈"""

from __future__ import annotations

from dataclasses import dataclass, field

import anthropic

from .config import Config
from .diff_parser import FileDiff, ParsedDiff


@dataclass
class ReviewComment:
    """개별 리뷰 코멘트"""
    
    file_path: str
    line_range: str     # e.g. "L10-L15"
    severity: str       # critical, warning, suggestion, nitpick
    category: str       # bug, security, performance, style, readability, logic
    comment: str
    suggestion: str = ""    # 개선 코드 제안 (있을 경우)


@dataclass
class ReviewResult:
    """전체 리뷰 결과"""
    
    summary: str = ""
    comments: list[ReviewComment] = field(default_factory=list)
    overall_score: int = 0  # 1~10
    diff_summary: str = ""
    
    @property
    def critical_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "critical")
    
    @property
    def warning_count(self) -> int:
        return sum(1 for c in self.comments if c.severity == "warning")
    
    @property
    def suggestion_count(self) -> int:
        return sum(1 for c in self.comments if c.severity in ("suggestion", "nitpick"))


SYSTEM_PROMPT = """\
당신은 시니어 소프트웨어 엔지니어이자 코드 리뷰어입니다.
주어진 git diff를 분석하고 한국어로 코드 리뷰를 작성합니다.

## 리뷰 원칙
1. 버그, 보안 취약점, 성능 문제를 최우선으로 지적합니다.
2. 코드 가독성과 유지보수성을 평가합니다.
3. 불필요한 지적은 하지 않습니다. 의미 있는 피드백만 제공합니다.
4. 각 코멘트에는 구체적인 이유와 가능하면 개선 코드를 제안합니다.
5. 전체적인 변경사항에 대한 요약과 점수(1~10)를 제공합니다.

## 심각도 기준
- critical: 반드시 수정해야 하는 버그, 보안 취약점
- warning: 수정을 강력히 권장하는 문제 (성능, 잠재적 버그)
- suggestion: 개선하면 좋을 사항 (가독성, 구조)
- nitpick: 사소한 스타일 지적

## 카테고리
- bug: 논리 오류, 런타임 에러 가능성
- security: 보안 취약점
- performance: 성능 문제
- style: 코딩 컨벤션, 포맷팅
- readability: 가독성, 네이밍
- logic: 비즈니스 로직 관련

## 응답 형식
반드시 아래 XML 형식으로 응답하세요.

<review>
  <summary>전체 변경사항에 대한 한국어 요약 (2~3문장)</summary>
  <score>점수(1~10)</score>
  <comments>
    <comment>
      <file>파일경로</file>
      <line>L시작-L끝</line>
      <severity>심각도</severity>
      <category>카테고리</category>
      <body>한국어 리뷰 코멘트</body>
      <suggestion>개선 코드 (없으면 빈 태그)</suggestion>
    </comment>
  </comments>
</review>
"""


def _build_diff_prompt(parsed_diff: ParsedDiff, max_lines: int = 500) -> str:
    """파싱된 diff를 LLM 프롬프트용 문자열로 변환합니다."""
    parts: list[str] = []
    total_liens = 0
    
    for file_diff in parsed_diff.files:
        # 바이너리, 설정 파일 등 리뷰 불필요한 파일 스킵
        if _should_skip_file(file_diff):
            continue
        
        file_header = f"\n### 파일: {file_diff.new_path} ({file_diff.language}, {file_diff.status})\n"
        parts.append(file_header)
        
        for hunk in file_diff.hunks:
            hunk_text = f"\n{hunk.header}\n{hunk.content}\n"
            hunk_line_count = len(hunk.content.splitlines())
            
            if total_liens + hunk_line_count > max_lines:
                parts.append("\n... (diff가 너무 길어 일부 생략됨)\n")
                return "\n".join(parts)
            
            parts.append(hunk_text)
            total_liens += hunk_line_count
    
    return "\n".join(parts)


def _should_skip_file(file_diff: FileDiff) -> bool:
    """리뷰할 필요 없는 파일인지 판별합니다."""
    skip_extensions = {
        "lock", "svg", "png", "jpg", "jpeg", "gif", "ico",
        "woff", "woff2", "ttf", "eot", "map",
    }
    skip_filenames = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "poetry.lock", "Pipfile.lock", "composer.lock",
        ".gitignore", ".editorconfig", "LICENSE",
    }
    
    if file_diff.extension in skip_extensions:
        return True
    
    filename = file_diff.new_path.rsplit("/", 1)[-1] if "/" in file_diff.new_path else file_diff.new_path
    if filename in skip_filenames:
        return True
    
    return False


def _parse_review_xml(text: str) -> ReviewResult:
    """LLM 응답에서 XML을 파싱하여 ReviewResult를 생성합니다."""
    result = ReviewResult()
    
    # summary 추출
    summary_start = text.find("<summary>")
    summary_end = text.find("</summary>")
    if summary_start != -1 and summary_end != -1:
        result.summary = text[summary_start + 9:summary_end].strip()
    
    # score 추출
    score_start = text.find("<score>")
    score_end = text.find("</score>")
    if score_start != -1 and score_end != -1:
        try:
            result.overall_score = int(text[score_start + 7:score_end].strip())
        except ValueError:
            result.overall_score = 0
    
    # comments 추출
    comments_text = text
    while True:
        comment_start = comments_text.find("<comment>")
        comment_end = comments_text.find("</comment>")
        if comment_start == -1 or comment_end == -1:
            break
        
        comment_block = comments_text[comment_start:comment_end + 10]
        comments_text = comments_text[comment_end + 10:]
        
        comment = _parse_single_comment(comment_block)
        if comment:
            result.comments.append(comment)
    
    return result


def _parse_single_comment(block: str) -> ReviewComment | None:
    """단일 comment XML 블록을 파싱합니다."""
    
    def _extract_tag(tag: str, text: str) -> str:
        start = text.find(f"<{tag}>")
        end = text.find(f"</{tag}>")
        if start != -1 and end != -1:
            return text[start + len(tag) + 2:end].strip()
        return ""
    
    file_path = _extract_tag("file", block)
    body = _extract_tag("body", block)
    
    if not file_path or not body:
        return None
    
    return ReviewComment(
        file_path=file_path,
        line_range=_extract_tag("line", block),
        severity=_extract_tag("severity", block) or "suggestion",
        category=_extract_tag("category", block) or "readability",
        comment=body,
        suggestion=_extract_tag("suggestion", block),
    )


class CodeReviewer:
    "Anthropic API를 사용한 코드 리뷰어"
    
    def __init__(self, config: Config):
        self.config = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    
    def review_diff(self, parsed_diff: ParsedDiff) -> ReviewResult:
        """파싱된 diff를 리뷰합니다."""
        if not parsed_diff.files:
            return ReviewResult(summary="변경사항이 없습니다.")
        
        diff_prompt = _build_diff_prompt(parsed_diff, self.config.max_diff_lines)
        diff_summary = parsed_diff.summary()
        
        user_message = (
            f"아래 git diff를 리뷰해주세요.\n\n"
            f"**변경 요약:** {diff_summary}\n\n"
            f"```diff\n{diff_prompt}\n```"
        )
        
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        
        response_text = response.content[0].text
        result = _parse_review_xml(response_text)
        result.diff_summary = diff_summary
        
        return result
    
    def review_file_diff(self, file_diff: FileDiff) -> ReviewResult:
        """단일 파일의 diff를 리뷰합니다."""
        single_parsed = ParsedDiff(files=[file_diff])
        single_parsed = ParsedDiff(files=[file_diff])
        return self.review_diff(single_parsed)