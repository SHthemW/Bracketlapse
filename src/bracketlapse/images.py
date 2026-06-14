from __future__ import annotations

import fnmatch
from pathlib import Path

from .common import BracketlapseError, log

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff"}
GENERATED_DIRECTORY_NAMES = {"hdr_enfuse", "hdr_deflick", "hdr_video"}


def find_images(directory: Path, pattern: str, sort_mode: str) -> list[Path]:
    try:
        directory_entries = list(directory.iterdir())
    except OSError as exc:
        log.warn(f"skipping unreadable directory {directory}: {exc}")
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
            log.warn(f"skipping unreadable path {path}: {exc}")
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
    deflick_output_dir: Path,
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
        excluded_paths=[output_dir, deflick_output_dir, video_output.parent],
        pattern=pattern,
        sort_mode=sort_mode,
    )

    if merge_subdirs:
        root_images = find_images(directory, pattern, sort_mode)
        if not candidates:
            if root_images:
                return [directory]
            raise BracketlapseError(f"No mergeable subdirectories were found in {directory}")
        if root_images:
            return [directory, *candidates]
        return candidates

    if no_merge_subdirs or not candidates:
        return [directory]

    current_directory_files = find_images(directory, pattern, sort_mode)
    default_merge = not current_directory_files

    log.info("Subdirectories with matching images were found:")
    for index, candidate in enumerate(candidates, start=1):
        count = len(find_images(candidate, pattern, sort_mode))
        log.info(f"  {index}. {candidate.name} ({count} files)")

    prompt = (
        "Merge multiple subdirectories? [Y/n]: "
        if default_merge
        else "Merge multiple subdirectories? [y/N]: "
    )
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
    excluded_paths: list[Path],
    pattern: str,
    sort_mode: str,
) -> list[Path]:
    excluded = {path.resolve() for path in excluded_paths}
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
