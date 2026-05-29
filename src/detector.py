import os
import subprocess
import configparser
from pathlib import Path


def detect_environment():
    candidates = [
        os.environ.get("XDG_CURRENT_DESKTOP", ""),
        os.environ.get("DESKTOP_SESSION", ""),
        os.environ.get("GDMSESSION", ""),
    ]
    desktop = "unknown"
    for c in candidates:
        cl = c.lower()
        if "deepin" in cl:
            desktop = "deepin"
            break
        if "kde" in cl or "plasma" in cl or "kwin" in cl:
            desktop = "kde"
            break
        if "gnome" in cl or "pantheon" in cl:
            desktop = "gnome"
            break
        if "xfce" in cl:
            desktop = "xfce"
            break
        if "cinnamon" in cl:
            desktop = "cinnamon"
            break
        if "sway" in cl:
            desktop = "sway"
            break
        if "hyprland" in cl or "hypr" in cl:
            desktop = "hyprland"
            break

    if os.environ.get("WAYLAND_DISPLAY"):
        display_server = "wayland"
        compositor = _detect_wayland_compositor()
    else:
        display_server = "x11"
        compositor = desktop

    dark_mode, accent, bg, fg = _detect_theme(desktop)

    return {
        "desktop": desktop,
        "display_server": display_server,
        "compositor": compositor,
        "dark_mode": dark_mode,
        "accent_color": accent,
        "bg_color": bg,
        "fg_color": fg,
    }


def _detect_wayland_compositor():
    wm = os.environ.get("XDG_SESSION_DESKTOP", "").lower()
    if wm:
        return wm
    for var in ("SWAYSOCK", "HYPRLAND_INSTANCE_SIGNATURE", "MUTTER_DEBUG_CONFIG"):
        if os.environ.get(var):
            return var.split("_")[0].lower()
    if os.environ.get("KDE_FULL_SESSION"):
        return "kwin"
    if os.environ.get("GNOME_DESKTOP_SESSION_ID"):
        return "mutter"
    try:
        r = subprocess.run(["loginctl", "show-session", "$(loginctl | grep $(whoami) | awk '{print $1}')"],
                           shell=True, capture_output=True, text=True, timeout=2)
        for line in r.stdout.splitlines():
            if "DesktopName" in line:
                return line.split("=")[1].strip().lower()
    except Exception:
        pass
    return "unknown"


def _detect_theme(desktop):
    dark_mode = False
    accent = "#2ca7f8"
    bg = "#f9fcff"
    fg = "#303030"

    try:
        if desktop == "deepin":
            dark_mode, accent, bg, fg = _deepin_theme()
        elif desktop in ("kde", "plasma"):
            dark_mode, accent, bg, fg = _kde_theme()
        elif desktop in ("gnome", "pantheon"):
            dark_mode, accent, bg, fg = _gnome_theme()
        elif desktop in ("xfce", "cinnamon"):
            dark_mode, accent, bg, fg = _xfce_theme()
        elif desktop in ("sway", "hyprland"):
            dark_mode, accent, bg, fg = _wlroots_theme()
    except Exception:
        pass

    return dark_mode, accent, bg, fg


def _deepin_theme():
    dark_mode = False
    try:
        r = subprocess.run(
            ["gsettings", "get", "com.deepin.dde.appearance", "gtk-theme"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            theme = r.stdout.strip().strip("'\"")
            dark_mode = "dark" in theme.lower()
    except Exception:
        pass

    css_name = "gtk-dark.css" if dark_mode else "gtk.css"
    css_path = f"/usr/share/themes/deepin/gtk-3.0/{css_name}"
    try:
        css = Path(css_path).read_text()
        accent = _css_color(css, "accent_color", "#14364d" if dark_mode else "#2ca7f8")
        bg = _css_color(css, "bg_color", "#1e2329" if dark_mode else "#f9fcff")
        fg = _css_color(css, "fg_color", "#5c616c" if dark_mode else "#303030")
    except Exception:
        accent = "#14364d" if dark_mode else "#2ca7f8"
        bg = "#1e2329" if dark_mode else "#f9fcff"
        fg = "#5c616c" if dark_mode else "#303030"

    return dark_mode, accent, bg, fg


def _css_color(css, name, fallback):
    import re
    m = re.search(rf"@define-color\s+{name}\s+([#\w]+)", css)
    if m:
        val = m.group(1)
        if val.startswith("#"):
            return val
    return fallback


def _kde_theme():
    dark_mode = False
    accent = "#3daee9"
    bg = "#eff0f1"
    fg = "#232629"
    try:
        for name in ("plasmarc", "kdeglobals"):
            p = Path.home() / ".config" / name
            if p.exists():
                cfg = configparser.ConfigParser()
                cfg.read(str(p))
                if cfg.has_section("General"):
                    scheme = cfg["General"].get("ColorScheme", "")
                    if "dark" in scheme.lower():
                        dark_mode = True
                        bg = "#232629"
                        fg = "#eff0f1"
                if cfg.has_section("Colors:Window"):
                    bg_raw = cfg["Colors:Window"].get("BackgroundNormal", "")
                    if bg_raw:
                        bg = _kde_color(bg_raw, bg)
                    fg_raw = cfg["Colors:Window"].get("ForegroundNormal", "")
                    if fg_raw:
                        fg = _kde_color(fg_raw, fg)
                if cfg.has_section("Colors:Selection"):
                    accent_raw = cfg["Colors:Selection"].get("BackgroundNormal", "")
                    if accent_raw:
                        accent = _kde_color(accent_raw, accent)
    except Exception:
        pass
    return dark_mode, accent, bg, fg


def _kde_color(raw, fallback):
    parts = raw.split(",")
    if len(parts) == 3:
        r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
        return f"#{r:02x}{g:02x}{b:02x}"
    return fallback


def _gnome_theme():
    dark_mode = False
    accent = "#3584e4"
    bg = "#ffffff"
    fg = "#2e3436"
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            dark_mode = "dark" in r.stdout.lower()
        if dark_mode:
            bg = "#2e3436"
            fg = "#ffffff"
    except Exception:
        pass
    return dark_mode, accent, bg, fg


def _xfce_theme():
    dark_mode = False
    accent = "#5293e1"
    bg = "#fdf6e3"
    fg = "#073642"
    try:
        r = subprocess.run(
            ["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            dark_mode = "dark" in r.stdout.lower()
            if dark_mode:
                bg = "#073642"
                fg = "#fdf6e3"
    except Exception:
        pass
    return dark_mode, accent, bg, fg


def _wlroots_theme():
    dark_mode = False
    accent = "#7c3aed"
    bg = "#1e1e2e"
    fg = "#cdd6f4"
    try:
        gtk_theme = None
        for ini in ("gtk-3.0/settings.ini", ".gtkrc-2.0"):
            p = Path.home() / ".config" / ini
            if p.exists():
                content = p.read_text()
                if "gtk-theme-name" in content:
                    for line in content.splitlines():
                        if "gtk-theme-name" in line:
                            gtk_theme = line.split("=")[1].strip().lower()
                            dark_mode = "dark" in gtk_theme
        if dark_mode:
            bg = "#1e1e2e"
            fg = "#cdd6f4"
    except Exception:
        pass
    return dark_mode, accent, bg, fg
