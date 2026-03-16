"""GitHub API 연동 모듈"""

from __future__ import annotations

from dataclasses import dataclass

from github import Github, GithubException

from .config import Config
from .diff_parser import parse_diff_text, ParsedDiff
from .formatter import format_review_github_comment
from .reviewer import CodeReviewer, ReviewResult


@dataclass
class PRInfo:
    """PR 기본 정보"""
    
    number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    url: str
    additions: int
    deletions: int
    changed_files: int


class GitHubClient:
    """GitHub PR 리뷰 클라이언트"""
    
    def __init__(self, config: Config):
        self.config = config
        self.github = Github(config.github_token)
    
    def get_pr_info(self, repo_name: str, pr_number: int) -> PRInfo:
        """PR 기본 정보를 가져옵니다.
        
        Args:
            repo_name: 'owner/repo' 형식의 레포지토리 이름
            pr_number: PR 번호
        """
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        return PRInfo(
            number=pr.number,
            title=pr.title,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            url=pr.html_url,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files=pr.changed_files,
        )
    
    def get_pr_diff(self, repo_name: str, pr_number: int) -> str:
        """PR의 diff 텍스트를 가져옵니다."""
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        # PyGithub에서 diff를 가져오려면 Accept 헤더를 변경해야 함
        # 직접 requester를 사용
        headers, data = pr._requester.requestJsonAndCheck(
            "GET",
            pr.url,
            headers={"Accept": "application/vnd.github.v3.diff"},
        )
        return data if isinstance(data, str) else ""
    
    def get_pr_diff_via_files(self, repo_name: str, pr_number: int) -> ParsedDiff:
        """PR의 파일별 diff를 가져와 ParsedDiff로 변환합니다.
        
        get_pr_diff()가 실패할 경우 대안으로 사용합니다.
        """
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        
        diff_parts: list[str] = []
        for file in pr.get_files():
            if file.patch:
                diff_parts.append(
                    f"diff --git a/{file.filename} b/{file.filename}\n"
                    f"--- a/{file.filename}\n"
                    f"+++ b/{file.filename}\n"
                    f"{file.patch}"
                )
        
        full_diff = "\n".join(diff_parts)
        return parse_diff_text(full_diff)
    
    def post_review_comment(
        self,
        repo_name: str,
        pr_number: int,
        comment_body: str,
    ) -> str:
        """PR에 리뷰 코멘트를 작성합니다.
        
        Returns:
            작성된 코멘트의 URL
        """
        repo = self.github.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        comment = pr.create_issue_comment(comment_body)
        return comment.html_url
    
    def review_pr(self, repo_name: str, pr_number: int) -> tuple[ReviewResult, PRInfo]:
        """PR을 리뷰합니다.
        
        Returns:
            (ReviewResult, PRInfo) 튜플
        """
        # PR 정보 가져오기
        pr_info = self.get_pr_info(repo_name, pr_number)
        
        # diff 가져오기 (파일별 방식 사용)
        parsed_diff = self.get_pr_diff_via_files(repo_name, pr_number)
        
        if not parsed_diff.files:
            return (
                ReviewResult(summary="리뷰할 변경사항이 없습니다."),
                pr_info,
            )
        
        # 리뷰 실행
        reviewer = CodeReviewer(self.config)
        result = reviewer.review_diff(parsed_diff)
        
        return result, pr_info
    
    def review_and_comment(self, repo_name: str, pr_number: int) -> str:
        """PR을 리뷰하고 결과를 코멘트로 작성합니다.
        
        Returns:
            작성된 코멘트의 URL
        """
        result, pr_info = self.review_pr(repo_name, pr_number)
        
        # GitHub 코멘트용으로 포매팅
        comment_body = format_review_github_comment(result)
        
        # 코멘트 작성
        comment_url = self.post_reivew_comment(repo_name, pr_number, comment_body)
        
        return comment_url


def parse_pr_url(url: str) -> tuple[str, int]:
    """GitHub PR URL에서 repo_name과 pr_number를 추출합니다.
    
    Args:
        url: 'https://github.com/owner/repo/pull/123' 또는 'owner/repo#123' 형식
    
    Returns:
        (repo_name, pr_number) 튜플
    
    Raises:
        ValueError: URL 형식이 올바르지 않은 경우
    """
    # https://github.com/owner/repo/pull/123 형식
    if "github.com" in url and "/pull/" in url:
        parts = url.rstrip("/").split("/")
        try:
            pull_idx = parts.index("pull")
            owner = parts[pull_idx - 2]
            repo = parts[pull_idx - 1]
            pr_number = int(parts[pull_idx + 1])
            return f"{owner}/{repo}", pr_number
        except (IndexError, ValueError):
            pass
    
    # owner/repo#123 형식
    if "#" in url and "/" in url:
        try:
            repo_part, number_part = url.split("#")
            pr_number = int(number_part)
            return repo_part.strip(), pr_number
        except ValueError:
            pass
    
    raise ValueError(
        f"PR URL 형식을 인식할 수 없습니다: {url}\n"
        f"지원 형식: https://github.com/owner/repo/pull/123 또는 owner/repo#123"
    )