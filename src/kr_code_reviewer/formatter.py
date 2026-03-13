"""리뷰 결과 포매팅 모듈"""

from __future__ import annotations
from .reviewer import ReviewComment, ReviewResult


# 심각도별 이모지 매핑
SEVERITY_EMOJI: dict[str, str] = {
    "critical": "🚨",
    "warning": "⚠️",
    "suggestion": "💡",
    "nitpick": "🔍",
}

# 심각도별 한국어 라벨
SEVERITY_LABEL: dict[str, str] = {
    "critical": "치명적",
    "warning": "경고",
    "suggestion": "제안",
    "nitpick": "사소한 지적",
}

# 카테고리별 이모지 매핑
CATEGORY_EMOJI: dict[str, str] = {
    "bug": "🐛",
    "security": "🔒",
    "performance": "⚡",
    "style": "🎨",
    "readability": "📖",
    "logic": "🧠",
}

# 점수별 등급
SCORE_GRADE: dict[range, str] = {
    range(9, 11): "🟢 훌륭함",
    range(7, 9): "🟡 양호",
    range(5, 7): "🟠 개선 필요",
    range(1, 5): "🔴 심각한 문제",
}


def _get_score_grade(score: int) -> str:
    """점수에 해당하는 등급 문자열을 반환합니다."""
    for score_range, grade in SCORE_GRADE.items():
        if score in score_range:
            return grade
    return "⚪ 평가 불가"


def _format_comment_markdown(comment: ReviewComment, index: int) -> str:
    """개별 코멘트를 마크다운으로 포매팅합니다."""
    severity_emoji = SEVERITY_EMOJI.get(comment.severity, "❓")
    severity_label = SEVERITY_LABEL.get(comment.severity, comment.severity)
    category_emoji = CATEGORY_EMOJI.get(comment.category, "📌")

    lines = [
        f"### {index}. {severity_emoji} [{severity_label}] {category_emoji} {comment.category}",
        f"",
        f"**파일:** `{comment.file_path}`",
    ]

    if comment.line_range:
        lines.append(f"**라인:** {comment.line_range}")

    lines.append(f"")
    lines.append(comment.comment)

    if comment.suggestion:
        lines.append(f"")
        lines.append(f"**개선 제안:**")
        lines.append(f"```")
        lines.append(comment.suggestion)
        lines.append(f"```")

    return "\n".join(lines)


def format_review_markdown(result: ReviewResult) -> str:
    """ReviewResult를 마크다운 문자열로 포매팅합니다."""
    lines: list[str] = []

    # 헤더
    lines.append("# 🧩 코드 리뷰 결과")
    lines.append("")

    # 변경사항 요약
    if result.diff_summary:
        lines.append(f"> 📊 **변경사항:** {result.diff_summary}")
        lines.append("")

    # 점수
    if result.overall_score > 0:
        grade = _get_score_grade(result.overall_score)
        lines.append(f"## 📈 점수: {result.overall_score}/10 {grade}")
        lines.append("")

    # 전체 요약
    if result.summary:
        lines.append("## 📝 요약")
        lines.append("")
        lines.append(result.summary)
        lines.append("")

    # 통계
    if result.comments:
        lines.append("## 📊 통계")
        lines.append("")
        lines.append(f"| 심각도 | 개수 |")
        lines.append(f"|--------|------|")
        if result.critical_count:
            lines.append(f"| 🚨 치명적 | {result.critical_count} |")
        if result.warning_count:
            lines.append(f"| ⚠️ 경고 | {result.warning_count} |")
        if result.suggestion_count:
            lines.append(f"| 💡 제안/사소 | {result.suggestion_count} |")
        lines.append(f"| **합계** | **{len(result.comments)}** |")
        lines.append("")

    # 개별 코멘트
    if result.comments:
        lines.append("## 💬 상세 리뷰")
        lines.append("")

        # 심각도 순으로 정렬
        severity_order = {"critical": 0, "warning": 1, "suggestion": 2, "nitpick": 3}
        sorted_comments = sorted(
            result.comments,
            key=lambda c: severity_order.get(c.severity, 99),
        )

        for i, comment in enumerate(sorted_comments, 1):
            lines.append(_format_comment_markdown(comment, i))
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("## ✅ 특이사항 없음")
        lines.append("")
        lines.append("리뷰할 이슈가 발견되지 않았습니다. 좋은 코드입니다!")
        lines.append("")

    return "\n".join(lines)


