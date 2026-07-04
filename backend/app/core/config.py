from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "local"
    database_url: str = "postgresql+psycopg://homies:homies@localhost:5432/homies"
    redis_url: str = "redis://localhost:6379/0"
    meili_url: str = "http://localhost:7700"
    meili_master_key: str = "dev-master-key"
    nats_url: str = "nats://localhost:4222"


settings = Settings()
