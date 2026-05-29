import subprocess
import json
import os
from pathlib import Path


def get_video_info(video_path):
    result = {"duration": 0, "width": 0, "height": 0, "fps": 0}
    if not os.path.isfile(video_path):
        return result
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True, timeout=10,
        ).stdout
        data = json.loads(out)
        if "format" in data:
            result["duration"] = float(data["format"].get("duration", 0))
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                result["width"] = stream.get("width", 0)
                result["height"] = stream.get("height", 0)
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    parts = fps_str.split("/")
                    if len(parts) == 2 and float(parts[1]) > 0:
                        result["fps"] = round(float(parts[0]) / float(parts[1]), 2)
                break
    except Exception:
        pass
    return result


def format_duration(seconds):
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    return f"{m}:{s:02d}"


def format_resolution(w, h):
    if w and h:
        return f"{w}x{h}"
    return ""


def send_notification(title, message, icon=""):
    try:
        cmd = ["notify-send", title, message]
        if icon:
            cmd.extend(["-i", icon])
        subprocess.run(cmd, capture_output=True, timeout=2)
    except Exception:
        pass


def generate_thumbnail(video_path, output_path="/tmp/wp_thumb.jpg"):
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", video_path, "-ss", "00:00:01",
             "-vframes", "1",
             "-vf", "scale=256:144:force_original_aspect_ratio=decrease,"
                     "pad=256:144:(ow-iw)/2:(oh-ih)/2",
             "-q:v", "5", output_path],
            capture_output=True, timeout=5,
        )
        p = Path(output_path)
        if p.exists() and p.stat().st_size > 0:
            return output_path
    except Exception:
        pass
    return None
