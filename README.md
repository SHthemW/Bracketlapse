# Bracketlapse

Bracketlapse is a cross-platform command line tool for bracketed timelapse work:

- Fuse every 3 JPG files into one exposure-fused HDR-looking frame with Hugin `enfuse`.
- Optionally align each bracket group with Hugin `align_image_stack`.
- Create an MP4 timelapse from JPG frames with `ffmpeg`.

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

Fuse bracketed JPG files in a directory:

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

The default output directory is `hdr_enfuse` inside the processing directory.

Use alignment when the camera moved between the bracketed shots:

```bash
bracketlapse "E:\Medias\Images\example" --align
```

Test only the first few groups:

```bash
bracketlapse "E:\Medias\Images\example" --limit 3 --overwrite
```

Create a 30 fps MP4 from JPG frames:

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
