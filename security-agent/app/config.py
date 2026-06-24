from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Security Agent"
    data_dir: Path = Path("/data")
    policy_file: Path = Path("/app/policies/default.yaml")
    llm_base_url: str = "http://llama:8080/v1"
    llm_api_key: str = "local"
    llm_model: str = "local-model"
    llm_timeout_seconds: float = 120
    llm_disable_thinking: bool = True
    llm_plan_disable_thinking: bool = True
    llm_report_disable_thinking: bool = True
    llm_plan_max_tokens: int = 350
    llm_report_max_tokens: int = 650
    max_tool_rounds: int = 3
    api_key: str = ""
    approval_key: str = ""
    lab_cidrs: str = "10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    bas_executor_url: str = "http://bas-executor:8010"
    bas_executor_secret: str = ""
    mcp_config_file: Path = Path("/app/connectors/mcp.yaml")
    skill_dir: Path = Path("/app/skills")
    knowledge_dirs: str = "/app/knowledge,/app/docs"
    rag_chunk_chars: int = 1_800
    rag_overlap_chars: int = 200
    rag_max_documents: int = 500
    rag_max_file_bytes: int = 25 * 1024 * 1024
    web_dir: Path = Path("/app/web")
    web_username: str = "admin"
    web_password_hash: str = ""
    web_session_secret: str = ""
    web_session_ttl_seconds: int = 28_800
    web_memory_turns: int = 8
    web_memory_chars_per_turn: int = 1_200
    web_secure_cookie: bool = True
    enable_api_docs: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
