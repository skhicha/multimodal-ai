from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SV_", env_file=".env", extra="ignore")

    # Core / network
    env: str = "development"
    public_origin: str = "http://localhost:5173"
    cors_origins: str = "http://localhost:5173"
    database_url: str = "sqlite+aiosqlite:///./sonavault.db"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    queue_backend: str = "in-process"  # redis | in-process

    # Auth / crypto
    jwt_ed25519_private_key_path: str = ""
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7
    argon2_memory_kib: int = 65536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 2
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "SonaVault"
    master_kek_b64: str = ""
    blind_index_key_b64: str = ""
    internal_service_token: str = ""
    mediamtx_webhook_secret: str = ""
    enforce_mfa_tier_min: int = 3
    enforce_mfa_all: bool = False

    # AI sidecars / feature flags
    speech_sidecar_url: str = "http://localhost:8001"
    nlp_sidecar_url: str = "http://localhost:8002"
    vllm_base_url: str = "http://localhost:8000"
    vllm_model_id: str = "nvidia/Qwen3-30B-A3B-NVFP4"
    mt_model_id: str = "google/madlad400-3b-mt"
    feature_vllm_enabled: bool = False

    # Storage paths
    blob_root: str = "./data/blobs"
    model_root: str = "./data/models"
    cache_root: str = "./data/cache"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def blob_path(self) -> Path:
        return Path(self.blob_root)

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_root)


@lru_cache
def get_settings() -> Settings:
    return Settings()
