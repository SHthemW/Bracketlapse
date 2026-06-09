<p align="center">
  <img src="res/title.jpg" alt="Bracketlapse" width="60%">
</p>

<p align="center">
  English | <a href="README.zh-CN.md">简体中文</a>
</p>

# Bracketlapse

Bracketlapse is a cross-platform command line tool for bracketed timelapse work:

- Fuse every 3 JPG files into one exposure-fused HDR-looking frame with Hugin `enfuse`.
- Optionally align each bracket group with Hugin `align_image_stack`.
- Automatically create an HEVC/H.265 MP4 timelapse from the fused frames with `ffmpeg`.
- Especially useful for Nikon and FUJIFILM cameras, because they can automatically shoot bracketed exposures during timelapse capture. This program was tested with my own Nikon Z30.

<p align="center">
  <img src="res/z30_cn.jpg" alt="Nikon Z30 bracketing settings in Chinese" width="33%">
  <img src="res/z30_en.jpg" alt="Nikon Z30 bracketing settings in English" width="33%">
</p>

It runs on Windows and macOS with Python 3.10+.

## Requirements

Install these tools and make sure their `bin` directories are in `PATH`:

- Hugin command line tools: `enfuse`, and optionally `align_image_stack`
- `ffmpeg`

On Windows, if Hugin is installed at `D:\Medias\Hugin\bin`, add that directory to your user `PATH`.

## Install for Development

From this repository:

```powershell
python -m pip install -e .
```

On macOS, use `python3` if `python` is not available:

```bash
python3 -m pip install -e .
```

## Usage

Fuse bracketed JPG files in a directory, then automatically create a video:

```bash
bracketlapse "E:\Medias\Images\example"
```

If you do not pass a directory, Bracketlapse asks for one:

```bash
bracketlapse
```

Standby mode watches one directory until its recursive entry count stops increasing, then moves everything into a dated folder under the target directory and runs the normal fusion/video flow there:

```bash
bracketlapse --standby WATCH_DIR TARGET_DIR QUIET_SECONDS [loop]
```

It prints a status log every QUIET_SECONDS interval while listening.

If a folder named like `20260609` already exists, the next one becomes `20260609-1`, then `20260609-2`, and so on.

When the input filenames contain a numeric sequence and one or more numbers are missing, the incomplete HDR group is skipped, later groups stay aligned, and a warning is printed.

If you run Bracketlapse from a directory that contains image subdirectories, which is common because camera storage formats usually enforce strict limits on the maximum number of photos in a single folder, it asks whether to merge multiple subdirectories. In merge mode, the selected subdirectories are used as input, while `hdr_enfuse` and `hdr_video` are still created in the current working directory.

<p align="center">
  <img src="res/multi_folders.png" alt="Multiple image folders" width="66%">
</p>

Merge all detected image subdirectories:

```bash
bracketlapse --merge-subdirs
```

Merge specific subdirectories:

```bash
bracketlapse --merge-dirs part1 part2 part3
```

Ignore subdirectories and process only the chosen directory:

```bash
bracketlapse --no-merge-subdirs
```

By default it sorts files by name and processes every 3 JPG files as one group:

```text
DSC_0480.JPG, DSC_0481.JPG, DSC_0482.JPG -> hdr_00001.jpg
DSC_0483.JPG, DSC_0484.JPG, DSC_0485.JPG -> hdr_00002.jpg
```

If the total number of input files is not divisible by the group size, Bracketlapse drops the final leftover file(s), prints a warning, and continues processing the complete groups.

The default fused-frame output directory is `hdr_enfuse` inside the processing directory.
The default video output is `hdr_video/hdr_timelapse.mp4` inside the processing directory. Videos are encoded as HEVC/H.265.

Use alignment when the camera moved between the bracketed shots:

```bash
bracketlapse "E:\Medias\Images\example" --align
```

Test only the first few groups:

```bash
bracketlapse "E:\Medias\Images\example" --limit 3 --overwrite
```

Only create fused frames and skip the automatic video:

```bash
bracketlapse "E:\Medias\Images\example" --no-video
```

Choose video settings for the automatic video:

```bash
bracketlapse "E:\Medias\Images\example" --fps 30 --video-output hdr_video\hdr_timelapse.mp4
```

Create a video manually from an existing JPG frame directory:

```bash
bracketlapse video "E:\Medias\Images\example\hdr_enfuse" --fps 30 --output hdr_timelapse.mp4
```

The video command also asks for the processing directory if it is omitted:

```bash
bracketlapse video
```

## Useful Options

```bash
bracketlapse --help
bracketlapse video --help
```

Important options:

- `--sort name|time`: choose filename sorting or modified-time sorting.
- `--output PATH`: write output to a custom directory or file.
- `--merge-subdirs`: merge all detected image subdirectories.
- `--merge-dirs DIR...`: merge specific subdirectories.
- `--no-merge-subdirs`: ignore subdirectories and process only the chosen directory.
- `--overwrite`: replace existing output.
- `--align`: align bracket groups before exposure fusion.
- `--ext jpg|tif`: choose fused frame extension.
- `--no-video`: skip automatic video creation after fusion.
- `--fps`: video frames per second.
- `--video-output PATH`: automatic video output path.
- `--crf` and `--preset`: x265 quality and speed settings for video encoding.

## License

Bracketlapse is licensed under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE) for details.
