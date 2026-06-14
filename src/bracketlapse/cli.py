from __future__ import annotations

import sys

from .arguments import build_parser
from .common import BracketlapseError, log
from .fusion import fuse_brackets
from .standby import extract_standby_config, run_standby
from .video import build_video


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        standby_config, normalized_argv = extract_standby_config(argv)
        parser = build_parser(normalized_argv)
        args = parser.parse_args(
            normalized_argv[1:] if normalized_argv[:1] == ["video"] else normalized_argv
        )

        if standby_config is not None:
            if argv[:1] == ["video"]:
                raise BracketlapseError("Standby mode cannot be combined with the video command.")
            run_standby(args, standby_config)
        elif argv[:1] == ["video"]:
            build_video(args)
        else:
            fuse_brackets(args)
    except BracketlapseError as exc:
        log.error(str(exc))
        return 1
    except KeyboardInterrupt:
        log.error("Interrupted.")
        return 130

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
