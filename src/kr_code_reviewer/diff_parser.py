"""Git diff 파싱 모듈"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field


@dataclass
class DiffHunk:
    """diff의 개별 변경 블록(hunk)"""
    
    start_line_old: int
    start_line_new: int
    count_old: int
    count_new: int
    content: str
    header: str = ""


@dataclass
class FileDiff:
    """단일 파일의 diff 정보"""
    
    old_path: str
    new_path: str
    status: str     # added, modified, deleted, renamed
    hunks: list[DiffHunk] = field(default_factory=list)
    language: str = ""
    
    @property
    def extension(self) -> str:
        """파일 확장자를 반환합니다."""
        if "." in self.new_path:
            return self.new_path.rsplit(".", 1)[-1].lower()
        return ""
    
    @property
    def added_lines(self) -> list[str]:
        """추가된 라인만 반환합니다."""
        lines = []
        for hunk in self.hunks:
            for line in hunk.content.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    lines.append(line[1:])
        return lines
    
    @property
    def removed_lines(self) -> list[str]:
        """삭제된 라인만 반환합니다."""
        lines = []
        for hunk in self.hunks:
            for line in hunk.content.splitlines():
                if line.startswith("-") and not line.startswith("---"):
                    lines.append(line[1:])
        return lines


@dataclass
class ParsedDiff:
    """파싱된 전체 diff"""
    
    files: list[FileDiff] = field(default_factory=list)
    raw_diff: str = ""
    
    @property
    def total_additions(self) -> int:
        return sum(len(f.added_lines) for f in self.files)
    
    @property
    def total_deletions(self) -> int:
        return sum(len(f.removed_lines) for f in self.files)
    
    @property
    def file_count(self) -> int:
        return len(self.files)
    
    def summary(self) -> str:
        """변경사항 요약 문자열을 반환합니다."""
        return (
            f"{self.file_count}개 파일 변경, "
            f"+{self.total_additions} 추가, "
            f"-{self.total_deletions} 삭제"
        )


# 확장자 → 언어 매핑
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    "py": "Python",
    "js": "JavaScript",
    "ts": "TypeScript",
    "jsx": "React JSX",
    "tsx": "React TSX",
    "java": "Java",
    "kt": "Kotlin",
    "go": "Go",
    "rs": "Rust",
    "rb": "Ruby",
    "php": "PHP",
    "cs": "C#",
    "cpp": "C++",
    "c": "C",
    "h": "C/C++ Header",
    "swift": "Swift",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "scss": "SCSS",
    "yaml": "YAML",
    "yml": "YAML",
    "toml": "TOML",
    "json": "JSON",
    "md": "Markdown",
    "sh": "Shell",
    "bat": "Batch",
    "ps1": "PowerShell",
    "dockerfile": "Dockerfile",
}


def detect_language(file_path: str) -> str:
    """파일 경로에서 프로그래밍 언어를 감지합니다."""
    # Dockerfile 등 확장자 없는 특수 파일
    filename = file_path.rsplit("/", 1)[-1].lower() if "/" in file_path else file_path.lower()
    if filename == "dockerfile":
        return "Dockerfile"
    if filename == "makefile":
        return "Makefile"
    
    if "." in file_path:
        ext = file_path.rsplit(".", 1) [-1].lower()
        return EXTENSION_LANGUAGE_MAP.get(ext, ext.upper())
    return "Unknown"


def _parse_hunk_header(header: str) -> tuple[int, int, int, int]:
    """@@ -a,b +c,d @@ 형식의 헤더를 파싱합니다."""
    # @@ -10,5 +10,8 @@ 에서 숫자 추출
    try:
        parts = header.split("@@")[1].strip()
        old_part, new_part = parts.split(" ")
        
        # -10,5 → (10, 5)
        old_vals = old_part.lstrip("-").split(",")
        old_start = int(old_vals[0])
        old_count = int(old_vals[1]) if len(old_vals) > 1 else 1
        
        # +10,8 → (10, 8)
        new_vals = new_part.lstrip("+").split(",")
        new_start = int(new_vals[0])
        new_count = int(new_vals[1]) if len(new_vals) > 1 else 1
        
        return old_start, old_count, new_start, new_count
    except (IndexError, ValueError):
        return 0, 0, 0, 0


def _detect_file_status(old_path: str, new_path: str) -> str:
    """파일의 변경 상태를 판별합니다."""
    if old_path == "/dev/null":
        return "added"
    if new_path == "/dev/null":
        return "deleted"
    if old_path != new_path:
        return "renamed"
    return "modified"


def parse_diff_text(diff_text: str) -> ParsedDiff:
    """diff 텍스트 문자열을 파싱합니다."""
    if not diff_text.strip():
        return ParsedDiff(raw_diff=diff_text)
    
    files: list[FileDiff] = []
    current_file: FileDiff | None = None
    current_hunk_lines: list[str] = []
    current_hunk_header: str = ""
    hunk_meta: tuple[int, int, int, int] = (0, 0, 0, 0)
    
    def _flush_hunk():
        """현재 hunk를 파일에 추가합니다."""
        nonlocal current_hunk_lines, current_hunk_header, hunk_meta
        if current_file and current_hunk_lines:
            current_file.hunks.append(
                DiffHunk(
                    start_line_old=hunk_meta[0],
                    count_old=hunk_meta[1],
                    start_line_new=hunk_meta[2],
                    count_new=hunk_meta[3],
                    content="\n".join(current_hunk_lines),
                    header=current_hunk_header,
                )
            )
        current_hunk_lines = []
        current_hunk_header = ""
    
    old_path = ""
    new_path = ""
    
    for line in diff_text.splitlines():
        # 새 파일 diff 시작
        if line.startswith("diff --git"):
            _flush_hunk()
            if current_file:
                files.append(current_file)
            
            # diff --git a/path b/path 에서 경로 추출
            parts = line.split(" ")
            if len(parts) >= 4:
                old_path = parts[2][2:]     # a/ 제거
                new_path = parts[3][2:]     # b/ 제거
            current_file = None
            continue
        
        # --- a/path 또는 --- /dev/null
        if line.startswith("--- "):
            path = line[4:]
            if path.startswith("a/"):
                old_path = path[2:]
            elif path == "/dev/null":
                old_path = "/dev/null"
            continue
        
        # +++ b/path 또는 +++ /dev/null
        if line.startswith("+++ "):
            path = line[4:]
            if path.startswith("b/"):
                new_path = path[2:]
            elif path == "/dev/null":
                new_path = "/dev/null"
            
            status = _detect_file_status(old_path, new_path)
            display_path = new_path if new_path != "/dev/null" else old_path
            current_file = FileDiff(
                old_path=old_path,
                new_path=new_path,
                status=status,
                language=detect_language(display_path),
            )
            continue
        
        # hunk 헤더
        if line.startswith("@@"):
            _flush_hunk()
            current_hunk_header = line
            hunk_meta = _parse_hunk_header(line)
            continue
        
        # hunk 내용 (+ - 또는 공백으로 시작하는 라인)
        if current_file is not None and (
            line.startswith("+")
            or line.startswith("-")
            or line.startswith(" ")
            or line == ""
        ):
            current_hunk_lines.append(line)
    
    # 마지막 hunk/파일 flush
    _flush_hunk()
    if current_file:
        files.append(current_file)
    
    return ParsedDiff(files=files, raw_diff=diff_text)


def get_staged_diff() -> str:
    """git에서 staged 변경사항의 diff를 가져옵니다."""
    result = subprocess.run(
        ["git", "diff", "--cached"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def get_working_diff() -> str:
    """git에서 working directory의 diff를 가져옵니다."""
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def get_branch_diff(base: str = "main") -> str:
    """현재 브랜치와 base 브랜치 간의 diff를 가져옵니다."""
    result = subprocess.run(
        ["git", "diff", f"{base}...HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def get_commit_diff(commit_hash: str = "HEAD") -> str:
    """특정 커밋의 diff를 가져옵니다."""
    result = subprocess.run(
        ["git", "diff", f"{commit_hash}~1", commit_hash],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout