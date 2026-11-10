import sys
from collections.abc import Sequence

from cleanyourphone_app.version import __version__


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        print(f"CleanYourPhone app {__version__}")
        return 0

    from cleanyourphone_app.ui.app import run

    result = run(args)
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