def format_review_compact(result: ReviewResult) -> str:
    """ReviewResult를 간결한 한 줄 형식으로 포매팅합니다. (터미널 출력용)"""
    lines: list[str] = []

    # 점수 + 요약
    grade = _get_score_grade(result.overall_score) if result.overall_score > 0 else ""
    lines.append(f"점수: {result.overall_score}/10 {grade}")

    if result.diff_summary:
        lines.append(f"변경: {result.diff_summary}")

    lines.append(f"코멘트: 🚨{result.critical_count} ⚠️{result.warning_count} 💡{result.suggestion_count}")
    lines.append("")

    if result.summary:
        lines.append(result.summary)
        lines.append("")

    # 코멘트 간결 출력
    severity_order = {"critical": 0, "warning": 1, "suggestion": 2, "nitpick": 3}
    sorted_comments = sorted(
        result.comments,
        key=lambda c: severity_order.get(c.severity, 99),
    )

    for comment in sorted_comments:
        emoji = SEVERITY_EMOJI.get(comment.severity, "❓")
        loc = f" ({comment.line_range})" if comment.line_range else ""
        lines.append(f"  {emoji} {comment.file_path}{loc}")
        lines.append(f"    {comment.comment}")
        if comment.suggestion:
            lines.append(f"    → {comment.suggestion}")
        lines.append("")

    return "\n".join(lines)


def format_review_github_comment(result: ReviewResult) -> str:
    """ReviewResult를 GitHub PR 코멘트용으로 포매팅합니다."""
    lines: list[str] = []

    # 헤더
    lines.append("## 🧩 KR Code Reviewer")
    lines.append("")

    # 점수
    if result.overall_score > 0:
        grade = _get_score_grade(result.overall_score)
        lines.append(f"**점수:** {result.overall_score}/10 {grade}")
        lines.append("")

    # 요약
    if result.summary:
        lines.append(f"> {result.summary}")
        lines.append("")

    # 통계 (인라인)
    if result.comments:
        stats_parts = []
        if result.critical_count:
            stats_parts.append(f"🚨 치명적 {result.critical_count}")
        if result.warning_count:
            stats_parts.append(f"⚠️ 경고 {result.warning_count}")
        if result.suggestion_count:
            stats_parts.append(f"💡 제안 {result.suggestion_count}")
        lines.append(f"**코멘트:** {' / '.join(stats_parts)}")
        lines.append("")

    # 코멘트 (접이식)
    if result.comments:
        severity_order = {"critical": 0, "warning": 1, "suggestion": 2, "nitpick": 3}
        sorted_comments = sorted(
            result.comments,
            key=lambda c: severity_order.get(c.severity, 99),
        )

        lines.append("<details>")
        lines.append("<summary>상세 리뷰 보기</summary>")
        lines.append("")

        for comment in sorted_comments:
            emoji = SEVERITY_EMOJI.get(comment.severity, "❓")
            severity_label = SEVERITY_LABEL.get(comment.severity, comment.severity)
            loc = f" `{comment.line_range}`" if comment.line_range else ""

            lines.append(f"#### {emoji} [{severity_label}] `{comment.file_path}`{loc}")
            lines.append("")
            lines.append(comment.comment)

            if comment.suggestion:
                lines.append("")
                lines.append("```suggestion")
                lines.append(comment.suggestion)
                lines.append("```")

            lines.append("")

        lines.append("</details>")
        lines.append("")

    # 푸터
    lines.append("---")
    lines.append("*Generated by [KR Code Reviewer](https://github.com/Dev-2A/kr-code-reviewer)*")

    return "\n".join(lines)