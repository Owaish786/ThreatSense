from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_version: str = os.getenv('MODEL_VERSION', 'v0-local-joblib')


settings = Settings()
