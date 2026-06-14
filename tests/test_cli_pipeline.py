from __future__ import annotations

from pathlib import Path

from helpers import create_input_frames, create_mock_tools, run_bracketlapse
from helpers import write_executable


def test_no_arguments_prints_main_help(tmp_path: Path) -> None:
    result = run_bracketlapse([], tmp_path / "bin")

    assert result.returncode == 0
    assert "usage: bracketlapse" in result.stdout
    assert "--deflick-output" in result.stdout
    assert "--debug" in result.stdout
    assert "Checking runtime environment" not in result.stdout


def test_video_without_arguments_prints_video_help(tmp_path: Path) -> None:
    result = run_bracketlapse(["video"], tmp_path / "bin")

    assert result.returncode == 0
    assert "usage: bracketlapse video" in result.stdout
    assert "--output" in result.stdout
    assert "--debug" in result.stdout
    assert "Checking runtime environment" not in result.stdout


def test_fuse_pipeline_deflickers_before_video(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    work_dir = tmp_path / "work"
    create_mock_tools(bin_dir)
    create_input_frames(work_dir, 6)

    result = run_bracketlapse(
        [str(work_dir), "--no-merge-subdirs", "--overwrite", "--fps", "24"],
        bin_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert sorted(path.name for path in (work_dir / "hdr_enfuse").glob("*.jpg")) == [
        "hdr_00001.jpg",
        "hdr_00002.jpg",
    ]
    assert sorted(path.name for path in (work_dir / "hdr_deflick").glob("*.jpg")) == [
        "hdr_00001.jpg",
        "hdr_00002.jpg",
    ]
    assert (work_dir / "hdr_video" / "hdr_timelapse.mp4").read_text(encoding="utf-8") == "video\n"
    assert "mock enfuse debug" not in result.stdout


def test_debug_creates_hdr_video_and_prints_debug_logs(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    work_dir = tmp_path / "work"
    create_mock_tools(bin_dir)
    create_input_frames(work_dir, 3)

    result = run_bracketlapse(
        [str(work_dir), "--no-merge-subdirs", "--overwrite", "--debug"],
        bin_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "mock enfuse debug" in result.stdout
    assert "mock deflicker debug" in result.stdout
    assert (work_dir / "hdr_video" / "hdr_timelapse_hdr_debug.mp4").exists()
    assert (work_dir / "hdr_video" / "hdr_timelapse.mp4").exists()


def test_no_video_still_deflickers_by_default(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    work_dir = tmp_path / "work"
    create_mock_tools(bin_dir)
    create_input_frames(work_dir, 3)

    result = run_bracketlapse([str(work_dir), "--no-merge-subdirs", "--no-video"], bin_dir)

    assert result.returncode == 0, result.stderr + result.stdout
    assert (work_dir / "hdr_enfuse" / "hdr_00001.jpg").exists()
    assert (work_dir / "hdr_deflick" / "hdr_00001.jpg").exists()
    assert not (work_dir / "hdr_video").exists()


def test_no_deflick_uses_fused_frames_for_video(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    work_dir = tmp_path / "work"
    create_mock_tools(bin_dir, include_deflicker=False)
    create_input_frames(work_dir, 3)

    result = run_bracketlapse(
        [str(work_dir), "--no-merge-subdirs", "--no-deflick", "--overwrite"],
        bin_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (work_dir / "hdr_enfuse" / "hdr_00001.jpg").exists()
    assert not (work_dir / "hdr_deflick").exists()
    assert (work_dir / "hdr_video" / "hdr_timelapse.mp4").exists()


def test_video_command_only_requires_ffmpeg(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    frames_dir = tmp_path / "frames"
    create_mock_tools(bin_dir, include_deflicker=False)
    (bin_dir / "enfuse").unlink()
    create_input_frames(frames_dir, 2)

    result = run_bracketlapse(
        ["video", str(frames_dir), "--output", "out.mp4", "--overwrite"],
        bin_dir,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert (frames_dir / "out.mp4").read_text(encoding="utf-8") == "video\n"


def test_fuse_failure_does_not_create_output_frame(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    work_dir = tmp_path / "work"
    bin_dir.mkdir()
    write_executable(
        bin_dir / "enfuse",
        """#!/bin/sh
printf "enfuse failed\\n" >&2
exit 1
""",
    )
    create_input_frames(work_dir, 3)

    result = run_bracketlapse([str(work_dir), "--no-merge-subdirs", "--no-video"], bin_dir)

    assert result.returncode == 1
    assert "enfuse" in result.stderr
    assert not (work_dir / "hdr_enfuse" / "hdr_00001.jpg").exists()
