"""
src/opensak/utils/run_cli.py — Entry point for the `opensak` CLI command.
"""


def main() -> None:
    from opensak.app import main as _main
    _main()
