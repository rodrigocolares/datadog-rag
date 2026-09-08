from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    datadog_docs_base_url: str = "https://docs.datadoghq.com"
    datadog_docs_prefixes: str = "/getting_started/,/agent/,/integrations/,/logs/,/tracing/,/monitors/,/dashboards/,/api/"
    max_pages: int = 250
    request_delay_seconds: float = 0.15
    top_k: int = 6
    min_similarity: float = 0.20
    database_path: Path = ROOT / "data" / "datadog_rag.db"

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    @property
    def allowed_prefixes(self) -> tuple[str, ...]:
        return tuple(p.strip() for p in self.datadog_docs_prefixes.split(",") if p.strip())


settings = Settings()

