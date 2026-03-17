"""reviewer 모듈 테스트 (API 호출 없이 파싱 로직만 테스트)"""

import pytest

from kr_code_reviewer.reviewer import (
    ReviewComment,
    ReviewResult,
    _parse_review_xml,
    _parse_single_comment,
    _should_skip_file,
)
from kr_code_reviewer.diff_parser import FileDiff


# ============================================================
# _should_skip_file 테스트
# ============================================================

class TestShouldSkipFile:

    def _make_file_diff(self, path: str) -> FileDiff:
        return FileDiff(old_path=path, new_path=path, status="modified")

    def test_skip_lock_file(self):
        assert _should_skip_file(self._make_file_diff("package-lock.json"))

    def test_skip_yarn_lock(self):
        assert _should_skip_file(self._make_file_diff("yarn.lock"))

    def test_skip_image(self):
        assert _should_skip_file(self._make_file_diff("logo.png"))

    def test_skip_svg(self):
        assert _should_skip_file(self._make_file_diff("icon.svg"))

    def test_skip_license(self):
        assert _should_skip_file(self._make_file_diff("LICENSE"))

    def test_skip_gitignore(self):
        assert _should_skip_file(self._make_file_diff(".gitignore"))

    def test_keep_python(self):
        assert not _should_skip_file(self._make_file_diff("main.py"))

    def test_keep_js(self):
        assert not _should_skip_file(self._make_file_diff("app.js"))

    def test_keep_nested_path(self):
        assert not _should_skip_file(self._make_file_diff("src/utils/helper.ts"))


# ============================================================
# _parse_review_xml 테스트
# ============================================================

SAMPLE_XML = """\
<review>
  <summary>설정 모듈을 추가하고 환경변수 로딩을 구현했습니다. 전반적으로 깔끔한 구조입니다.</summary>
  <score>8</score>
  <comments>
    <comment>
      <file>src/config.py</file>
      <line>L15-L20</line>
      <severity>warning</severity>
      <category>security</category>
      <body>API 키가 비어있을 때 빈 문자열로 초기화하면 이후 로직에서 잘못된 요청이 발생할 수 있습니다.</body>
      <suggestion>api_key = os.getenv("API_KEY") or raise ValueError("API_KEY required")</suggestion>
    </comment>
    <comment>
      <file>src/config.py</file>
      <line>L30</line>
      <severity>suggestion</severity>
      <category>readability</category>
      <body>max_diff_lines의 기본값 500은 매직 넘버입니다. 상수로 분리하면 좋겠습니다.</body>
      <suggestion></suggestion>
    </comment>
  </comments>
</review>
"""


class TestParseReviewXml:

    def test_parse_summary(self):
        result = _parse_review_xml(SAMPLE_XML)
        assert "설정 모듈" in result.summary

    def test_parse_score(self):
        result = _parse_review_xml(SAMPLE_XML)
        assert result.overall_score == 8

    def test_parse_comments_count(self):
        result = _parse_review_xml(SAMPLE_XML)
        assert len(result.comments) == 2

    def test_parse_comment_fields(self):
        result = _parse_review_xml(SAMPLE_XML)
        first = result.comments[0]
        assert first.file_path == "src/config.py"
        assert first.line_range == "L15-L20"
        assert first.severity == "warning"
        assert first.category == "security"
        assert "API 키" in first.comment

    def test_parse_empty_suggestion(self):
        result = _parse_review_xml(SAMPLE_XML)
        second = result.comments[1]
        assert second.suggestion == ""

    def test_severity_counts(self):
        result = _parse_review_xml(SAMPLE_XML)
        assert result.critical_count == 0
        assert result.warning_count == 1
        assert result.suggestion_count == 1

    def test_empty_xml(self):
        result = _parse_review_xml("")
        assert result.summary == ""
        assert result.overall_score == 0
        assert len(result.comments) == 0

    def test_malformed_xml(self):
        result = _parse_review_xml("<review><summary>요약</summary></review>")
        assert result.summary == "요약"
        assert len(result.comments) == 0


# ============================================================
# ReviewResult 프로퍼티 테스트
# ============================================================

class TestReviewResult:

    def test_empty_result(self):
        result = ReviewResult()
        assert result.critical_count == 0
        assert result.warning_count == 0
        assert result.suggestion_count == 0

    def test_mixed_severities(self):
        result = ReviewResult(
            comments=[
                ReviewComment("a.py", "L1", "critical", "bug", "버그"),
                ReviewComment("b.py", "L2", "critical", "security", "보안"),
                ReviewComment("c.py", "L3", "warning", "performance", "성능"),
                ReviewComment("d.py", "L4", "nitpick", "style", "스타일"),
            ]
        )
        assert result.critical_count == 2
        assert result.warning_count == 1
        assert result.suggestion_count == 1  # nitpick도 suggestion_count에 포함