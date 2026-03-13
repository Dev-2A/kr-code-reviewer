"""설정 관리 모듈"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    """애플리케이션 설정"""
    
    # API 키
    anthropic_api_key: str = ""
    github_token: str = ""
    
    # 리뷰 설정
    language: str = "ko"
    model: str = "claude-sonnet-4-20250514"
    max_diff_lines: int = 500
    max_tokens: int = 4096
    
    @classmethod
    def from_env(cls, env_path: str | None = None) -> "Config":
        """환경변수에서 설정을 로드합니다."""
        if env_path:
            load_dotenv(env_path)
        else:
            load_dotenv()
        
        return cls(
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            language=os.getenv("REVIEW_LANGUAGE", "ko"),
            model=os.getenv("REVIEW_MODEL", "claude-sonnet-4-20250514"),
            max_diff_lines=int(os.getenv("MAX_DIFF_LINES", "500")),
            max_tokens=int(os.getenv("MAX_TOKENS", "4096")),
        )
    
    def validate(self, require_github: bool = False) -> list[str]:
        """설정 유효성을 검증합니다. 오류 메시지 리스트를 반환합니다."""
        errors = []
        
        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        
        if require_github and not self.github_token:
            errors.append("GITHUB_TOKEN이 설정되지 않았습니다.")
        
        return errors