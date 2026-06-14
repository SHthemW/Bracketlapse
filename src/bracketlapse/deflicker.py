from __future__ import annotations

from pathlib import Path
import shutil

from .common import BracketlapseError, log, require_tool, run_command
from .images import find_images

DEFAULT_DEFLICK_OUTPUT = Path("hdr_deflick")
DEFLICK_PATTERN = "*.jp*g"


def ensure_deflick_supported_extension(ext: str) -> None:
    if ext.lower() not in {"jpg", "jpeg"}:
        raise BracketlapseError(
            "Automatic deflicker uses simple-deflicker, which only supports JPG/PNG. "
            "Use --ext jpg when automatic video creation is enabled."
        )


def deflick_frames(
    source_dir: Path,
    output_dir: Path,
    executable_name: str,
    overwrite: bool,
    rolling_average: int,
    jpeg_compression: int,
    threads: int | None,
) -> None:
    if source_dir.resolve() == output_dir.resolve():
        raise BracketlapseError("Deflicker output directory must differ from the source directory.")
    if rolling_average < 0:
        raise BracketlapseError("--deflick-rolling-average must be at least 0")
    if jpeg_compression < 1 or jpeg_compression > 100:
        raise BracketlapseError("--deflick-jpeg-compression must be between 1 and 100")
    if threads is not None and threads < 1:
        raise BracketlapseError("--deflick-threads must be at least 1")

    source_files = find_images(source_dir, DEFLICK_PATTERN, "name")
    if not source_files:
        raise BracketlapseError(f"No JPG files were found for deflicker in {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    existing_output = find_images(output_dir, DEFLICK_PATTERN, "name")
    if existing_output and not overwrite:
        source_names = {file.name for file in source_files}
        output_names = {file.name for file in existing_output}
        if output_names != source_names:
            raise BracketlapseError(
                f"Deflicker output already contains {len(existing_output)} frame(s), "
                f"but the source sequence has {len(source_files)} different frame(s). "
                "Use --overwrite."
            )
        log.info(f"Skip existing deflickered frames: {output_dir}")
        return
    if existing_output and overwrite:
        for file in existing_output:
            file.unlink()

    executable = resolve_deflick_executable(executable_name)
    log.info(f"Deflicker input directory: {source_dir}")
    log.info(f"Deflicker output directory: {output_dir}")
    command = [
        executable,
        "-source",
        str(source_dir),
        "-destination",
        str(output_dir),
        "-rollingAverage",
        str(rolling_average),
        "-jpegCompression",
        str(jpeg_compression),
    ]
    if threads is not None:
        command.extend(["-threads", str(threads)])
    run_command(command)

    output_files = find_images(output_dir, DEFLICK_PATTERN, "name")
    if len(output_files) < len(source_files):
        raise BracketlapseError(
            f"simple-deflicker produced {len(output_files)} frame(s), "
            f"expected at least {len(source_files)}."
        )


def resolve_deflick_executable(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.parent != Path(".") or candidate.is_absolute():
        if candidate.exists():
            return str(candidate.resolve())
        raise BracketlapseError(f"simple-deflicker executable does not exist: {candidate}")

    executable = shutil.which(value)
    if executable is not None:
        return executable
    return require_tool(value)
