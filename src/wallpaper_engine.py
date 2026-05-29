import subprocess
import os
import signal
import time
import json
import socket
import threading
import shutil
import tempfile
from pathlib import Path
from Xlib import X, display
from Xlib import Xatom
from Xlib.protocol import event as xevent

try:
    import dbus
    _dbus_session = dbus.SessionBus()
except Exception:
    _dbus_session = None

IPC_SOCKET = Path.home() / ".config" / "wallpaper-dinamicos" / "mpv-socket"

PLAYBACK_MODES = {
    "fill": "--panscan=1.0",
    "fit": "--panscan=0.0 --keepaspect=yes",
    "stretch": "--panscan=0.0 --keepaspect=no",
    "center": "--panscan=0.0 --keepaspect=yes --video-align-x=0 --video-align-y=0",
}

GSETTINGS_SCHEMA = "com.deepin.dde.appearance"
GSETTINGS_KEY = "background-uris"


class WallpaperEngine:
    def __init__(self, desktop="unknown"):
        self._desktop = desktop
        self._display = display.Display()
        self._screen = self._display.screen()
        self._root = self._screen.root
        self._window = None
        self._mpv_process = None
        self._current_video = None
        self._filters = {}
        self._ipc_socket = str(IPC_SOCKET)
        self._is_paused = False
        self._is_muted = True
        self._ipc_ready = False
        self._original_wallpaper = None
        self._setup_window()

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
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                sock.connect(self._ipc_socket)
                sock.close()
                self._ipc_ready = True
                return True
            except Exception:
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
        except Exception:
            return False

    def start(self, video_path, fps=None, **kwargs):
        self._stop_mpv()

        if not os.path.isfile(video_path):
            print(f"Video no encontrado: {video_path}")
            return False

        if not self._window:
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
            f"--mute={'yes' if muted else 'no'}",
            f"--volume={volume}",
            f"--input-ipc-server={self._ipc_socket}",
        ]

        mode_args = PLAYBACK_MODES.get(mode, PLAYBACK_MODES["fill"]).split()
        cmd.extend(mode_args)

        if blur > 0:
            cmd.append(f"--vf=lavfi=boxblur={blur}:{blur}")

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

    def pause(self):
        if self.is_running:
            self._send_ipc_command(["cycle", "pause"])
            self._is_paused = not self._is_paused

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
                self._send_ipc_command(["vf", "set", f"lavfi=boxblur={val}:{val}"])
            else:
                self._send_ipc_command(["vf", "clr"])

    def update_filters(self, filters):
        needs_restart = False
        for k, v in filters.items():
            if k == "brightness":
                self.set_brightness(v)
            elif k == "contrast":
                self.set_contrast(v)
            elif k == "blur":
                self.set_blur(v)
            else:
                self._filters[k] = v
                if k == "playback_mode":
                    needs_restart = True
        if needs_restart and self._current_video:
            self.start(self._current_video)

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


