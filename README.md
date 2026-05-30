# Wallpapers Dynamics

> **ES:** Reproductor de video como fondo de pantalla animado para Linux. Compatible con X11 y Wayland.  
> **EN:** Animated video wallpaper player for Linux. Compatible with X11 and Wayland.

![Wallpaper Dinamicos](screenshot.jpg)
![Wallpaper Dinamicos - Panel](screenshot1.jpg)

---

## 📦 Descarga rápida / Quick download

**ES:** Descarga el paquete `.deb` desde [GitHub Releases](https://github.com/yhas1984/Wallpapers_Dynamics/releases) e instala:

**EN:** Download the `.deb` package from [GitHub Releases](https://github.com/yhas1984/Wallpapers_Dynamics/releases) and install:

```bash
curl -LO https://github.com/yhas1984/Wallpapers_Dynamics/releases/download/v1.0.1/wallpaper-dinamicos-1.0.1.deb
sudo dpkg -i wallpaper-dinamicos-1.0.1.deb
sudo apt install -f
# Run: wallpaper-dinamicos
```

---

## Características / Features

| ES | EN |
|----|----|
| **Video como wallpaper** — reproduce MP4, WebM, MKV, AVI, MOV como fondo de escritorio | **Video wallpaper** — plays MP4, WebM, MKV, AVI, MOV as desktop background |
| **Dos modos**: mpv embebido (X11, fluido) o frames vía D-Bus (X11/Wayland, con iconos) | **Two modes**: embedded mpv (X11, smooth) or D-Bus frames (X11/Wayland, with icons) |
| **Filtros en vivo**: brillo, contraste, blur (vía IPC mpv, sin reiniciar) | **Live filters**: brightness, contrast, blur (via mpv IPC, no restart) |
| **Playlist** con auto-avance (5s–3600s) | **Playlist** with auto-advance (5s–3600s) |
| **FPS configurables** 10–180 para modo iconos | **Configurable FPS** 10–180 for icon mode |
| **Volumen**, mute, atajos de teclado | **Volume**, mute, keyboard shortcuts |
| **Drag & Drop** de videos | **Drag & Drop** videos |
| **Inicio minimizado** en la bandeja | **Start minimized** to system tray |
| **Tema adaptable** (oscuro/claro) | **Adaptive theme** (dark/light) |
| **Cross-desktop**: Deepin, KDE, GNOME, XFCE, Cinnamon | **Cross-desktop**: Deepin, KDE, GNOME, XFCE, Cinnamon |
| **No inhibe suspensión** del sistema | **Does not prevent** system suspend |
| **Auto-inicio** con la sesión | **Auto-start** with session |
| **PyQt6** con QSS moderno | **PyQt6** with modern QSS |

---

## Modos de funcionamiento / Modes

### Modo normal / Normal mode (no icons)

**ES:** Usa mpv incrustado en una ventana X11. Video fluido a fps nativos, con filtros, audio y controles completos. Los iconos quedan debajo.

**EN:** Uses mpv embedded in an X11 window. Smooth video at native fps, with filters, audio and full controls. Desktop icons are hidden below.

### Modo iconos / Icon mode (experimental, Deepin)

**ES:** Extrae frames con ffmpeg y los muestra vía D-Bus (`SetCurrentWorkspaceBackground`). Los iconos del escritorio quedan visibles. Sin audio/filtros. FPS 10–180. X11 y Wayland.

**EN:** Extracts frames with ffmpeg and displays them via D-Bus (`SetCurrentWorkspaceBackground`). Desktop icons remain visible. No audio/filters. FPS 10–180. X11 and Wayland.

---

## Requisitos / Requirements

- **Sistema/System:** Linux con/with X11 o Wayland
- **Python:** 3.9+

```bash
# Debian/Ubuntu/Deepin
sudo apt install mpv ffmpeg libnotify-bin python3-pyqt6 python3-xlib python3-dbus

# Arch
sudo pacman -S mpv ffmpeg libnotify python-pyqt6 python-xlib python-dbus

# Fedora
sudo dnf install mpv ffmpeg libnotify python3-qt6 python3-xlib python3-dbus
```

---

## Instalación / Installation

### Desde .deb (recomendado / recommended)

```bash
curl -LO https://github.com/yhas1984/Wallpapers_Dynamics/releases/download/v1.0.1/wallpaper-dinamicos-1.0.1.deb
sudo dpkg -i wallpaper-dinamicos-1.0.1.deb
sudo apt install -f
wallpaper-dinamicos
```

### Desde código fuente / From source

```bash
git clone https://github.com/yhas1984/Wallpapers_Dynamics.git
cd Wallpapers_Dynamics
pip install -r requirements.txt --break-system-packages
python3 run.py
```

### Ejecutable standalone / Standalone binary

```bash
pyinstaller wallpaper-dinamicos.spec --noconfirm
./dist/wallpaper-dinamicos
```

---

## Uso / Usage

**ES:** La app inicia minimizada en la bandeja. Haz clic en el icono para abrir. Arrastra un video o haz clic en "Seleccionar". Para cerrar a la bandeja, solo cierra la ventana.

**EN:** The app starts minimized to the system tray. Click the tray icon to open. Drag a video or click "Select". Close the window to minimize to tray.

Para iniciar con la ventana visible / To start with visible window:
```bash
# Editar ~/.config/wallpaper-dinamicos/config.json
# Cambiar "start_minimized": true → false
```

---

## Configuración / Configuration

`~/.config/wallpaper-dinamicos/config.json`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `last_video` | string | `""` | Último video / Last video |
| `muted` | bool | `true` | Silencio / Muted |
| `volume` | int | `50` | Volumen (0–100) |
| `brightness` | int | `100` | Brillo (0–200) |
| `contrast` | int | `100` | Contraste (0–200) |
| `saturation` | int | `100` | Saturación (0–200) |
| `blur` | int | `0` | Desenfoque (0–20) |
| `playback_mode` | string | `"fill"` | Modo: fill/fit/stretch/center |
| `playlist` | array | `[]` | Lista de videos / Video list |
| `auto_advance` | bool | `false` | Avance automático / Auto-advance |
| `auto_advance_seconds` | int | `30` | Intervalo (5–3600) |
| `autostart` | bool | `false` | Iniciar con sesión / Start with session |
| `show_icons` | bool | `false` | Modo iconos (Deepin) |
| `frame_fps` | int | `30` | FPS modo iconos (10–180) |
| `start_minimized` | bool | `true` | Inicio minimizado / Start minimized |

---

## Estructura del proyecto / Project structure

```
├── run.py                      # Entry point
├── requirements.txt            # Python dependencies
├── wallpaper-dinamicos.spec    # PyInstaller config
├── screenshot.jpg / screenshot1.jpg  # Screenshots
├── build-deb/                  # .deb packaging
├── src/
│   ├── __init__.py             # Config (JSON)
│   ├── detector.py             # Desktop/display/theme detection
│   ├── wallpaper_engine.py     # WallpaperEngine (mpv) + FrameWallpaperEngine (D-Bus)
│   ├── tray_app.py             # GUI (PyQt6), tray, playlist, QSS
│   ├── utils.py                # Video metadata, notifications, thumbnails
│   └── icons.py                # Programmatic vector icons
└── samples/                    # Sample videos
```

---

## Solución de problemas / Troubleshooting

| ES | EN |
|----|----|
| **El video no se muestra** → verifica X11 (`echo $XDG_SESSION_TYPE`), ejecuta desde terminal | **Video not showing** → check X11, run from terminal |
| **No suspende** → `--stop-screensaver=no` ya configurado | **System won't suspend** → `--stop-screensaver=no` already set |
| **Iconos no visibles** → Deepin V23+ con dde-shell, subir FPS | **Icons not visible** → Deepin V23+ with dde-shell, increase FPS |
| **No restaura desde bandeja** → clic simple (no doble) en Deepin | **Won't restore from tray** → single click (not double) on Deepin |
| **"cannot connect to X server"** → ejecutar desde sesión gráfica | → run from a graphical session |
| **Error PyQt6** → `sudo apt install python3-pyqt6` | → install PyQt6 system package |

---

## Licencia / License

MIT
