from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    jarvis_host: str = "127.0.0.1"
    jarvis_port: int = 8000
    jarvis_data_dir: str = "./data"

    @property
    def data_path(self) -> Path:
        root = Path(__file__).resolve().parent.parent
        p = Path(self.jarvis_data_dir)
        return p if p.is_absolute() else root / p

    @property
    def files_path(self) -> Path:
        return self.data_path / "files"

    @property
    def db_path(self) -> Path:
        return self.data_path / "jarvis.db"


settings = Settings()