class FrameWallpaperEngine:
    MAX_FRAMES = 2000

    def __init__(self):
        self._running = False
        self._timer = None
        self._ffmpeg_proc = None
        self._ffmpeg_checker = None
        self._on_complete = None
        self._frame_dir = Path(tempfile.gettempdir()) / "wp-dinamicos-frames"
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

        first_frame = str(self._frame_dir / "frame_1.jpg")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", video_path, "-vf", f"fps={fps}",
                 "-vframes", "1", "-q:v", "5", first_frame],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass

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
            print(f"Error al iniciar ffmpeg: {e}")
            return False

        from PyQt6.QtCore import QTimer
        self._ffmpeg_checker = QTimer()
        self._ffmpeg_checker.timeout.connect(self._on_ffmpeg_check)
        self._ffmpeg_checker.start(100)

        first = Path(first_frame)
        if first.exists() and first.stat().st_size > 0:
            self._set_wallpaper(first)
            self._frames = [first]
            self._running = True
            try:
                from PyQt6.QtCore import QTimer
                self._timer = QTimer()
                self._timer.timeout.connect(self._update_frame)
                self._timer.start(int(1000 / self._fps))
            except Exception:
                self._timer = None
                self._thread = threading.Thread(target=self._update_loop, daemon=True)
                self._thread.start()
        return True

    def _on_ffmpeg_check(self):
        if self._ffmpeg_proc and self._ffmpeg_proc.poll() is None:
            return
        if self._ffmpeg_checker:
            self._ffmpeg_checker.stop()
            self._ffmpeg_checker = None

        if self._ffmpeg_proc:
            try:
                self._ffmpeg_proc.wait(timeout=5)
            except Exception:
                self._ffmpeg_proc.kill()
                self._ffmpeg_proc.wait()
            self._ffmpeg_proc = None

        all_frames = sorted(
            self._frame_dir.glob("frame_*.jpg"),
            key=lambda p: int(p.stem.split("_")[1]),
        )
        if len(all_frames) > self.MAX_FRAMES:
            keep = all_frames[::len(all_frames) // self.MAX_FRAMES + 1]
            for old in all_frames:
                if old not in keep:
                    old.unlink(missing_ok=True)
            all_frames = keep

        if all_frames:
            self._frames = all_frames
        else:
            print("No se generaron frames")
            return

        if self._on_complete:
            self._on_complete()

    def _update_frame(self):
        if not self._running or not self._frames:
            return
        try:
            idx = self._frame_counter % len(self._frames)
            self._set_wallpaper(self._frames[idx])
            self._frame_counter += 1
        except Exception:
            pass

    def _update_loop(self):
        import time as _time
        interval = 1.0 / self._fps
        total = len(self._frames)
        while self._running and total > 0:
            try:
                idx = self._frame_counter % total
                self._set_wallpaper(self._frames[idx])
                self._frame_counter += 1
            except Exception:
                pass
            _time.sleep(interval)

    def set_fps(self, fps):
        self._fps = max(1, min(fps, 180))
        if self._timer:
            self._timer.setInterval(int(1000 / self._fps))

    def _set_wallpaper(self, path):
        uri = f"file://{path}"
        if _dbus_session:
            try:
                proxy = _dbus_session.get_object(
                    "org.deepin.dde.Appearance1",
                    "/org/deepin/dde/Appearance1"
                )
                iface = dbus.Interface(proxy, "org.deepin.dde.Appearance1")
                iface.SetCurrentWorkspaceBackground(uri)
            except Exception:
                pass
        else:
            try:
                subprocess.run(
                    ["dbus-send", "--session", "--dest=org.deepin.dde.Appearance1",
                     "--type=method_call", "--print-reply",
                     "/org/deepin/dde/Appearance1",
                     "org.deepin.dde.Appearance1.SetCurrentWorkspaceBackground",
                     f"string:{uri}"],
                    capture_output=True, timeout=2,
                )
            except Exception:
                pass

    def stop(self, skip_restore=False):
        self._running = False
        if self._timer:
            self._timer.stop()
            self._timer = None
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
        try:
            r = subprocess.run(
                ["gsettings", "get", GSETTINGS_SCHEMA, GSETTINGS_KEY],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                val = r.stdout.strip()
                if val.startswith("@as"):
                    self._original_wallpaper = None
                else:
                    self._original_wallpaper = val
        except Exception:
            pass

    def _restore_wallpaper(self):
        if self._original_wallpaper:
            uri = self._original_wallpaper.strip("[]").strip("'\"")
            if _dbus_session:
                try:
                    proxy = _dbus_session.get_object(
                        "org.deepin.dde.Appearance1",
                        "/org/deepin/dde/Appearance1"
                    )
                    iface = dbus.Interface(proxy, "org.deepin.dde.Appearance1")
                    iface.SetCurrentWorkspaceBackground(uri)
                except Exception:
                    pass
            else:
                try:
                    subprocess.run(
                        ["dbus-send", "--session", "--dest=org.deepin.dde.Appearance1",
                         "--type=method_call", "--print-reply",
                         "/org/deepin/dde/Appearance1",
                         "org.deepin.dde.Appearance1.SetCurrentWorkspaceBackground",
                         f"string:{uri}"],
                        capture_output=True, timeout=2,
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
