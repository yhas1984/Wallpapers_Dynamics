# Wallpapers Dynamics

Reproductor de video como fondo de pantalla animado para Linux. Funciona en Deepin, KDE Plasma, GNOME, XFCE y otros entornos de escritorio X11.

## Características

- **Video como wallpaper** — reproduce videos MP4, WebM, MKV, AVI, MOV como fondo de escritorio real
- **Modo iconos (Deepin)** — extrae frames del video y los muestra vía D-Bus (`SetCurrentWorkspaceBackground`), permitiendo que los iconos del escritorio sean visibles encima
- **Bandeja del sistema** — control mínimo desde la bandeja, GUI completa al hacer clic
- **Playlist** — lista de reproducción con auto-avance configurable (5s–3600s)
- **Modos de reproducción** — Fill, Fit, Stretch, Center
- **Filtros en vivo** — brillo, contraste, blur (vía mpv IPC, sin reiniciar)
- **FPS configurables** — 10–180 fps para el modo iconos
- **Volumen** — control deslizante con mute automático
- **Atajos de teclado** — Ctrl+O (abrir), Espacio (pausa), Ctrl+Q (salir), Ctrl+←/→ (anterior/siguiente), Ctrl+M (silencio)
- **Drag & Drop** — arrastra videos directamente a la ventana
- **Persistencia** — guarda configuración, geometría de ventana, playlist y último video
- **Tema adaptable** — detecta modo oscuro/claro del sistema y ajusta colores
- **Cross-desktop** — Deepin, KDE, GNOME, XFCE, Cinnamon y más
- **Auto-inicio** — opción para iniciar con la sesión

## Modos de funcionamiento

### Modo normal (sin iconos)
Usa mpv directamente incrustado en una ventana X11 del escritorio. Video fluido a fps nativos, con filtros, audio y controles completos. Los iconos del escritorio quedan debajo de la ventana de video.

### Modo iconos (experimental, solo Deepin)
Extrae frames del video con ffmpeg y los muestra como fondo de escritorio vía D-Bus de Deepin (`org.deepin.dde.Appearance1.SetCurrentWorkspaceBackground`). Los iconos del escritorio quedan visibles encima. Sin audio, sin pausa, sin filtros — solo el video como fondo animado. FPS configurables (10–180).

## Requisitos

- **Sistema**: Linux con X11 (Wayland no soportado aún)
- **Python**: 3.9+
- **Dependencias del sistema**:

```bash
# Debian/Ubuntu/Deepin
sudo apt install mpv ffmpeg libnotify-bin python3-pyqt5 python3-xlib

# Arch
sudo pacman -S mpv ffmpeg libnotify python-pyqt5 python-xlib

# Fedora
sudo dnf install mpv ffmpeg libnotify python3-qt5 python3-xlib
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

Arrastra un video a la ventana o haz clic en "Seleccionar" para elegir uno. El video se mostrará como fondo de escritorio al instante.

Para cerrar al system tray, solo cierra la ventana (clic en el icono de la bandeja para reabrir).

### Ejecutable standalone

También se puede generar un ejecutable independiente:

```bash
pyinstaller --onefile --name "wallpaper-dinamicos" --windowed run.py
./dist/wallpaper-dinamicos
```

## Estructura del proyecto

```
├── run.py                      # Punto de entrada
├── requirements.txt            # Dependencias Python
├── src/
│   ├── __init__.py             # Configuración persistente (JSON)
│   ├── detector.py             # Detección de escritorio/display/tema
│   ├── wallpaper_engine.py     # Motor X11 (mpv) + FrameWallpaperEngine (D-Bus)
│   ├── tray_app.py             # GUI (PyQt5), bandeja, playlist
│   ├── utils.py                # Metadatos de video, notificaciones
│   └── icons.py                # Iconos generados programáticamente
└── .gitignore
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
| `blur` | int | `0` | Desenfoque (0–20) |
| `playback_mode` | string | `"fill"` | Modo: fill/fit/stretch/center |
| `playlist` | array | `[]` | Lista de rutas de video |
| `auto_advance` | bool | `false` | Avance automático |
| `auto_advance_seconds` | int | `30` | Intervalo de avance (5–3600) |
| `autostart` | bool | `false` | Iniciar con la sesión |
| `show_icons` | bool | `false` | Modo iconos (Deepin) |
| `frame_fps` | int | `30` | FPS del modo iconos (10–180) |

## Solución de problemas

**El video no se muestra como fondo:**
- Verifica que estás en X11 (`echo $XDG_SESSION_TYPE`)
- Ejecuta desde terminal para ver errores: `python3 run.py`
- Asegúrate de que mpv esté instalado: `mpv --version`

**Los iconos del escritorio no se ven (modo iconos):**
- Verifica que estés en Deepin V23 con dde-shell
- Prueba subir los FPS si el video se ve entrecortado

**La app no se restaura desde la bandeja:**
- En Deepin, haz clic simple en el icono de la bandeja (no doble clic)

**Error "cannot connect to X server":**
- Ejecuta la app desde una sesión gráfica, no desde SSH sin `-X`

## Licencia

MIT
