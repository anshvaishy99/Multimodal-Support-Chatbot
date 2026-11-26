import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    gemini_tts_model: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    max_upload_bytes: int
    api_base_url: str

    def __post_init__(self):
        if self.max_upload_bytes <= 0:
            raise ValueError("MAX_UPLOAD_BYTES must be greater than zero.")

    @classmethod
    def from_env(cls):
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            gemini_tts_model=os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
            mysql_host=os.getenv("MYSQL_HOST", "127.0.0.1"),
            mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
            mysql_user=os.getenv("MYSQL_USER", "root"),
            mysql_password=os.getenv("MYSQL_PASSWORD", ""),
            mysql_database=os.getenv("MYSQL_DATABASE", "support_chatbot"),
            max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
            api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
        )


settings = Settings.from_env()
