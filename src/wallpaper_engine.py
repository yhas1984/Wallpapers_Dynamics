import subprocess
import os
import signal
import time
import json
import socket
import threading
import shutil
import tempfile
import shutil
from pathlib import Path
from Xlib import X, display
from Xlib import Xatom
from Xlib.protocol import event as xevent

try:
    import dbus
except Exception:
    dbus = None

IPC_SOCKET = Path.home() / ".config" / "wallpaper-dinamicos" / "mpv-socket"

PLAYBACK_MODES = {
    "fill": {"keepaspect": True, "panscan": 1.0},
    "fit": {"keepaspect": True, "panscan": 0.0},
    "stretch": {"keepaspect": False, "panscan": 0.0},
    "center": {"keepaspect": True, "panscan": 0.0, "video-align-x": 0, "video-align-y": 0},
}

def _mode_to_cmd_args(mode):
    props = PLAYBACK_MODES.get(mode, PLAYBACK_MODES["fill"])
    args = []
    args.append("--keepaspect=yes" if props.get("keepaspect", True) else "--keepaspect=no")
    panscan = props.get("panscan", 0.0)
    if panscan:
        args.append(f"--panscan={panscan}")
    for key in ("video-align-x", "video-align-y"):
        if key in props:
            args.append(f"--{key}={props[key]}")
    return args

def _detect_gpu():
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            return "nvidia"
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["glxinfo", "-B"],
            capture_output=True, text=True, timeout=3,
        )
        for line in r.stdout.splitlines():
            if "OpenGL vendor" in line:
                vendor = line.split(":")[-1].strip().lower()
                if "nvidia" in vendor:
                    return "nvidia"
                if "amd" in vendor or "ati" in vendor or "advanced micro" in vendor:
                    return "amd"
                if "intel" in vendor:
                    return "intel"
                return vendor.split()[-1]
    except Exception:
        pass
    return "unknown"

GSETTINGS_SCHEMA = "com.deepin.dde.appearance"
GSETTINGS_KEY = "background-uris"


