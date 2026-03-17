"""CLI 인터페이스 모듈"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from .config import Config
from .diff_parser import (
    get_branch_diff,
    get_commit_diff,
    get_staged_diff,
    get_working_diff,
    parse_diff_text,
)
from .formatter import (
    format_review_compact,
    format_review_github_comment,
    format_review_markdown,
)
from .reviewer import CodeReviewer


@click.group()
@click.version_option(package_name="kr-code-reviewer")
def main():
    """🧩 KR Code Reviewer - 한국어 코드 리뷰 자동 생성기"""
    pass


@main.command()
@click.option(
    "--source",
    type=click.Choice(["staged", "working", "branch", "commit"]),
    default="staged",
    help="diff 소스 선택 (기본: staged)",
)
@click.option("--base", default="main", help="브랜치 비교 시 base 브랜치 (기본: main)")
@click.option("--commit", "commit_hash", default=None, help="특정 커밋 해시")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "compact", "github"]),
    default="compact",
    help="출력 형식 (기본: compact)",
)
@click.option("--output", "-o", default=None, help="결과를 파일로 저장 (경로 지정)")
@click.option("--env", "env_path", default=None, help=".env 파일 경로")
def review(source, base, commit_hash, output_format, output, env_path):
    """로컬 git diff를 리뷰합니다."""
    # 설정 로드
    config = Config.from_env(env_path)
    errors = config.validate()
    if errors:
        for err in errors:
            click.echo(f"❌ {err}", err=True)
        click.echo("\n💡 .env 파일에 API 키를 설정하거나 환경변수로 지정해주세요.", err=True)
        click.echo("   참고: .env.example", err=True)
        sys.exit(1)
    
    # diff 가져오기
    if source == "staged":
        diff_text = get_staged_diff()
        if not diff_text.strip():
            click.echo("💡 staged 변경사항이 없습니다. working 변경사항을 확인합니다...")
            diff_text = get_working_diff()
    elif source == "working":
        diff_text = get_working_diff()
    elif source == "branch":
        diff_text = get_branch_diff(base)
    elif source == "commit":
        hash_val = commit_hash or "HEAD"
        diff_text = get_commit_diff(hash_val)

    if not diff_text.strip():
        click.echo("ℹ️  변경사항이 없습니다.")
        sys.exit(0)

    # diff 파싱
    parsed_diff = parse_diff_text(diff_text)
    click.echo(f"📊 {parsed_diff.summary()}")
    click.echo("")

    # 리뷰 실행
    click.echo("🤖 리뷰를 생성하는 중...")
    reviewer = CodeReviewer(config)

    try:
        result = reviewer.review_diff(parsed_diff)
    except Exception as e:
        click.echo(f"❌ 리뷰 생성 실패: {e}", err=True)
        sys.exit(1)

    # 결과 포매팅
    if output_format == "markdown":
        formatted = format_review_markdown(result)
    elif output_format == "github":
        formatted = format_review_github_comment(result)
    else:
        formatted = format_review_compact(result)

    # 출력
    if output:
        output_path = Path(output)
        output_path.write_text(formatted, encoding="utf-8")
        click.echo(f"✅ 리뷰 결과를 저장했습니다: {output_path}")
    else:
        click.echo("")
        click.echo(formatted)


@main.command()
@click.argument("diff_file", type=click.Path(exists=True))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "compact", "github"]),
    default="compact",
    help="출력 형식 (기본: compact)",
)
@click.option("--output", "-o", default=None, help="결과를 파일로 저장 (경로 지정)")
@click.option("--env", "env_path", default=None, help=".env 파일 경로")
def review_file(diff_file, output_format, output, env_path):
    """diff 파일을 읽어 리뷰합니다.

    DIFF_FILE: .diff 또는 .patch 파일 경로
    """
    # 설정 로드
    config = Config.from_env(env_path)
    errors = config.validate()
    if errors:
        for err in errors:
            click.echo(f"❌ {err}", err=True)
        sys.exit(1)

    # diff 파일 읽기
    diff_path = Path(diff_file)
    diff_text = diff_path.read_text(encoding="utf-8")

    if not diff_text.strip():
        click.echo("ℹ️  diff 파일이 비어 있습니다.")
        sys.exit(0)

    # 파싱 + 리뷰
    parsed_diff = parse_diff_text(diff_text)
    click.echo(f"📊 {parsed_diff.summary()}")
    click.echo("")
    click.echo("🤖 리뷰를 생성하는 중...")

    reviewer = CodeReviewer(config)

    try:
        result = reviewer.review_diff(parsed_diff)
    except Exception as e:
        click.echo(f"❌ 리뷰 생성 실패: {e}", err=True)
        sys.exit(1)

    # 결과 포매팅
    if output_format == "markdown":
        formatted = format_review_markdown(result)
    elif output_format == "github":
        formatted = format_review_github_comment(result)
    else:
        formatted = format_review_compact(result)

    # 출력
    if output:
        output_path = Path(output)
        output_path.write_text(formatted, encoding="utf-8")
        click.echo(f"✅ 리뷰 결과를 저장했습니다: {output_path}")
    else:
        click.echo("")
        click.echo(formatted)


@main.command()
def check():
    """설정 상태를 확인합니다."""
    config = Config.from_env()

    click.echo("🔧 KR Code Reviewer 설정 확인")
    click.echo("")

    # Anthropic API 키
    if config.anthropic_api_key:
        masked = config.anthropic_api_key[:10] + "..." + config.anthropic_api_key[-4:]
        click.echo(f"  ✅ ANTHROPIC_API_KEY: {masked}")
    else:
        click.echo("  ❌ ANTHROPIC_API_KEY: 미설정")

    # GitHub 토큰
    if config.github_token:
        masked = config.github_token[:6] + "..." + config.github_token[-4:]
        click.echo(f"  ✅ GITHUB_TOKEN: {masked}")
    else:
        click.echo("  ⚠️  GITHUB_TOKEN: 미설정 (PR 리뷰 시 필요)")

    # 기타 설정
    click.echo(f"  📝 리뷰 언어: {config.language}")
    click.echo(f"  🤖 모델: {config.model}")
    click.echo(f"  📏 최대 diff 라인: {config.max_diff_lines}")
    click.echo(f"  📦 최대 토큰: {config.max_tokens}")


@main.command()
@click.argument("pr_url")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "compact", "github"]),
    default="compact",
    help="출력 형식 (기본: compact)",
)
@click.option("--output", "-o", default=None, help="결과를 파일로 저장 (경로 지정)")
@click.option("--post", is_flag=True, default=False, help="리뷰 결과를 PR 코멘트로 자동 작성")
@click.option("--env", "env_path", default=None, help=".env 파일 경로")
def pr(pr_url, output_format, output, post, env_path):
    """GitHub PR을 리뷰합니다.
    
    PR_URL: PR URL 또는 'owner/repo#번호' 형식
    
    예시:
        kr-review pr https://github.com/Dev-2A/kr-code-reviewer/pull/1
        kr-review pr Dev-2A/kr-code-reviewer#1
        kr-review pr Dev-2A/kr-code-reviewer#1 --post
    """
    from .github_client import GitHubClient, parse_pr_url
    
    # 설정 로드
    config = Config.from_env(env_path)
    errors = config.validate(require_github=True)
    if errors:
        for err in errors:
            click.echo(f"❌ {err}", err=True)
        click.echo("\n💡 .env 파일에 API 키를 설정해주세요.", err=True)
        sys.exit(1)
    
    # PR URL 파싱
    try:
        repo_name, pr_number = parse_pr_url(pr_url)
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)
    
    click.echo(f"🔗 PR 정보를 가져오는 중... ({repo_name}#{pr_number})")
    
    # GitHub 클라이언트
    client = GitHubClient(config)
    
    try:
        pr_info = client.get_pr_info(repo_name, pr_number)
    except Exception as e:
        click.echo(f"❌ PR 정보를 가져올 수 없습니다: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"📌 #{pr_info.number} {pr_info.title}")
    click.echo(f"   👤 {pr_info.author} | {pr_info.base_branch} ← {pr_info.head_branch}")
    click.echo(f"   📊 +{pr_info.additions} -{pr_info.deletions} ({pr_info.changed_files}개 파일)")
    click.echo("")
    
    # 리뷰 실행
    click.echo("🤖 리뷰를 생성하는 중...")
    
    try:
        result, _ = client.review_pr(repo_name, pr_number)
    except Exception as e:
        click.echo(f"❌ 리뷰 생성 실패: {e}", err=True)
        sys.exit(1)
    
    # 결과 포매팅
    if output_format == "markdown":
        formatted = format_review_markdown(result)
    elif output_format == "github":
        formatted = format_review_github_comment(result)
    else:
        formatted = format_review_compact(result)
    
    # 출력
    if output:
        output_path = Path(output)
        output_path.write_text(formatted, encoding="utf-8")
        click.echo(f"✅ 리뷰 결과를 저장했습니다: {output_path}")
    else:
        click.echo("")
        click.echo(formatted)
    
    # PR에 코멘트 작성
    if post:
        click.echo("")
        click.echo("📝 PR에 코멘트를 작성하는 중...")
        try:
            comment_body = format_review_github_comment(result)
            comment_url = client.post_review_comment(repo_name, pr_number, comment_body)
            click.echo(f"✅ 코멘트가 작성되었습니다: {comment_url}")
        except Exception as e:
            click.echo(f"❌ 코멘트 작성 실패: {e}", err=True)
            sys.exit(1)


if __name__ == "__main__":
    main()