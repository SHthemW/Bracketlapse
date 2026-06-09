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
GENERATED_DIRECTORY_NAMES = {"hdr_enfuse", "hdr_video"}


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
        "--merge-subdirs",
        action="store_true",
        help="Merge images from selected immediate subdirectories of the processing directory.",
    )
    parser.add_argument(
        "--merge-dirs",
        nargs="+",
        type=Path,
        help=(
            "Subdirectories to merge. Relative paths are resolved inside the "
            "processing directory. Implies --merge-subdirs."
        ),
    )
    parser.add_argument(
        "--no-merge-subdirs",
        action="store_true",
        help="Do not ask about merging subdirectories; process only the chosen directory.",
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
        help="x265 CRF quality value for the automatic video. Default: 18",
    )
    parser.add_argument(
        "--preset",
        default="slow",
        help="x265 preset for the automatic video. Default: slow",
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
        help="x265 CRF quality value. Lower is higher quality. Default: 18",
    )
    parser.add_argument(
        "--preset",
        default="slow",
        help="x265 preset. Default: slow",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output video if it already exists.",
    )


def fuse_brackets(args: argparse.Namespace) -> None:
    directory = resolve_fuse_working_directory(args)
    output_dir = resolve_inside(directory, args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    enfuse = require_tool("enfuse")
    align_image_stack = require_tool("align_image_stack") if args.align else None

    source_dirs = resolve_source_directories(
        directory=directory,
        output_dir=output_dir,
        video_output=resolve_inside(directory, args.video_output),
        pattern=args.pattern,
        sort_mode=args.sort,
        merge_subdirs=args.merge_subdirs,
        merge_dirs=args.merge_dirs,
        no_merge_subdirs=(
            args.no_merge_subdirs
            or (
                args.directory is not None
                and not is_current_directory_argument(args.directory)
                and not args.merge_subdirs
                and not args.merge_dirs
            )
        ),
    )
    files = find_images_in_directories(source_dirs, args.pattern, args.sort)
    if not files:
        raise BracketlapseError(
            f"No image files matched {args.pattern!r} in {format_paths(source_dirs)}"
        )
    if args.group_size < 2:
        raise BracketlapseError("--group-size must be at least 2")
    if args.fps <= 0:
        raise BracketlapseError("--fps must be greater than zero")
    remainder = len(files) % args.group_size
    if remainder:
        dropped_files = files[-remainder:]
        files = files[:-remainder]
        print(
            "Warning: "
            f"found {len(files) + remainder} files, which is not divisible by "
            f"group size {args.group_size}; dropping the last {remainder} file(s): "
            f"{format_paths(dropped_files)}"
        )
    if not files:
        raise BracketlapseError(
            f"No complete groups can be formed with group size {args.group_size}."
        )

    groups = [
        files[index : index + args.group_size]
        for index in range(0, len(files), args.group_size)
    ]
    if args.limit is not None:
        groups = groups[: args.limit]

    print(f"Working directory: {directory}")
    print(f"Input directories: {format_paths(source_dirs)}")
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
            "libx265",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-tag:v",
            "hvc1",
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


def resolve_fuse_working_directory(args: argparse.Namespace) -> Path:
    if args.directory is not None:
        return resolve_processing_directory(args.directory)

    current_directory = Path.cwd().resolve()
    if args.merge_subdirs or args.merge_dirs or args.no_merge_subdirs:
        return current_directory

    output_dir = resolve_inside(current_directory, args.output)
    video_output = resolve_inside(current_directory, args.video_output)
    candidates = find_merge_candidates(
        directory=current_directory,
        output_dir=output_dir,
        video_output=video_output,
        pattern=args.pattern,
        sort_mode=args.sort,
    )
    if candidates:
        return current_directory

    return resolve_processing_directory(None)


def is_current_directory_argument(value: Path) -> bool:
    return value.expanduser().resolve() == Path.cwd().resolve()


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
    try:
        directory_entries = list(directory.iterdir())
    except OSError as exc:
        print(f"Warning: skipping unreadable directory {directory}: {exc}", file=sys.stderr)
        return []

    files = []
    for path in directory_entries:
        try:
            is_matching_file = (
                path.is_file()
                and path.suffix.lower() in IMAGE_EXTENSIONS
                and fnmatch.fnmatchcase(path.name.lower(), pattern.lower())
            )
        except OSError as exc:
            print(f"Warning: skipping unreadable path {path}: {exc}", file=sys.stderr)
            continue
        if is_matching_file:
            files.append(path)
    if sort_mode == "time":
        return sorted(files, key=image_sort_key_by_time)
    return sorted(files, key=lambda path: path.name.lower())


def image_sort_key_by_time(path: Path) -> tuple[float, str]:
    try:
        modified_time = path.stat().st_mtime
    except OSError:
        modified_time = 0.0
    return (modified_time, path.name.lower())


def find_images_in_directories(
    directories: list[Path],
    pattern: str,
    sort_mode: str,
) -> list[Path]:
    files: list[Path] = []
    for directory in directories:
        files.extend(find_images(directory, pattern, sort_mode))
    if sort_mode == "time":
        return sorted(
            files,
            key=lambda path: (
                image_sort_key_by_time(path)[0],
                path.parent.name.lower(),
                path.name.lower(),
            ),
        )
    return files


def resolve_source_directories(
    directory: Path,
    output_dir: Path,
    video_output: Path,
    pattern: str,
    sort_mode: str,
    merge_subdirs: bool,
    merge_dirs: list[Path] | None,
    no_merge_subdirs: bool,
) -> list[Path]:
    if merge_dirs:
        return resolve_merge_directories(directory, merge_dirs)

    candidates = find_merge_candidates(
        directory=directory,
        output_dir=output_dir,
        video_output=video_output,
        pattern=pattern,
        sort_mode=sort_mode,
    )

    if merge_subdirs:
        if not candidates:
            raise BracketlapseError(f"No mergeable subdirectories were found in {directory}")
        return candidates

    if no_merge_subdirs or not candidates:
        return [directory]

    current_directory_files = find_images(directory, pattern, sort_mode)
    default_merge = not current_directory_files

    print("Subdirectories with matching images were found:")
    for index, candidate in enumerate(candidates, start=1):
        count = len(find_images(candidate, pattern, sort_mode))
        print(f"  {index}. {candidate.name} ({count} files)")

    prompt = "Merge multiple subdirectories? [Y/n]: " if default_merge else "Merge multiple subdirectories? [y/N]: "
    answer = input(prompt).strip().lower()
    if not answer and default_merge:
        return candidates
    if answer not in {"y", "yes"}:
        return [directory]

    raw_selection = input(
        "Subdirectories to merge [all, numbers, or names; default: all]: "
    ).strip()
    if not raw_selection:
        return candidates

    return select_merge_candidates(candidates, raw_selection)


def find_merge_candidates(
    directory: Path,
    output_dir: Path,
    video_output: Path,
    pattern: str,
    sort_mode: str,
) -> list[Path]:
    excluded = {output_dir.resolve(), video_output.parent.resolve()}
    candidates = []
    for path in directory.iterdir():
        if not path.is_dir():
            continue
        if path.name.lower() in GENERATED_DIRECTORY_NAMES:
            continue
        resolved = path.resolve()
        if resolved in excluded:
            continue
        if find_images(path, pattern, sort_mode):
            candidates.append(resolved)
    return sorted(candidates, key=lambda path: path.name.lower())


def resolve_merge_directories(base: Path, merge_dirs: list[Path]) -> list[Path]:
    resolved_dirs = []
    for value in merge_dirs:
        directory = value.expanduser()
        if not directory.is_absolute():
            directory = base / directory
        directory = directory.resolve()
        if not directory.exists():
            raise BracketlapseError(f"Merge directory does not exist: {directory}")
        if not directory.is_dir():
            raise BracketlapseError(f"Merge path is not a directory: {directory}")
        resolved_dirs.append(directory)
    return resolved_dirs


def select_merge_candidates(candidates: list[Path], raw_selection: str) -> list[Path]:
    if raw_selection.lower() == "all":
        return candidates

    selected: list[Path] = []
    by_name = {path.name.lower(): path for path in candidates}
    tokens = [
        token.strip().strip('"')
        for part in raw_selection.split(",")
        for token in part.split()
        if token.strip()
    ]
    for token in tokens:
        if token.isdigit():
            index = int(token)
            if index < 1 or index > len(candidates):
                raise BracketlapseError(f"Subdirectory number is out of range: {token}")
            candidate = candidates[index - 1]
        else:
            candidate = by_name.get(token.lower())
            if candidate is None:
                raise BracketlapseError(f"Unknown subdirectory: {token}")
        if candidate not in selected:
            selected.append(candidate)

    if not selected:
        raise BracketlapseError("No subdirectories were selected for merging.")
    return selected


def format_paths(paths: list[Path]) -> str:
    return ", ".join(str(path) for path in paths)


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
