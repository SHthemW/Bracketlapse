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
- Automatically create an MP4 timelapse from the fused frames with `ffmpeg`.
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

By default it sorts files by name and processes every 3 JPG files as one group:

```text
DSC_0480.JPG, DSC_0481.JPG, DSC_0482.JPG -> hdr_00001.jpg
DSC_0483.JPG, DSC_0484.JPG, DSC_0485.JPG -> hdr_00002.jpg
```

The default fused-frame output directory is `hdr_enfuse` inside the processing directory.
The default video output is `hdr_video/hdr_timelapse.mp4` inside the processing directory.

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
- `--overwrite`: replace existing output.
- `--align`: align bracket groups before exposure fusion.
- `--ext jpg|tif`: choose fused frame extension.
- `--no-video`: skip automatic video creation after fusion.
- `--fps`: video frames per second.
- `--video-output PATH`: automatic video output path.
