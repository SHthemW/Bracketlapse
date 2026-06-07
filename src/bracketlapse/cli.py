from __future__ import annotations

import argparse
import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff"}


class BracketlapseError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser(argv)
    args = parser.parse_args(argv[1:] if argv[:1] == ["video"] else argv)

    try:
        if argv[:1] == ["video"]:
            build_video(args)
        else:
            fuse_brackets(args)
    except BracketlapseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130

    return 0


def build_parser(argv: list[str]) -> argparse.ArgumentParser:
    if argv[:1] == ["video"]:
        parser = argparse.ArgumentParser(
            prog="bracketlapse video",
            description="Create a video from JPG frames with ffmpeg.",
        )
        add_video_arguments(parser)
        return parser

    parser = argparse.ArgumentParser(
        prog="bracketlapse",
        description=(
            "Fuse three-shot bracketed JPG groups. Use 'bracketlapse video' "
            "to create a timelapse video."
        ),
    )
    add_fuse_arguments(parser)
    return parser


def add_fuse_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        help="Directory containing bracketed JPG files. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("hdr_enfuse"),
        help="Output directory. Relative paths are resolved inside the processing directory.",
    )
    parser.add_argument(
        "--pattern",
        default="*.jp*g",
        help="Input glob pattern. Default: *.jp*g",
    )
    parser.add_argument(
        "--group-size",
        type=int,
        default=3,
        help="Number of input images per bracket group. Default: 3",
    )
    parser.add_argument(
        "--sort",
        choices=("name", "time"),
        default="name",
        help="Sort input files by filename or modified time. Default: name",
    )
    parser.add_argument(
        "--align",
        action="store_true",
        help="Align each group with Hugin align_image_stack before fusing.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing fused images.",
    )
    parser.add_argument(
        "--start-number",
        type=int,
        default=1,
        help="Starting number for output names. Default: 1",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many groups. Useful for testing.",
    )
    parser.add_argument(
        "--ext",
        choices=("jpg", "tif"),
        default="jpg",
        help="Output image format extension. Default: jpg",
    )
    parser.add_argument(
        "--no-video",
        action="store_true",
        help="Only create fused frames; do not create a video afterward.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Frames per second for the automatic video. Default: 30",
    )
    parser.add_argument(
        "--video-output",
        type=Path,
        default=Path("hdr_video") / "hdr_timelapse.mp4",
        help=(
            "Automatic video output path. Relative paths are resolved inside "
            "the processing directory. Default: hdr_video/hdr_timelapse.mp4"
        ),
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="x264 CRF quality value for the automatic video. Default: 18",
    )
    parser.add_argument(
        "--preset",
        default="slow",
        help="x264 preset for the automatic video. Default: slow",
    )


def add_video_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        help="Directory containing JPG frames. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output_30fps.mp4"),
        help="Output video path. Relative paths are resolved inside the processing directory.",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Frames per second. Default: 30",
    )
    parser.add_argument(
        "--pattern",
        default="*.jp*g",
        help="Input glob pattern. Default: *.jp*g",
    )
    parser.add_argument(
        "--sort",
        choices=("name", "time"),
        default="name",
        help="Sort input files by filename or modified time. Default: name",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="x264 CRF quality value. Lower is higher quality. Default: 18",
    )
    parser.add_argument(
        "--preset",
        default="slow",
        help="x264 preset. Default: slow",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output video if it already exists.",
    )