class WallpaperEngine:
    def __init__(self, desktop="unknown", init_window=True):
        self._desktop = desktop
        self._window = None
        self._mpv_process = None
        self._current_video = None
        self._filters = {}
        self._ipc_socket = str(IPC_SOCKET)
        self._is_paused = False
        self._is_muted = True
        self._ipc_ready = False
        self._original_wallpaper = None
        self._available = False
        if init_window:
            try:
                self._display = display.Display()
                self._screen = self._display.screen()
                self._root = self._screen.root
                self._setup_window()
                self._available = True
            except Exception:
                self._display = None
                self._screen = None
                self._root = None
        else:
            self._display = None
            self._screen = None
            self._root = None

    def _get_screen_geometry(self):
        return self._screen.width_in_pixels, self._screen.height_in_pixels

    def _find_desktop_window(self):
        type_atom = self._display.intern_atom("_NET_WM_WINDOW_TYPE")
        desk_type_atom = self._display.intern_atom("_NET_WM_WINDOW_TYPE_DESKTOP")
        class_atom = self._display.intern_atom("WM_CLASS")

        def _search(parent):
            try:
                children = parent.query_tree().children
                for child in children:
                    try:
                        cls = child.get_full_property(class_atom, Xatom.STRING)
                        if cls:
                            val = cls.value.decode("utf-8", errors="ignore")
                            if "dde-shell" in val and "desktop" in val:
                                return child
                        prop = child.get_full_property(type_atom, Xatom.ATOM)
                        if prop and desk_type_atom in prop.value:
                            if self._window and child.id == self._window.id:
                                continue
                            return child
                    except Exception:
                        pass
                    result = _search(child)
                    if result:
                        return result
            except Exception:
                pass
            return None

        return _search(self._root)

    def _setup_window(self):
        if not self._display:
            from Xlib import display as xdisplay
            self._display = xdisplay.Display()
            self._screen = self._display.screen()
            self._root = self._screen.root
        w, h = self._get_screen_geometry()

        win = self._root.create_window(
            0, 0, w, h, 0,
            X.CopyFromParent,
            X.InputOutput,
            X.CopyFromParent,
            background_pixel=self._screen.black_pixel,
            event_mask=X.ExposureMask | X.StructureNotifyMask | X.SubstructureNotifyMask,
        )

        atoms = {
            "TYPE": self._display.intern_atom("_NET_WM_WINDOW_TYPE"),
            "DESKTOP": self._display.intern_atom("_NET_WM_WINDOW_TYPE_DESKTOP"),
            "STATE": self._display.intern_atom("_NET_WM_STATE"),
            "BELOW": self._display.intern_atom("_NET_WM_STATE_BELOW"),
            "STICKY": self._display.intern_atom("_NET_WM_STATE_STICKY"),
            "SKIP_P": self._display.intern_atom("_NET_WM_STATE_SKIP_PAGER"),
            "SKIP_T": self._display.intern_atom("_NET_WM_STATE_SKIP_TASKBAR"),
            "DESKTOP_ID": self._display.intern_atom("_NET_WM_DESKTOP"),
            "NAME": self._display.intern_atom("_NET_WM_NAME"),
        }

        win.change_property(atoms["TYPE"], Xatom.ATOM, 32, [atoms["DESKTOP"]])
        win.change_property(atoms["STATE"], Xatom.ATOM, 32, [
            atoms["BELOW"], atoms["STICKY"], atoms["SKIP_P"], atoms["SKIP_T"],
        ])
        win.change_property(atoms["DESKTOP_ID"], Xatom.CARDINAL, 32, [0xFFFFFFFF])
        win.change_property(atoms["NAME"], Xatom.STRING, 8, b"WallpaperDinamicos")

        win.map()
        self._display.sync()
        time.sleep(0.3)

        our_frame = win
        try:
            p = win.query_tree().parent
            if p and p.id != self._root.id:
                our_frame = p
        except Exception:
            pass

        desktop_win = self._find_desktop_window()
        if desktop_win:
            try:
                win.reparent(desktop_win, 0, 0)
                self._display.sync()
                self._window = win
                return
            except Exception:
                pass

        if not desktop_win:
            try:
                our_frame.configure(stack_mode=X.Below)
                self._display.sync()
            except Exception:
                pass
            self._window = win
            return

        try:
            desk_frame = desktop_win
            while True:
                p = desk_frame.query_tree().parent
                if not p or p.id == self._root.id:
                    break
                desk_frame = p
        except Exception:
            desk_frame = None

        try:
            if desk_frame and desk_frame.id != our_frame.id:
                restack = self._display.intern_atom("_NET_RESTACK_WINDOW")
                ev = xevent.ClientMessage(
                    display=self._display,
                    window=our_frame,
                    client_type=restack,
                    data=(32, [2, desk_frame.id, 0, 0, 0]),
                )
                mask = X.SubstructureRedirectMask | X.SubstructureNotifyMask
                self._root.send_event(ev, event_mask=mask)
                self._display.sync()
            else:
                our_frame.configure(stack_mode=X.Below)
                self._display.sync()
        except Exception:
            try:
                our_frame.configure(stack_mode=X.Below)
                self._display.sync()
            except Exception:
                pass

        self._window = win

    def _wait_ipc(self, timeout=3.0):
        start = time.time()
        while time.time() - start < timeout:
            sock = None
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect(self._ipc_socket)
                sock.close()
                self._ipc_ready = True
                return True
            except Exception:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                time.sleep(0.1)
        return False

    def _send_ipc_command(self, command):
        payload = json.dumps({"command": command}) + "\n"
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(self._ipc_socket)
            sock.sendall(payload.encode())
            sock.close()
            self._ipc_ready = True
            return True
        except Exception as e:
            print(f"IPC error: {e}")
            return False

    def start(self, video_path, fps=None, **kwargs):
        if not os.path.isfile(video_path):
            print(f"Video no encontrado: {video_path}")
            return False

        if self.is_running:
            self._filters["playback_mode"] = kwargs.get("playback_mode", self._filters.get("playback_mode", "fill"))
            self._filters["muted"] = kwargs.get("muted", self._filters.get("muted", True))
            if self._playlist_advance(video_path):
                return True

        self._stop_mpv()

        if not self._window:
            if not self._display:
                from Xlib import display as xdisplay
                self._display = xdisplay.Display()
                self._screen = self._display.screen()
                self._root = self._screen.root
            self._setup_window()
        if not self._window:
            print("No se pudo crear la ventana")
            return False

        IPC_SOCKET.parent.mkdir(parents=True, exist_ok=True)
        if IPC_SOCKET.exists():
            IPC_SOCKET.unlink()

        window_id = self._window.id
        volume = self._filters.get("volume", 50)
        muted = self._filters.get("muted", True)
        mode = self._filters.get("playback_mode", "fill")
        blur = self._filters.get("blur", 0)
        gpu = _detect_gpu()
        if gpu not in self._filters:
            self._filters["gpu"] = gpu

        cmd = [
            "mpv",
            f"--wid={window_id}",
            "--loop=inf",
            "--no-border",
            "--no-osc",
            "--no-osd-bar",
            "--no-input-default-bindings",
            "--no-terminal",
            "--stop-screensaver=no",
            "--hwdec=auto",
            "--vo=gpu-next",
            f"--gpu-api={'vulkan' if gpu == 'nvidia' else 'auto'}",
            f"--mute={'yes' if muted else 'no'}",
            f"--volume={volume}",
            f"--input-ipc-server={self._ipc_socket}",
        ]

        mode_args = _mode_to_cmd_args(mode)
        cmd.extend(mode_args)

        if blur > 0:
            cmd.append(f"--vf=boxblur={blur}:{blur}")

        cmd.append(video_path)

        try:
            self._mpv_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            self._wait_ipc(timeout=3.0)
            self._apply_initial_filters()
            self._current_video = video_path
            self._is_paused = False
            self._is_muted = muted
            return True
        except Exception as e:
            print(f"Error al iniciar mpv: {e}")
            return False

    def _playlist_advance(self, video_path):
        was_muted = self._is_muted
        try:
            self._send_ipc_command(["loadfile", video_path, "replace"])
            self._send_ipc_command(["set_property", "loop", "inf"])
            b = self._filters.get("brightness", 100)
            c = self._filters.get("contrast", 100)
            if b != 100:
                self._send_ipc_command(["set_property", "brightness", b - 100])
            if c != 100:
                self._send_ipc_command(["set_property", "contrast", c - 100])
            bl = self._filters.get("blur", 0)
            if bl > 0:
                self._send_ipc_command(["set_property", "vf", f"boxblur={bl}:{bl}"])
            else:
                self._send_ipc_command(["set_property", "vf", ""])
            self._current_video = video_path
            self._is_paused = False
            self._is_muted = was_muted
            return True
        except Exception:
            return False

    def _apply_initial_filters(self):
        brightness = self._filters.get("brightness", 100)
        contrast = self._filters.get("contrast", 100)
        if brightness != 100:
            self._send_ipc_command(["set_property", "brightness", brightness - 100])
        if contrast != 100:
            self._send_ipc_command(["set_property", "contrast", contrast - 100])

    def _stop_mpv(self):
        if self._mpv_process:
            self._send_ipc_command(["quit"])
            try:
                self._mpv_process.wait(timeout=3)
            except Exception:
                try:
                    os.killpg(os.getpgid(self._mpv_process.pid), signal.SIGKILL)
                except Exception:
                    pass
            self._mpv_process = None
        self._ipc_ready = False

    def stop(self):
        self._stop_mpv()
        self._current_video = None
        self._is_paused = False

    def _destroy_window(self):
        if self._window:
            try:
                self._window.destroy()
                self._display.sync()
            except Exception:
                pass
            self._window = None

    def cleanup(self):
        self.stop()
        self._destroy_window()
        if self._display:
            self._display.close()
            self._display = None

    def pause(self, force=None):
        if not self.is_running:
            return
        if force is not None:
            self._send_ipc_command(["set_property", "pause", bool(force)])
            self._is_paused = bool(force)
        else:
            self._send_ipc_command(["cycle", "pause"])
            self._is_paused = not self._is_paused

    def set_pause(self, paused):
        self.pause(force=paused)

    def set_mute(self, muted):
        self._is_muted = muted
        if self.is_running:
            self._send_ipc_command(["set_property", "mute", muted])

    def set_volume(self, volume):
        if self.is_running:
            self._send_ipc_command(["set_property", "volume", volume])
            if volume > 0 and self._is_muted:
                self._is_muted = False
                self._send_ipc_command(["set_property", "mute", False])

    def set_brightness(self, val):
        self._filters["brightness"] = val
        if self.is_running:
            self._send_ipc_command(["set_property", "brightness", val - 100])

    def set_contrast(self, val):
        self._filters["contrast"] = val
        if self.is_running:
            self._send_ipc_command(["set_property", "contrast", val - 100])

    def set_blur(self, val):
        self._filters["blur"] = val
        if self.is_running:
            if val > 0:
                self._send_ipc_command(["set_property", "vf", f"boxblur={val}:{val}"])
            else:
                self._send_ipc_command(["set_property", "vf", ""])
                self._send_ipc_command(["vf", "clr"])

    def set_playback_mode(self, mode):
        self._filters["playback_mode"] = mode
        props = PLAYBACK_MODES.get(mode, PLAYBACK_MODES["fill"])
        if not self.is_running:
            return
        self._send_ipc_command(["set_property", "keepaspect", props.get("keepaspect", True)])
        self._send_ipc_command(["set_property", "panscan", props.get("panscan", 0.0)])
        for key in ("video-align-x", "video-align-y"):
            if key in props:
                self._send_ipc_command(["set_property", key, props[key]])

    def set_speed(self, speed):
        self._filters["speed"] = speed
        if self.is_running:
            self._send_ipc_command(["set_property", "speed", speed])

    def update_filters(self, filters):
        for k, v in filters.items():
            if k == "brightness":
                self.set_brightness(v)
            elif k == "contrast":
                self.set_contrast(v)
            elif k == "blur":
                self.set_blur(v)
            elif k == "playback_mode":
                self.set_playback_mode(v)
            else:
                self._filters[k] = v

    @property
    def is_running(self):
        return self._mpv_process is not None and self._mpv_process.poll() is None

    @property
    def is_paused(self):
        return self._is_paused

    @property
    def current_video(self):
        return self._current_video

    @property
    def available(self):
        return self._available

    @property
    def mode(self):
        return "video"

    def hide(self):
        if self._window:
            try:
                self._window.unmap()
                self._display.sync()
            except Exception:
                pass

    def show(self):
        if self._window:
            try:
                self._window.map()
                self._display.sync()
            except Exception:
                pass


