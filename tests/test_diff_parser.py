"""diff_parser 모듈 테스트"""

import pytest

from kr_code_reviewer.diff_parser import (
    ParsedDiff,
    detect_language,
    parse_diff_text,
    _parse_hunk_header,
    _detect_file_status,
)


# ============================================================
# detect_language 테스트
# ============================================================

class TestDetectLanguage:

    def test_python(self):
        assert detect_language("src/main.py") == "Python"

    def test_javascript(self):
        assert detect_language("app/index.js") == "JavaScript"

    def test_typescript(self):
        assert detect_language("src/utils.ts") == "TypeScript"

    def test_react_jsx(self):
        assert detect_language("components/App.jsx") == "React JSX"

    def test_react_tsx(self):
        assert detect_language("components/App.tsx") == "React TSX"

    def test_java(self):
        assert detect_language("com/example/Main.java") == "Java"

    def test_dockerfile(self):
        assert detect_language("Dockerfile") == "Dockerfile"

    def test_makefile(self):
        assert detect_language("Makefile") == "Makefile"

    def test_unknown_extension(self):
        assert detect_language("config.xyz") == "XYZ"

    def test_no_extension(self):
        assert detect_language("README") == "Unknown"

    def test_nested_path(self):
        assert detect_language("src/kr_code_reviewer/cli.py") == "Python"


# ============================================================
# _parse_hunk_header 테스트
# ============================================================

class TestParseHunkHeader:

    def test_standard_header(self):
        result = _parse_hunk_header("@@ -10,5 +10,8 @@ def some_function():")
        assert result == (10, 5, 10, 8)

    def test_single_line(self):
        result = _parse_hunk_header("@@ -1 +1 @@")
        assert result == (1, 1, 1, 1)

    def test_zero_lines(self):
        result = _parse_hunk_header("@@ -0,0 +1,5 @@")
        assert result == (0, 0, 1, 5)

    def test_invalid_header(self):
        result = _parse_hunk_header("not a header")
        assert result == (0, 0, 0, 0)


# ============================================================
# _detect_file_status 테스트
# ============================================================

class TestDetectFileStatus:

    def test_added(self):
        assert _detect_file_status("/dev/null", "new_file.py") == "added"

    def test_deleted(self):
        assert _detect_file_status("old_file.py", "/dev/null") == "deleted"

    def test_modified(self):
        assert _detect_file_status("file.py", "file.py") == "modified"

    def test_renamed(self):
        assert _detect_file_status("old_name.py", "new_name.py") == "renamed"


# ============================================================
# parse_diff_text 테스트
# ============================================================

SAMPLE_DIFF = """\
diff --git a/hello.py b/hello.py
--- a/hello.py
+++ b/hello.py
@@ -1,3 +1,5 @@
 def hello():
-    print("hello")
+    print("hello world")
+
+hello()
"""

SAMPLE_NEW_FILE_DIFF = """\
diff --git a/new_file.py b/new_file.py
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,3 @@
+def greet():
+    return "hi"
+
"""

SAMPLE_DELETE_FILE_DIFF = """\
diff --git a/old_file.py b/old_file.py
--- a/old_file.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def unused():
-    pass
"""

SAMPLE_MULTI_FILE_DIFF = """\
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 from flask import Flask
+from flask import jsonify
 app = Flask(__name__)
diff --git a/utils.py b/utils.py
--- a/utils.py
+++ b/utils.py
@@ -5,3 +5,6 @@
 def helper():
     return True
+
+def new_helper():
+    return False
"""


class TestParseDiffText:

    def test_empty_diff(self):
        result = parse_diff_text("")
        assert result.file_count == 0
        assert result.total_additions == 0
        assert result.total_deletions == 0

    def test_whitespace_only(self):
        result = parse_diff_text("   \n\n  ")
        assert result.file_count == 0

    def test_single_file_modified(self):
        result = parse_diff_text(SAMPLE_DIFF)
        assert result.file_count == 1

        file_diff = result.files[0]
        assert file_diff.new_path == "hello.py"
        assert file_diff.status == "modified"
        assert file_diff.language == "Python"
        assert len(file_diff.hunks) == 1
        assert len(file_diff.added_lines) == 3
        assert len(file_diff.removed_lines) == 1

    def test_new_file(self):
        result = parse_diff_text(SAMPLE_NEW_FILE_DIFF)
        assert result.file_count == 1

        file_diff = result.files[0]
        assert file_diff.status == "added"
        assert len(file_diff.added_lines) == 3
        assert len(file_diff.removed_lines) == 0

    def test_deleted_file(self):
        result = parse_diff_text(SAMPLE_DELETE_FILE_DIFF)
        assert result.file_count == 1

        file_diff = result.files[0]
        assert file_diff.status == "deleted"
        assert len(file_diff.added_lines) == 0
        assert len(file_diff.removed_lines) == 2

    def test_multi_file(self):
        result = parse_diff_text(SAMPLE_MULTI_FILE_DIFF)
        assert result.file_count == 2
        assert result.files[0].new_path == "app.py"
        assert result.files[1].new_path == "utils.py"

    def test_summary(self):
        result = parse_diff_text(SAMPLE_DIFF)
        summary = result.summary()
        assert "1개 파일 변경" in summary
        assert "+3 추가" in summary
        assert "-1 삭제" in summary

    def test_total_counts(self):
        result = parse_diff_text(SAMPLE_MULTI_FILE_DIFF)
        assert result.total_additions == 4
        assert result.total_deletions == 0


# ============================================================
# ParsedDiff 프로퍼티 테스트
# ============================================================

class TestParsedDiff:

    def test_empty_parsed_diff(self):
        pd = ParsedDiff()
        assert pd.file_count == 0
        assert pd.total_additions == 0
        assert pd.total_deletions == 0
        assert "0개 파일 변경" in pd.summary()