def fuse_brackets(args: argparse.Namespace) -> None:
    directory = resolve_processing_directory(args.directory)
    output_dir = resolve_inside(directory, args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    enfuse = require_tool("enfuse")
    align_image_stack = require_tool("align_image_stack") if args.align else None

    files = find_images(directory, args.pattern, args.sort)
    if not files:
        raise BracketlapseError(f"No JPG files matched {args.pattern!r} in {directory}")
    if args.group_size < 2:
        raise BracketlapseError("--group-size must be at least 2")
    if args.fps <= 0:
        raise BracketlapseError("--fps must be greater than zero")
    if len(files) % args.group_size != 0:
        raise BracketlapseError(
            f"Found {len(files)} files, which is not divisible by group size {args.group_size}."
        )

    groups = [
        files[index : index + args.group_size]
        for index in range(0, len(files), args.group_size)
    ]
    if args.limit is not None:
        groups = groups[: args.limit]

    print(f"Input directory: {directory}")
    print(f"Found {len(files)} JPG files, {len(groups)} group(s) to process.")
    print(f"Output directory: {output_dir}")

    for offset, group in enumerate(groups):
        frame_number = args.start_number + offset
        output = output_dir / f"hdr_{frame_number:05d}.{args.ext}"
        if output.exists() and not args.overwrite:
            print(f"[{offset + 1}/{len(groups)}] Skip existing {output.name}")
            continue

        print(f"[{offset + 1}/{len(groups)}] Fusing {output.name}")
        if args.align:
            assert align_image_stack is not None
            with tempfile.TemporaryDirectory(prefix="bracketlapse_align_") as tmp:
                aligned = align_group(align_image_stack, group, Path(tmp), frame_number)
                run_command([enfuse, "-o", str(output), *map(str, aligned)])
        else:
            run_command([enfuse, "-o", str(output), *map(str, group)])

    if not args.no_video:
        video_output = resolve_inside(directory, args.video_output)
        print("Creating video from fused frames.")
        build_video_from_directory(
            directory=output_dir,
            output=video_output,
            fps=args.fps,
            pattern=f"*.{args.ext}",
            sort_mode="name",
            crf=args.crf,
            preset=args.preset,
            overwrite=args.overwrite,
            skip_existing=True,
        )

    print("Done.")


def build_video(args: argparse.Namespace) -> None:
    directory = resolve_processing_directory(args.directory)
    output = resolve_inside(directory, args.output)
    build_video_from_directory(
        directory=directory,
        output=output,
        fps=args.fps,
        pattern=args.pattern,
        sort_mode=args.sort,
        crf=args.crf,
        preset=args.preset,
        overwrite=args.overwrite,
        skip_existing=False,
    )

    print("Done.")


def build_video_from_directory(
    directory: Path,
    output: Path,
    fps: float,
    pattern: str,
    sort_mode: str,
    crf: int,
    preset: str,
    overwrite: bool,
    skip_existing: bool,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    if output.exists() and not overwrite:
        if skip_existing:
            print(f"Skip existing video: {output}")
            return
        raise BracketlapseError(f"Output already exists: {output}. Use --overwrite to replace it.")
    if fps <= 0:
        raise BracketlapseError("--fps must be greater than zero")

    ffmpeg = require_tool("ffmpeg")
    files = find_images(directory, pattern, sort_mode)
    if not files:
        raise BracketlapseError(f"No JPG files matched {pattern!r} in {directory}")

    print(f"Input directory: {directory}")
    print(f"Found {len(files)} JPG frames.")
    print(f"Output video: {output}")

    with tempfile.TemporaryDirectory(prefix="bracketlapse_ffmpeg_") as tmp:
        concat_file = Path(tmp) / "frames.ffconcat"
        write_ffconcat(concat_file, files, 1.0 / fps)

        command = [
            ffmpeg,
            "-y" if overwrite else "-n",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-r",
            format_fps(fps),
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-pix_fmt",
            "yuv420p",
            str(output),
        ]
        run_command(command)


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


def find_images(directory: Path, pattern: str, sort_mode: str) -> list[Path]:
    files = [
        path
        for path in directory.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
            and fnmatch.fnmatchcase(path.name.lower(), pattern.lower())
        )
    ]
    if sort_mode == "time":
        return sorted(files, key=lambda path: (path.stat().st_mtime, path.name.lower()))
    return sorted(files, key=lambda path: path.name.lower())


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


def write_ffconcat(path: Path, files: list[Path], frame_duration: float) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("ffconcat version 1.0\n")
        for file in files:
            handle.write(f"file {quote_ffconcat_path(file)}\n")
            handle.write(f"duration {frame_duration:.16g}\n")
        handle.write(f"file {quote_ffconcat_path(files[-1])}\n")


def quote_ffconcat_path(path: Path) -> str:
    text = path.resolve().as_posix()
    return "'" + text.replace("'", r"'\''") + "'"


def format_fps(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def run_command(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        raise BracketlapseError(f"Executable not found: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise BracketlapseError(
            f"Command failed with exit code {exc.returncode}: {' '.join(command)}"
        ) from exc


if __name__ == "__main__":
    raise SystemExit(main())
