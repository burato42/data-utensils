"""Write rejected records to per-run quarantine CSVs for post-hoc inspection."""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from loguru import logger


@dataclass
class RejectedRows:
    """Accumulates rejected rows from a single source file during a cleaning run."""
    source: str  # original filename, used as the output CSV stem
    frames: list[pd.DataFrame] = field(default_factory=list)

    def add(self, rows: pd.DataFrame, reason: str) -> None:
        """Append rows tagged with the rejection reason."""
        if rows.empty:
            return
        tagged = rows.copy()
        tagged["_rejection_reason"] = reason
        self.frames.append(tagged)

    @property
    def empty(self) -> bool:
        return not self.frames or all(f.empty for f in self.frames)


def write_quarantine(rejected: list[RejectedRows], run_dir: Path) -> None:
    """
    Write each RejectedRows to <run_dir>/<source_stem>_errors.csv.

    Creates run_dir if it does not exist. Logs a warning for each file written
    and an info message when nothing was rejected.
    """
    any_written = False
    for source_errors in rejected:
        if source_errors.empty:
            continue
        run_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(source_errors.source).stem
        out_path = run_dir / f"{stem}_errors.csv"
        combined = pd.concat(source_errors.frames, ignore_index=True)
        try:
            combined.to_csv(out_path, index=False)
        except OSError as e:
            print(f"ERROR: Could not write quarantine file {out_path}: {e}", file=sys.stderr)
            sys.exit(1)
        logger.warning(
            f"{len(combined)} rejected row(s) from '{source_errors.source}' "
            f"written to {out_path}"
        )
        any_written = True

    if not any_written:
        logger.info("No data quality issues found — quarantine directory not created")
