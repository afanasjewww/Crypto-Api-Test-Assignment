from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str
    mongo_uri: str
    api_version: str
    environment: str
    mongodb_url: str = "mongodb://mongo:27017"
    app_port: int = 8000
    moralis_api_key: str

    class Config:
        env_file = ".env"

settings = Settings()
