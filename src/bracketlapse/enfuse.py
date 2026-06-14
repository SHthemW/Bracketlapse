from __future__ import annotations

from pathlib import Path

from .common import BracketlapseError, run_command

DEFAULT_ENFUSE_ARGS = [
    "--exposure-width=0.05",
    "--exposure-optimum=0.30",
    "--saturation-weight=0",
    "--contrast-weight=0",
]


def build_enfuse_command(enfuse: str, output: Path, inputs: list[Path]) -> list[str]:
    return [enfuse, *DEFAULT_ENFUSE_ARGS, "-o", str(output), *map(str, inputs)]


def align_group(
    align_image_stack: str,
    group: list[Path],
    temp_dir: Path,
    frame_number: int,
) -> list[Path]:
    prefix = temp_dir / f"aligned_{frame_number:05d}_"
    run_command([align_image_stack, "-m", "-a", str(prefix), *map(str, group)])
    aligned = sorted(temp_dir.glob(f"aligned_{frame_number:05d}_*.tif"))
    if len(aligned) != len(group):
        raise BracketlapseError(
            f"align_image_stack produced {len(aligned)} file(s), expected {len(group)}."
        )
    return aligned
