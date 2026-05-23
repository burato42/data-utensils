import json
import sys
from datetime import date


class _DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def write_output(results: dict, output_path: str) -> None:
    """Serialize results to indented JSON and write to output_path."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, cls=_DateEncoder)
            f.write("\n")
    except OSError as e:
        print(f"ERROR: Could not write output to {output_path}: {e}", file=sys.stderr)
        sys.exit(1)
