import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    key: str


def load_settings(dotenv_path: Optional[Path] = None) -> SupabaseSettings:
    """Load Supabase credentials without exposing them in application code."""
    load_dotenv(dotenv_path)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY are required")
    url = url.rstrip("/")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    return SupabaseSettings(url=url, key=key)


def create_supabase_client(settings: Optional[SupabaseSettings] = None):
    """Create the Supabase client only when a real connection is requested."""
    from supabase import create_client

    settings = settings or load_settings()
    return create_client(settings.url, settings.key)