DE_SCHEMAS = {
    "deepin": {
        "type": "gsettings_uri_list",
        "schema": "com.deepin.dde.appearance",
        "key": "background-uris",
        "dbus": True,
    },
    "gnome": {
        "type": "gsettings_string",
        "schema": "org.gnome.desktop.background",
        "key": "picture-uri",
    },
    "kde": {
        "type": "command",
        "command": ["plasma-apply-wallpaperimage"],
    },
    "xfce": {
        "type": "xfconf",
        "channel": "xfce4-desktop",
        "property": "/backdrop/screen0/monitor0/workspace0/last-image",
    },
    "cinnamon": {
        "type": "gsettings_string",
        "schema": "org.cinnamon.desktop.background",
        "key": "picture-uri",
    },
}


class FrameWallpaperEngine:
    MAX_FRAMES = 2000

    def __init__(self, desktop="unknown"):
        self._desktop = desktop if desktop in DE_SCHEMAS else "deepin"
        self._de_config = DE_SCHEMAS[self._desktop]
        self._running = False
        self._last_uri = None
        self._ffmpeg_proc = None
        self._ffmpeg_checker = None
        self._on_complete = None
        self._frame_dir = Path(tempfile.gettempdir()) / "wp-dinamicos-frames"
        self._current_path = Path(tempfile.gettempdir()) / "wp-dinamicos" / "current.jpg"
        self._current_path.parent.mkdir(parents=True, exist_ok=True)
        self._frames = []
        self._original_wallpaper = None
        self._current_video = None
        self._fps = 5
        self._frame_counter = 1

    def start(self, video_path, fps=60, on_complete=None):
        self.stop()
        if not os.path.isfile(video_path):
            return False

        self._fps = fps
        self._current_video = video_path
        self._frame_counter = 1
        self._on_complete = on_complete
        self._save_wallpaper()
        self._frame_dir.mkdir(parents=True, exist_ok=True)
        for f in self._frame_dir.iterdir():
            f.unlink(missing_ok=True)

        output_pattern = str(self._frame_dir / "frame_%d.jpg")
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vf", f"fps={fps}",
            "-q:v", "5",
            "-y", output_pattern,
        ]
        try:
            self._ffmpeg_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return False

        from PyQt6.QtCore import QTimer
        self._ffmpeg_checker = QTimer()
        self._ffmpeg_checker.timeout.connect(self._on_ffmpeg_check)
        self._ffmpeg_checker.start(50)
        return True

    def _tick(self):
        if not self._running or not self._frames:
            return
        try:
            idx = self._frame_counter % len(self._frames)
            self._set_wallpaper(self._frames[idx])
            self._frame_counter += 1
        except Exception:
            pass
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(int(1000 / self._fps), self._tick)
        except Exception:
            pass

    def _on_ffmpeg_check(self):
        done = self._ffmpeg_proc and self._ffmpeg_proc.poll() is not None
        if done:
            try:
                self._ffmpeg_proc.wait(timeout=5)
            except Exception:
                self._ffmpeg_proc.kill()
                self._ffmpeg_proc.wait()
            self._ffmpeg_proc = None
            if self._ffmpeg_checker:
                self._ffmpeg_checker.stop()
                self._ffmpeg_checker = None
            if not self._running:
                current = sorted(
                    self._frame_dir.glob("frame_*.jpg"),
                    key=lambda p: int(p.stem.split("_")[1]),
                )
                if current:
                    if len(current) > self.MAX_FRAMES:
                        keep = current[::len(current) // self.MAX_FRAMES + 1]
                        for old in current:
                            if old not in keep:
                                old.unlink(missing_ok=True)
                        current = keep
                    self._frames = current
                    self._frame_counter = 0
                    self._running = True
                    self._set_wallpaper(current[0])
                    self._tick()
            if self._on_complete:
                self._on_complete()
            return

        if not self._running:
            current = sorted(
                self._frame_dir.glob("frame_*.jpg"),
                key=lambda p: int(p.stem.split("_")[1]),
            )
            if not current:
                return
            if len(current) > self.MAX_FRAMES:
                keep = current[::len(current) // self.MAX_FRAMES + 1]
                for old in current:
                    if old not in keep:
                        old.unlink(missing_ok=True)
                current = keep
            self._frames = current
            self._frame_counter = 0
            self._running = True
            self._set_wallpaper(current[0])
            self._tick()
            return

        existing = {f.name for f in self._frames}
        available = sorted(
            self._frame_dir.glob("frame_*.jpg"),
            key=lambda p: int(p.stem.split("_")[1]),
        )
        for f in available:
            if f.name not in existing:
                self._frames.append(f)

    def set_fps(self, fps):
        self._fps = max(1, min(fps, 180))

    def _set_wallpaper(self, path):
        try:
            shutil.copy2(path, self._current_path)
        except Exception:
            pass
        uri = f"file://{path}"
        if uri == self._last_uri:
            return
        self._last_uri = uri

        kind = self._de_config["type"]
        try:
            if kind == "gsettings_uri_list":
                subprocess.run(
                    ["gsettings", "set", self._de_config["schema"],
                     self._de_config["key"], f"['{uri}']"],
                    capture_output=True, timeout=1,
                )
                if self._de_config.get("dbus"):
                    subprocess.run(
                        ["dbus-send", "--session",
                         "--dest=org.deepin.dde.Appearance1",
                         "--type=method_call", "--print-reply",
                         "/org/deepin/dde/Appearance1",
                         "org.deepin.dde.Appearance1.SetCurrentWorkspaceBackground",
                         f"string:{uri}"],
                        capture_output=True, timeout=1,
                    )
            elif kind == "gsettings_string":
                subprocess.run(
                    ["gsettings", "set", self._de_config["schema"],
                     self._de_config["key"], uri],
                    capture_output=True, timeout=1,
                )
            elif kind == "command":
                cmd = list(self._de_config["command"]) + [str(path)]
                subprocess.run(cmd, capture_output=True, timeout=2)
            elif kind == "xfconf":
                subprocess.run(
                    ["xfconf-query", "-c", self._de_config["channel"],
                     "-p", self._de_config["property"], "-s", str(path)],
                    capture_output=True, timeout=1,
                )
        except Exception:
            pass

    def stop(self, skip_restore=False):
        self._running = False
        self._last_uri = None
        if self._ffmpeg_checker:
            self._ffmpeg_checker.stop()
            self._ffmpeg_checker = None
        if self._ffmpeg_proc:
            self._ffmpeg_proc.terminate()
            try:
                self._ffmpeg_proc.wait(timeout=3)
            except Exception:
                try:
                    self._ffmpeg_proc.kill()
                except Exception:
                    pass
            self._ffmpeg_proc = None
        if not skip_restore:
            self._restore_wallpaper()

    def cleanup(self, skip_restore=False):
        self.stop(skip_restore=skip_restore)
        try:
            shutil.rmtree(self._frame_dir, ignore_errors=True)
        except Exception:
            pass

    def _save_wallpaper(self):
        kind = self._de_config["type"]
        try:
            if kind == "gsettings_uri_list":
                r = subprocess.run(
                    ["gsettings", "get", self._de_config["schema"],
                     self._de_config["key"]],
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    val = r.stdout.strip()
                    if not val.startswith("@as"):
                        self._original_wallpaper = val
            elif kind == "gsettings_string":
                r = subprocess.run(
                    ["gsettings", "get", self._de_config["schema"],
                     self._de_config["key"]],
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    val = r.stdout.strip().strip("'\"")
                    if val and not val.startswith("@"):
                        self._original_wallpaper = val
            elif kind == "xfconf":
                r = subprocess.run(
                    ["xfconf-query", "-c", self._de_config["channel"],
                     "-p", self._de_config["property"]],
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    val = r.stdout.strip()
                    if val:
                        self._original_wallpaper = val
        except Exception:
            pass

    def _restore_wallpaper(self):
        if not self._original_wallpaper:
            return
        uri = self._original_wallpaper.strip("[]").strip("'\"")
        kind = self._de_config["type"]
        try:
            if kind == "gsettings_uri_list":
                try:
                    subprocess.run(
                        ["gsettings", "set", self._de_config["schema"],
                         self._de_config["key"], f"['{uri}']"],
                        capture_output=True, timeout=1,
                    )
                except Exception:
                    pass
                if self._de_config.get("dbus"):
                    try:
                        subprocess.run(
                            ["dbus-send", "--session",
                             "--dest=org.deepin.dde.Appearance1",
                             "--type=method_call", "--print-reply",
                             "/org/deepin/dde/Appearance1",
                             "org.deepin.dde.Appearance1.SetCurrentWorkspaceBackground",
                             f"string:{uri}"],
                            capture_output=True, timeout=1,
                        )
                    except Exception:
                        pass
            elif kind == "gsettings_string":
                subprocess.run(
                    ["gsettings", "set", self._de_config["schema"],
                     self._de_config["key"], uri],
                    capture_output=True, timeout=1,
                )
            elif kind == "xfconf":
                subprocess.run(
                    ["xfconf-query", "-c", self._de_config["channel"],
                     "-p", self._de_config["property"], "-s", uri],
                    capture_output=True, timeout=1,
                )
        except Exception:
            pass
        self._original_wallpaper = None

    @property
    def is_running(self):
        return self._running

    @property
    def current_video(self):
        return self._current_video

    @property
    def is_paused(self):
        return False

    @property
    def mode(self):
        return "frame"

    @property
    def desktop(self):
        return self._desktop

    def pause(self):
        pass

    def set_mute(self, muted):
        pass

    def set_volume(self, volume):
        pass

    def set_brightness(self, val):
        pass

    def set_contrast(self, val):
        pass

    def set_blur(self, val):
        pass

    def update_filters(self, filters):
        pass
