"""Configuration without opening connections or downloading models at import time."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    # Hide connection details in logs/reprs, including optional credentials in URI.
    mongodb_uri: str = field(repr=False)
    mongodb_username: str | None = field(default=None, repr=False)
    mongodb_password: str | None = field(default=None, repr=False)
    database: str = "sakti_sahayak"
    corpus_dir: Path = Path("data/raw")
    reports_dir: Path = Path("data/reports")
    processed_dir: Path = Path("data/processed")
    catalog_path: Path = Path("data/catalog.json")
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_dimensions: int = 384
    embedding_device: str = "cpu"

    @classmethod
    def from_env(cls) -> "Settings":
        # Resolve from this package, not whichever directory a command starts in.
        backend_dir = Path(__file__).resolve().parents[2]
        load_dotenv(backend_dir / ".env", override=False)
        project_dir = backend_dir.parent
        os.environ.setdefault("HF_HOME", str(project_dir / ".cache/huggingface"))
        uri = os.getenv("MONGODB_URI")
        return cls(
            mongodb_uri=uri or (
                f"mongodb://{os.getenv('MONGODB_HOST', 'localhost')}:"
                f"{os.getenv('MONGODB_PORT', '27017')}/?directConnection=true"
            ),
            mongodb_username=None if uri else os.getenv("MONGODB_USERNAME"),
            mongodb_password=None if uri else os.getenv("MONGODB_PASSWORD"),
            database=os.getenv("MONGODB_DB", "sakti_sahayak"),
            corpus_dir=Path(os.getenv("CORPUS_DIR", str(project_dir / "data/raw"))),
            reports_dir=Path(os.getenv("REPORTS_DIR", str(project_dir / "data/reports"))),
            processed_dir=Path(os.getenv("PROCESSED_DIR", str(project_dir / "data/processed"))),
            catalog_path=Path(os.getenv("CORPUS_CATALOG", str(project_dir / "data/catalog.json"))),
            embedding_device=os.getenv("EMBEDDING_DEVICE", "cpu"),
        )

