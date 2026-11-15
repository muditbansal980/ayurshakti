"""Compatibility entry point: install this package, then run `python db.py`."""

from ip_sakti.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["status"]))

