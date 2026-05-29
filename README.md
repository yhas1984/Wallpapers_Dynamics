# Wallpapers Dynamics

Reproductor de video como fondo de pantalla animado para Linux. Compatible con X11 y Wayland.

![Wallpaper Dinamicos](screenshot.jpg)
![Wallpaper Dinamicos - Panel](screenshot1.jpg)

## Características

- **Video como wallpaper** — reproduce videos MP4, WebM, MKV, AVI, MOV como fondo de escritorio real
- **Dos modos de reproducción**: mpv embebido (X11, fluido) o extracción de frames vía D-Bus (X11/Wayland, compatible con iconos del escritorio)
- **Filtros en vivo** — brillo, contraste, blur (vía mpv IPC, sin reiniciar). Cambiar blur ya no pierde brillo/contraste
- **Modos de reproducción** — Fill, Fit, Stretch, Center
- **Playlist** — lista de reproducción con auto-avance configurable (5s–3600s)
- **FPS configurables** — 10–180 fps para el modo iconos
- **Volumen** — control deslizante con mute automático
- **Atajos de teclado** — Ctrl+O (abrir), Espacio (pausa), Ctrl+Q (salir), Ctrl+←/→ (anterior/siguiente), Ctrl+M (silencio)
- **Drag & Drop** — arrastra videos directamente a la ventana
- **Inicio minimizado** — arranca en la bandeja del sistema por defecto
- **Persistencia** — guarda configuración, geometría de ventana, playlist y último video
- **Tema adaptable** — detecta modo oscuro/claro del sistema y ajusta colores vía QSS (PyQt6)
- **Interfaz moderna** — bordes redondeados, hover effects, sliders personalizados, scrollbar estilizado
- **Cross-desktop** — Deepin, KDE, GNOME, XFCE, Cinnamon y más
- **No inhibe suspensión** — el sistema puede suspender normalmente mientras se reproduce el video
- **D-Bus nativo** — usa python-dbus en lugar de subprocess, hasta 100x más rápido en modo iconos
- **Auto-inicio** — opción para iniciar con la sesión
- **Ejecutable standalone** — compilable con PyInstaller

## Modos de funcionamiento

### Modo normal (sin iconos)
Usa mpv directamente incrustado en una ventana X11 del escritorio. Video fluido a fps nativos, con filtros, audio y controles completos. Los iconos del escritorio quedan debajo de la ventana de video. Solo X11.

### Modo iconos (experimental, Deepin)
Extrae frames del video con ffmpeg y los muestra como fondo de escritorio vía D-Bus de Deepin (`org.deepin.dde.Appearance1.SetCurrentWorkspaceBackground`). Los iconos del escritorio quedan visibles encima. Sin audio, sin pausa, sin filtros — solo el video como fondo animado. FPS configurables (10–180). Compatible con **X11 y Wayland**.

## Requisitos

- **Sistema**: Linux con X11 o Wayland
- **Python**: 3.9+
- **Dependencias del sistema**:

```bash
# Debian/Ubuntu/Deepin
sudo apt install mpv ffmpeg libnotify-bin python3-pyqt6 python3-xlib python3-dbus

# Arch
sudo pacman -S mpv ffmpeg libnotify python-pyqt6 python-xlib python-dbus

# Fedora
sudo dnf install mpv ffmpeg libnotify python3-qt6 python3-xlib python3-dbus
```

## Instalación

```bash
git clone https://github.com/yhas1984/Wallpapers_Dynamics.git
cd Wallpapers_Dynamics
pip install -r requirements.txt --break-system-packages
```

## Uso

```bash
python3 run.py
```

La aplicación inicia minimizada en la bandeja del sistema. Haz doble clic en el icono para abrir el panel.
Arrastra un video a la ventana o haz clic en "Seleccionar" para elegir uno. El video se mostrará como fondo de escritorio al instante.

Para cerrar al system tray, solo cierra la ventana (clic en el icono de la bandeja para reabrir).

Para iniciar con la ventana visible, edita `~/.config/wallpaper-dinamicos/config.json` y cambia `start_minimized` a `false`.

### Ejecutable standalone

```bash
pyinstaller wallpaper-dinamicos.spec --noconfirm
./dist/wallpaper-dinamicos
```

## Estructura del proyecto

```
├── run.py                      # Punto de entrada
├── requirements.txt            # Dependencias Python
├── wallpaper-dinamicos.spec    # Configuración de PyInstaller
├── screenshot.jpg              # Captura de pantalla
├── src/
│   ├── __init__.py             # Configuración persistente (JSON)
│   ├── detector.py             # Detección de escritorio/display/tema
│   ├── wallpaper_engine.py     # WallpaperEngine (mpv) + FrameWallpaperEngine (D-Bus)
│   ├── tray_app.py             # GUI (PyQt6), bandeja, playlist, QSS
│   ├── utils.py                # Metadatos de video, notificaciones, thumbnail
│   └── icons.py                # Iconos vectoriales programáticos
└── samples/                    # Videos de ejemplo
```

## Configuración

El archivo de configuración se guarda en `~/.config/wallpaper-dinamicos/config.json`. Se puede editar manualmente o desde la GUI.

| Clave | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `last_video` | string | `""` | Último video reproducido |
| `muted` | bool | `true` | Silencio al iniciar |
| `volume` | int | `50` | Volumen (0–100) |
| `brightness` | int | `100` | Brillo (0–200) |
| `contrast` | int | `100` | Contraste (0–200) |
| `saturation` | int | `100` | Saturación (0–200) |
| `blur` | int | `0` | Desenfoque (0–20) |
| `playback_mode` | string | `"fill"` | Modo: fill/fit/stretch/center |
| `playlist` | array | `[]` | Lista de rutas de video |
| `auto_advance` | bool | `false` | Avance automático |
| `auto_advance_seconds` | int | `30` | Intervalo de avance (5–3600) |
| `autostart` | bool | `false` | Iniciar con la sesión |
| `show_icons` | bool | `false` | Modo iconos (Deepin) |
| `frame_fps` | int | `30` | FPS del modo iconos (10–180) |
| `start_minimized` | bool | `true` | Iniciar minimizado en la bandeja |

## Solución de problemas

**El video no se muestra como fondo:**
- Verifica que estás en X11 (`echo $XDG_SESSION_TYPE`)
- Ejecuta desde terminal para ver errores: `python3 run.py`
- Asegúrate de que mpv esté instalado: `mpv --version`

**La laptop no entra en suspensión:**
- Verifica que la opción `--stop-screensaver=no` esté activa en mpv (configurado por defecto en v1.2+)

**Los iconos del escritorio no se ven (modo iconos):**
- Verifica que estés en Deepin V23+ con dde-shell
- Prueba subir los FPS si el video se ve entrecortado

**La app no se restaura desde la bandeja:**
- En Deepin, haz clic simple en el icono de la bandeja (no doble clic)

**Error "cannot connect to X server":**
- Ejecuta la app desde una sesión gráfica, no desde SSH sin `-X`. En Wayland no aplica.

**Error de import PyQt6:**
- Instala PyQt6: `sudo apt install python3-pyqt6` o `pip install PyQt6`

## Licencia

MIT
