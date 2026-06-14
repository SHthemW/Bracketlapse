from __future__ import annotations

from pathlib import Path
import re

from .common import log


def build_fusion_groups(files: list[Path], group_size: int) -> list[list[Path]]:
    numbered_files = []
    for path in files:
        sequence_number = extract_sequence_number(path)
        if sequence_number is None:
            return chunk_files(files, group_size)
        numbered_files.append((sequence_number, path))

    if len({sequence_number for sequence_number, _ in numbered_files}) != len(numbered_files):
        log.warn("duplicate sequence numbers were found; falling back to simple grouping.")
        return chunk_files(files, group_size)

    sequence_map = {sequence_number: path for sequence_number, path in numbered_files}
    start_sequence = min(sequence_number for sequence_number, _ in numbered_files)
    end_sequence = max(sequence_number for sequence_number, _ in numbered_files)

    groups: list[list[Path]] = []
    for block_start in range(start_sequence, end_sequence + 1, group_size):
        expected = list(range(block_start, block_start + group_size))
        group = [sequence_map.get(sequence_number) for sequence_number in expected]
        missing = [
            sequence_number
            for sequence_number, item in zip(expected, group)
            if item is None
        ]
        if missing:
            log.warn(
                f"skipping incomplete HDR group "
                f"{block_start}-{block_start + group_size - 1}; "
                f"missing sequence number(s): {format_sequence_numbers(missing)}"
            )
            continue
        groups.append([path for path in group if path is not None])

    return groups


def chunk_files(files: list[Path], group_size: int) -> list[list[Path]]:
    return [files[index : index + group_size] for index in range(0, len(files), group_size)]


def extract_sequence_number(path: Path) -> int | None:
    matches = re.findall(r"\d+", path.stem)
    if not matches:
        return None
    return int(matches[-1])


def format_sequence_numbers(numbers: list[int]) -> str:
    return ", ".join(str(number) for number in numbers)


def detect_sequence_gap_ranges(files: list[Path]) -> list[tuple[int, int]]:
    sequence_numbers: list[int] = []
    seen_numbers: set[int] = set()
    for path in files:
        sequence_number = extract_sequence_number(path)
        if sequence_number is None or sequence_number in seen_numbers:
            return []
        sequence_numbers.append(sequence_number)
        seen_numbers.add(sequence_number)

    if not sequence_numbers:
        return []

    missing_numbers = [
        number
        for number in range(min(sequence_numbers), max(sequence_numbers) + 1)
        if number not in seen_numbers
    ]
    return compress_number_ranges(missing_numbers)


def compress_number_ranges(numbers: list[int]) -> list[tuple[int, int]]:
    if not numbers:
        return []

    ranges: list[tuple[int, int]] = []
    start = previous = numbers[0]
    for number in numbers[1:]:
        if number == previous + 1:
            previous = number
            continue
        ranges.append((start, previous))
        start = previous = number
    ranges.append((start, previous))
    return ranges


def format_sequence_gap_ranges(ranges: list[tuple[int, int]]) -> str:
    return ", ".join(
        f"{start}" if start == end else f"{start}-{end}"
        for start, end in ranges
    )
