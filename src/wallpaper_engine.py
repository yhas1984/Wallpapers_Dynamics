import subprocess
import os
import signal
import time
import json
import socket
from pathlib import Path
from Xlib import X, display
from Xlib import Xatom
from Xlib.protocol import event as xevent

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
                desk_frame = desktop_win
                while True:
                    p = desk_frame.query_tree().parent
                    if not p or p.id == self._root.id:
                        break
                    desk_frame = p
            except Exception:
                pass

        try:
            if desktop_win and desk_frame and desk_frame.id != our_frame.id:
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
        self._clear_wallpaper()

    def _clear_wallpaper(self):
        if self._desktop == "deepin":
            try:
                r = subprocess.run(
                    ["gsettings", "get", GSETTINGS_SCHEMA, GSETTINGS_KEY],
                    capture_output=True, text=True, timeout=2,
                )
                if r.returncode == 0:
                    self._original_wallpaper = r.stdout.strip()
                subprocess.run(
                    ["gsettings", "set", GSETTINGS_SCHEMA, GSETTINGS_KEY, "@as []"],
                    capture_output=True, timeout=2,
                )
            except Exception:
                pass

    def _restore_wallpaper(self):
        if self._original_wallpaper:
            try:
                subprocess.run(
                    ["gsettings", "set", GSETTINGS_SCHEMA, GSETTINGS_KEY,
                     self._original_wallpaper],
                    capture_output=True, timeout=2,
                )
            except Exception:
                pass
            self._original_wallpaper = None

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
        if not self._ipc_ready:
            return False
        payload = json.dumps({"command": command}) + "\n"
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(self._ipc_socket)
            sock.sendall(payload.encode())
            sock.close()
            return True
        except Exception:
            return False

    def start(self, video_path):
        self._stop_mpv()

        if not os.path.isfile(video_path):
            print(f"Video no encontrado: {video_path}")
            return False

        IPC_SOCKET.parent.mkdir(parents=True, exist_ok=True)
        if IPC_SOCKET.exists():
            IPC_SOCKET.unlink()

        window_id = self._window.id
        volume = self._filters.get("volume", 50)
        muted = self._filters.get("muted", True)
        mode = self._filters.get("playback_mode", "fill")

        cmd = [
            "mpv",
            f"--wid={window_id}",
            "--loop=inf",
            "--no-border",
            "--no-osc",
            "--no-osd-bar",
            "--no-input-default-bindings",
            "--no-terminal",
            f"--mute={'yes' if muted else 'no'}",
            f"--volume={volume}",
            f"--input-ipc-server={self._ipc_socket}",
        ]

        mode_args = PLAYBACK_MODES.get(mode, PLAYBACK_MODES["fill"]).split()
        cmd.extend(mode_args)

        brightness = self._filters.get("brightness", 100)
        contrast = self._filters.get("contrast", 100)
        blur = self._filters.get("blur", 0)

        vf_parts = []
        if blur > 0:
            vf_parts.append(f"boxblur={blur}:{blur}")
        if brightness != 100:
            vf_parts.append(f"eq=brightness={(brightness - 100) / 200:.2f}")
        if contrast != 100:
            vf_parts.append(f"eq=contrast={contrast / 100:.2f}")

        if vf_parts:
            cmd.append(f"--vf=lavfi={'|'.join(vf_parts)}")

        cmd.append(video_path)

        try:
            self._mpv_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid,
            )
            self._wait_ipc(timeout=3.0)
            self._current_video = video_path
            self._is_paused = False
            self._is_muted = muted
            return True
        except Exception as e:
            print(f"Error al iniciar mpv: {e}")
            return False

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

    def cleanup(self):
        self.stop()
        self._restore_wallpaper()
        if self._window:
            try:
                self._window.destroy()
                self._display.sync()
            except Exception:
                pass
            self._window = None
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

    def update_filters(self, filters):
        self._filters = filters
        if self._current_video:
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
