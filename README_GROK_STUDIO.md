# Grok Studio Lab

Version V6: Gallery release with the expanded Image Editor and folder layout controls.

Grok Studio Lab is a local Mac web app for Grok Imagine-style image, video, prompt, and extension workflows.

## Run

Double-click:

```bash
Grok Studio Lab.app
```

This opens the local server in the background without opening Terminal. Startup
logs are written to:

```text
Grok Studio Lab/grok_studio_data/logs/grok_studio.log
```

The app launcher checks common Homebrew, python.org, pyenv, Conda, and system
Python 3 locations so Finder launches work even when the Terminal `PATH` is not
available. If startup fails, the app shows an error dialog with the log path.

When launched as an app, writable settings, logs, account registrations, and the
built-in library are stored beside the app bundle in the extracted distribution
folder:

```text
Grok Studio Lab/grok_studio_data/
```

If macOS launches the downloaded app from a read-only App Translocation path,
the launcher automatically uses this writable fallback instead:

```text
~/Library/Application Support/Grok Studio Lab/V6/Instances/<download-instance>/
```

Each newly downloaded translocated app uses a separate clean instance folder,
so an older download's library settings are not reused.

For debugging, you can still run from Terminal:

```bash
python3 grok_studio.py --open
```

Then open:

```text
http://127.0.0.1:8765
```

Paused-point extension trims the source MP4 locally before submitting it. Install
ffmpeg first if you want that behavior:

```bash
brew install ffmpeg
```

## Auth

The app does not require typing an API key. It reads the Grok Build CLI OAuth
session from:

```text
~/.grok/auth.json
```

If that token expires, Grok Studio tries to refresh it from the stored
`refresh_token` before sending a request, and retries once after a 401/403 auth
error. If refresh also fails, log in again with the Grok Build CLI, then restart
Grok Studio.

## Local storage

Generated media is downloaded to the built-in local library by default:

```text
grok_studio_data/media/
```

Use **Library Folder** in the sidebar to choose an external folder. Grok Studio
Lab will create:

```text
Image/
Video/
Prompt/
Upload Image/
.grok_studio/
```

New generations are saved there, and future updated app packages can load the
same folder again.

Gallery workspaces are stored as real Finder folders:

```text
Gallery/
  Collection/
    Workspace/
      Image/
      Video/
      Prompt/
```

The main Home screen includes every generated item. A Gallery workspace Home
screen only includes items created or moved into that workspace. Use
`Move to Gallery` on an unassigned Home item to move its real local file into a
Gallery workspace.

In Gallery, click a collection or workspace once to select it. Double-click a
workspace to open its independent Home screen. `Rename` changes both the Gallery
name and its real Finder folder name. `Delete` removes the selected folder and
its contents; non-empty folders show a confirmation warning before deletion.

The browser UI displays those local files through `127.0.0.1`. The app does not
publish generated images or videos to a public website. Requests and uploaded
source media still go to xAI/Grok servers to perform generation, editing, or
video extension.

## Supported

- Image generation
- Image editing with up to 3 Source Images, including file click, file drag-and-drop, Library drag-and-drop, and per-image removal
- Text-to-video
- Image-to-video
- Reference-to-video with up to 7 Reference Images and per-image removal
- Video model toggle: Default `grok-imagine-video`, optional `grok-imagine-video-1.5`
- Video extension by dropping a Library video or uploading an MP4, with playable thumbnail preview
- Extend from the paused point when ffmpeg is installed locally
- Image Count selector: 1 to 4, default 1
- Image Resolution selector: 2K Image, 1K Image, default 2K Image
- Video Duration selector: 15 to 1 seconds, default 15
- Video Resolution selector: 720P Video, 480P Video, default 720P Video
- Extend Duration selector: 10 to 2 seconds, default 10
- Extend trim quality defaults to High CRF 16 with preset medium
- Unified custom video cards and fullscreen player with loop, A-B repeat, and pitch-preserving speed controls
- Studio fullscreen player volume control with Up/Down arrow and mouse wheel shortcuts
- Library video cards use the simple title `Video`
- Prompt saving with a title into local text files
- Uploaded source images saved separately in `Upload Image/`
- Imagine-style media gallery and separate prompt library
- Gallery collections with independent workspace Home, Video, Image, Prompt, and Search views
- Single-click Gallery folder selection, double-click workspace opening, folder rename, and folder deletion
- Real Finder folder storage for Gallery workspaces and `Move to Gallery`
- Sidebar hide/show
- Job cancel/dismiss controls
- Local library multi-select deletion, including local media files
- Local library multi-select download
- Drag local image results into `Start image` for image-to-video
- Send local image results to `Start image` with `To Video`
- Start image thumbnail preview
- Always-visible local library selection dots
- Height-fit image preview pop-up for library images and uploaded image thumbnails
- Open the local media folder in Finder
- Persistent error panel with short labels such as `Moderate`, plus copy/close controls
- Browser-tab close requests local server shutdown when no jobs are running

## Troubleshooting generation

When you press `Go`, the app UI should show `Progress` in the Jobs area.
If you run from Terminal for debugging, Terminal should show:

```text
POST /api/client-event
POST /api/video
```

If the log only repeats `GET /api/jobs`, the browser did not submit the job.
Hard-refresh the page with `Command + Shift + R`, select the `Video` tab, choose
the image under `Start image`, enter a prompt, and press `Go` again.

If `POST /api/video` appears and the job fails, the red job chip will show the
error. The most common cause is an expired Grok Build CLI OAuth session; log in
again with the Grok Build CLI and restart Grok Studio.
