from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys

_RESET = "\033[0m"
_DIM = "\033[2m"
_RED = "\033[31m"
_YELLOW = "\033[33m"


class Logger:
    def __init__(self) -> None:
        self.debug_enabled = False

    def set_debug(self, enabled: bool) -> None:
        self.debug_enabled = enabled

    def debug(self, msg: str) -> None:
        if not self.debug_enabled:
            return
        print(f"{_DIM}[{datetime.now().strftime('%H:%M:%S')} D] {msg}{_RESET}")

    def info(self, msg: str) -> None:
        print(f"[{datetime.now().strftime('%H:%M:%S')} I] {msg}")

    def warn(self, msg: str) -> None:
        print(
            f"{_YELLOW}[{datetime.now().strftime('%H:%M:%S')} W] {msg}{_RESET}",
            file=sys.stderr,
        )

    def error(self, msg: str) -> None:
        print(
            f"{_RED}[{datetime.now().strftime('%H:%M:%S')} E] {msg}{_RESET}",
            file=sys.stderr,
        )


log = Logger()


class BracketlapseError(RuntimeError):
    pass


def resolve_processing_directory(value: Path | None) -> Path:
    if value is None:
        raw = input("Processing directory: ").strip().strip('"')
        if not raw:
            raise BracketlapseError("No processing directory was provided.")
        value = Path(raw)

    directory = value.expanduser().resolve()
    if not directory.exists():
        raise BracketlapseError(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise BracketlapseError(f"Not a directory: {directory}")
    return directory


def resolve_inside(base: Path, path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


def require_tool(name: str) -> str:
    executable = shutil.which(name)
    if executable is None and os.name == "nt":
        executable = shutil.which(f"{name}.exe")
    if executable is None:
        raise BracketlapseError(
            f"{name} was not found in PATH. Install it or add its bin directory to PATH."
        )
    return executable


def run_command(command: list[str]) -> None:
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise BracketlapseError(f"Executable not found: {command[0]}") from exc

    if result.returncode != 0:
        _emit_external_output(result.stdout, error=True)
        _emit_external_output(result.stderr, error=True)
        raise BracketlapseError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}"
        )

    _emit_external_output(result.stdout)
    _emit_external_output(result.stderr)


def _emit_external_output(text: str, *, error: bool = False) -> None:
    if not text:
        return
    level = log.error if error else log.debug
    for line in text.strip().split("\n"):
        stripped = line.strip()
        if stripped:
            level(stripped)


def format_fps(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def format_paths(paths: list[Path]) -> str:
    return ", ".join(str(path) for path in paths)


def parse_float(raw: str, label: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise BracketlapseError(f"Invalid {label} value: {raw!r}") from exc
