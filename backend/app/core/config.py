"""애플리케이션 설정. 모든 값은 환경변수(.env)에서 읽으며 코드에 시크릿을 하드코딩하지 않는다.

기존 backend/.env 는 발제사 원본 키 이름(SECRET_KEY, EMBEDDING_MODEL_NAME, MONGODB_VECTOR_INDEX ...)을
그대로 쓰고 있어 값을 지우거나 이름을 바꾸지 않는다. 과제에서 요구하는 표준 키 이름
(JWT_SECRET_KEY, OPENAI_EMBEDDING_MODEL, ATLAS_VECTOR_INDEX_NAME ...)은 AliasChoices로 기존 키와
함께 인식하도록 하고, .env.example에는 신규 키만 추가한다.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- App ---
    app_name: str = Field(default="hug-anshim-backend", validation_alias="APP_NAME")
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    debug: bool = Field(default=True, validation_alias=AliasChoices("APP_DEBUG", "DEBUG"))
    api_v1_prefix: str = Field(default="/api/v1", validation_alias="API_V1_PREFIX")
    mock_mode: bool = Field(default=True, validation_alias="MOCK_MODE")

    # --- Mongo ---
    mongodb_uri: str = Field(default="", validation_alias="MONGODB_URI")
    mongodb_db_name: str = Field(default="dive2026", validation_alias="MONGODB_DB_NAME")

    # --- JWT ---
    jwt_secret_key: str = Field(
        default="change-me-before-deploy",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # --- OpenAI / RAG ---
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    openai_embedding_model: str = Field(
        default="text-embedding-3-large",
        validation_alias=AliasChoices("OPENAI_EMBEDDING_MODEL", "EMBEDDING_MODEL_NAME"),
    )
    openai_embedding_dimensions: int = Field(
        default=1024,
        validation_alias=AliasChoices("OPENAI_EMBEDDING_DIMENSIONS", "EMBEDDING_DIMENSIONS"),
    )
    atlas_vector_index_name: str = Field(
        default="rag_chunks_vector_index",
        validation_alias=AliasChoices("ATLAS_VECTOR_INDEX_NAME", "MONGODB_VECTOR_INDEX"),
    )
    atlas_vector_collection: str = Field(default="rag_chunks", validation_alias="ATLAS_VECTOR_COLLECTION")
    atlas_vector_path: str = Field(default="embedding", validation_alias="ATLAS_VECTOR_PATH")

    # --- Blockchain (mock 우선, Polygon 연동은 추후) ---
    blockchain_mode: str = Field(default="mock", validation_alias="BLOCKCHAIN_MODE")
    polygon_rpc_url: str = Field(default="", validation_alias="POLYGON_RPC_URL")
    polygon_private_key: str = Field(default="", validation_alias="POLYGON_PRIVATE_KEY")
    polygon_contract_address: str = Field(
        default="",
        validation_alias=AliasChoices("POLYGON_CONTRACT_ADDRESS", "CONTRACT_ADDRESS"),
    )
    polygon_chain_id: int = Field(default=80002, validation_alias="POLYGON_CHAIN_ID")

    # --- CODEF 등기부 (샌드박스 검증 완료 2026-07-20) ---
    codef_env: str = Field(default="sandbox", validation_alias="CODEF_ENV")
    codef_sandbox_client_id: str = Field(default="", validation_alias="CODEF_SANDBOX_CLIENT_ID")
    codef_sandbox_client_secret: str = Field(default="", validation_alias="CODEF_SANDBOX_CLIENT_SECRET")
    codef_demo_client_id: str = Field(default="", validation_alias="CODEF_DEMO_CLIENT_ID")
    codef_demo_client_secret: str = Field(default="", validation_alias="CODEF_DEMO_CLIENT_SECRET")
    codef_oauth_url: str = Field(default="https://oauth.codef.io/oauth/token", validation_alias="CODEF_OAUTH_URL")
    codef_sandbox_base_url: str = Field(default="https://sandbox.codef.io", validation_alias="CODEF_SANDBOX_BASE_URL")
    codef_demo_base_url: str = Field(default="https://development.codef.io", validation_alias="CODEF_DEMO_BASE_URL")
    codef_public_key_path: str = Field(default="secrets/codef_public_key.pem", validation_alias="CODEF_PUBLIC_KEY_PATH")
    # 샌드박스 열람용 더미 비밀번호(실계정 아님). 운영 전환 시 사용자 입력으로 대체.
    codef_register_password: str = Field(default="dive2026!", validation_alias="CODEF_REGISTER_PASSWORD")

    # --- VWorld NED 공시가격 3종 (개발키, domain=등록 서비스 URL 필수) ---
    official_price_apt_api_key: str = Field(default="", validation_alias="OFFICIAL_PRICE_APT_API_KEY")
    official_price_house_api_key: str = Field(default="", validation_alias="OFFICIAL_PRICE_HOUSE_API_KEY")
    official_price_land_api_key: str = Field(default="", validation_alias="OFFICIAL_PRICE_LAND_API_KEY")
    official_price_domain: str = Field(
        default="", validation_alias="OFFICIAL_PRICE_REGISTERED_SERVICE_URL"
    )

    # --- 수집 데이터/ML 아티팩트 경로 ---
    # 기본값은 저장소 루트의 "개별수집데이터 및 API". 배포 환경에서는 DATA_DIR로 재지정한다.
    data_dir: str = Field(
        default=str(BACKEND_DIR.parent / "개별수집데이터 및 API"),
        validation_alias="DATA_DIR",
    )

    # --- CORS ---
    cors_allow_origins: str = Field(default="*", validation_alias="CORS_ALLOW_ORIGINS")

    @property
    def cors_origins_list(self) -> list[str]:
        if self.cors_allow_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
