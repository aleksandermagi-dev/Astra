from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from astra.outputs import default_outputs_root


@dataclass(slots=True)
class TendrilSettings:
    repo_root: Path
    data_root: Path
    persistence_db_path: Path

    @classmethod
    def from_repo_root(
        cls,
        repo_root: Path | None = None,
        *,
        data_root: Path | None = None,
    ) -> "TendrilSettings":
        resolved_repo = (repo_root or Path(__file__).resolve().parents[3]).resolve()
        resolved_data = (data_root or default_outputs_root() / "tendril").resolve()
        return cls(
            repo_root=resolved_repo,
            data_root=resolved_data,
            persistence_db_path=resolved_data / "astra_tendril.sqlite3",
        )
