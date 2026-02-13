from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    anthropic_api_url: Optional[str] = None
    
    servicenow_instance: Optional[str] = None
    servicenow_username: Optional[str] = None
    servicenow_password: Optional[str] = None
    servicenow_jdbc_path: str = "./jdbc/ServiceNowJdbc-1.0.3-SNAPSHOT.jar"
    
    upload_dir: str = "./uploads"
    diagram_output_dir: str = "./diagrams"
    vector_db_path: str = "./vectordb"
    
    serpapi_key: Optional[str] = None
    
    max_file_size: int = 50 * 1024 * 1024
    allowed_extensions: list = [".pdf", ".docx", ".xlsx", ".txt", ".csv"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.diagram_output_dir, exist_ok=True)
os.makedirs(settings.vector_db_path, exist_ok=True)
os.makedirs("./jdbc", exist_ok=True)
