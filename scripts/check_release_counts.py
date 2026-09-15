"""Reject unexpected loss/addition of real equipment/material rows during release."""
import json
import sys
from pathlib import Path


def main() -> int:
    before = json.loads(Path(sys.argv[1]).read_text())
    after = json.loads(Path(sys.argv[2]).read_text())
    identity = ("environment", "host", "port", "database", "expected_revision")
    if any(before[key] != after[key] for key in identity):
        print("ERROR: release target changed between snapshots", file=sys.stderr)
        return 1
    for table in ("eqp.equipment", "mm.material"):
        if before["counts"].get(table) is None or before["counts"][table] != after["counts"].get(table):
            print(f"ERROR: unexpected row-count change: {table}; inspect release reports", file=sys.stderr)
            return 1
    print("设备和物料记录数前后一致；数据转换仍须专项抽检。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
