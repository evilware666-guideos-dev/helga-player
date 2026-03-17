#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ==============================================================================
#  Helga-Player
# ==============================================================================
#  Beschreibung:
#      Helga ist ein moderner, vollständig GTK4-basierter Musikplayer mit
#      automatischer Theme-Erkennung, GStreamer-Backend, Cover-Download,
#      Smart-Playlists, Equalizer, Crossfade, Visualizer und umfangreicher
#      Metadaten-Unterstützung.
#
#  Hauptfunktionen:
#      • Automatische Erkennung des System-Themes (Hell/Dunkel)
#      • GStreamer-Backend mit Equalizer, Spectrum-Visualizer & Fade-Control
#      • Unterstützung aller gängigen Audioformate (MP3, OGG, FLAC, AAC, M4A,
#        OPUS, WAV, WMA, APE, ALAC, MP4, WEBM, MKA)
#      • Intelligente Playlists (Most Played, Never Played, Favorites, Genres,
#        Jahrzehnte, Recently Added, uvm.)
#      • Automatischer Cover-Download (MusicBrainz + iTunes)
#      • Metadaten-Reparatur (Mojibake-Fix für fehlerhafte ID3-Tags)
#      • Persistente Konfiguration & Cover-Cache
#      • Lautstärke-Fading (Ein-/Ausblenden) mit wählbaren Kurven
#      • Shuffle, Repeat, History, Rating-System
#
#  Abhängigkeiten:
#      python3-gi, python3-gst-1.0, gstreamer1.0-plugins-base,
#      gstreamer1.0-plugins-good, gstreamer1.0-plugins-ugly,
#      gstreamer1.0-libav
#
#  Autor:    evilware666 & Helga
#  Version:  1.0
#  Lizenz:   MIT
#  Datum:    2026
# ==============================================================================


import sys
import os
import subprocess
import math
import random
import json
import time
import threading
import urllib.request
import urllib.parse
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# ─── Dependency check mit GTK4 Fenster ───────────────────────────────────────

def check_deps_gui():
    missing = []
    checks = [
        ("python3-gi",              "PyGObject (GTK Bindungen)"),
        ("python3-gst-1.0",         "GStreamer Python"),
        ("gstreamer1.0-plugins-base","GStreamer Basis-Plugins"),
        ("gstreamer1.0-plugins-good","GStreamer Good (OGG/FLAC/WAV)"),
        ("gstreamer1.0-plugins-ugly","GStreamer Ugly (MP3)"),
        ("gstreamer1.0-libav",       "GStreamer libav (AAC/M4A/OPUS)"),
    ]
    for pkg, label in checks:
        r = subprocess.run(["dpkg", "-s", pkg], capture_output=True, text=True)
        if r.returncode != 0:
            missing.append((pkg, label))
    if not missing:
        return True

    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk, GLib, Gio

    dialog = Gtk.Window(title="Helga - Fehlende Abhängigkeiten")
    dialog.set_default_size(500, 400)
    dialog.set_modal(True)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    vbox.set_margin_top(20); vbox.set_margin_bottom(20)
    vbox.set_margin_start(20); vbox.set_margin_end(20)
    dialog.set_child(vbox)
    header = Gtk.Label()
    header.set_markup("<span size='large' weight='bold'>Fehlende Systempakete</span>")
    vbox.append(header)
    desc = Gtk.Label()
    desc.set_text("Folgende Pakete werden für Helga benötigt:")
    desc.set_margin_top(10)
    vbox.append(desc)
    scrolled = Gtk.ScrolledWindow(); scrolled.set_vexpand(True); vbox.append(scrolled)
    listbox = Gtk.ListBox(); listbox.set_selection_mode(Gtk.SelectionMode.NONE); scrolled.set_child(listbox)
    for pkg, label in missing:
        row = Gtk.ListBoxRow()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_top(5); hbox.set_margin_bottom(5)
        hbox.set_margin_start(10); hbox.set_margin_end(10)
        pkg_label = Gtk.Label(label=pkg); pkg_label.set_halign(Gtk.Align.START); pkg_label.set_width_chars(20)
        hbox.append(pkg_label)
        desc_label = Gtk.Label(label=label); desc_label.set_halign(Gtk.Align.START); desc_label.set_hexpand(True)
        hbox.append(desc_label)
        row.set_child(hbox); listbox.append(row)
    cmd_frame = Gtk.Frame(); cmd_frame.set_margin_top(10); vbox.append(cmd_frame)
    cmd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    cmd_box.set_margin_top(8); cmd_box.set_margin_bottom(8)
    cmd_box.set_margin_start(8); cmd_box.set_margin_end(8)
    cmd_frame.set_child(cmd_box)
    cmd_label = Gtk.Label(); cmd_label.set_markup("<b>Installationsbefehl:</b>"); cmd_label.set_halign(Gtk.Align.START)
    cmd_box.append(cmd_label)
    cmd_text = Gtk.Entry(); cmd_text.set_text(f"sudo apt install {' '.join(p for p,_ in missing)}")
    cmd_text.set_editable(False); cmd_box.append(cmd_text)
    note = Gtk.Label(); note.set_markup("<i>Nach der Installation bitte Helga neu starten.</i>")
    note.set_margin_top(10); vbox.append(note)
    button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    button_box.set_halign(Gtk.Align.CENTER); button_box.set_margin_top(15); vbox.append(button_box)
    install_btn = Gtk.Button(label="Installieren")
    install_btn.add_css_class("suggested-action")
    install_btn.connect("clicked", lambda b: install_with_sudo(dialog, missing))
    button_box.append(install_btn)
    exit_btn = Gtk.Button(label="Beenden")
    exit_btn.connect("clicked", lambda b: sys.exit(1))
    button_box.append(exit_btn)

    def install_with_sudo(parent, missing_pkgs):
        passwd_dialog = Gtk.Dialog(title="Passwort erforderlich", transient_for=parent)
        passwd_dialog.set_modal(True); passwd_dialog.set_default_size(350, 150)
        content = passwd_dialog.get_content_area()
        content.set_margin_top(20); content.set_margin_bottom(20)
        content.set_margin_start(20); content.set_margin_end(20); content.set_spacing(10)
        info = Gtk.Label(); info.set_markup("Bitte <b>sudo-Passwort</b> für die Installation eingeben:")
        content.append(info)
        passwd_entry = Gtk.PasswordEntry(); passwd_entry.set_placeholder_text("Passwort"); content.append(passwd_entry)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END); btn_box.set_margin_top(10)
        cancel_btn = Gtk.Button(label="Abbrechen"); cancel_btn.connect("clicked", lambda b: passwd_dialog.close())
        btn_box.append(cancel_btn)
        ok_btn = Gtk.Button(label="Installieren"); ok_btn.add_css_class("suggested-action")
        ok_btn.connect("clicked", lambda b: do_install(parent, passwd_dialog, passwd_entry.get_text(), missing_pkgs))
        btn_box.append(ok_btn); content.append(btn_box); passwd_dialog.present()

    def do_install(parent, passwd_dialog, password, missing_pkgs):
        passwd_dialog.close()
        install_win = Gtk.Window(title="Installation läuft...")
        install_win.set_transient_for(parent); install_win.set_modal(True); install_win.set_default_size(400, 200)
        vbox2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox2.set_margin_top(20); vbox2.set_margin_bottom(20)
        vbox2.set_margin_start(20); vbox2.set_margin_end(20)
        install_win.set_child(vbox2)
        spinner = Gtk.Spinner(); spinner.set_size_request(50, 50); spinner.start(); vbox2.append(spinner)
        status_label = Gtk.Label(); status_label.set_markup("<b>Installiere Pakete...</b>"); vbox2.append(status_label)
        progress = Gtk.ProgressBar(); progress.set_show_text(True); progress.set_text("Initialisiere..."); vbox2.append(progress)
        output_view = Gtk.TextView(); output_view.set_editable(False); output_view.set_wrap_mode(Gtk.WrapMode.WORD)
        output_view.set_size_request(-1, 100)
        scrolled2 = Gtk.ScrolledWindow(); scrolled2.set_child(output_view); scrolled2.set_vexpand(True); vbox2.append(scrolled2)
        output_buffer = output_view.get_buffer(); install_win.present()
        def install_thread():
            success = True
            for i, (pkg, label) in enumerate(missing_pkgs):
                GLib.idle_add(progress.set_fraction, i / len(missing_pkgs))
                GLib.idle_add(progress.set_text, f"Installiere {pkg}...")
                cmd = f"echo '{password}' | sudo -S apt install -y {pkg}"
                process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None: break
                    if line: GLib.idle_add(output_buffer.insert, output_buffer.get_end_iter(), line)
                if process.returncode != 0:
                    success = False
                    error = process.stderr.read()
                    GLib.idle_add(output_buffer.insert, output_buffer.get_end_iter(), f"\nFEHLER: {error}")
                    break
            GLib.idle_add(progress.set_fraction, 1.0)
            if success:
                GLib.idle_add(status_label.set_markup, "<b>✅ Installation erfolgreich!</b>")
                GLib.idle_add(progress.set_text, "Fertig!")
                restart_btn = Gtk.Button(label="Helga neu starten")
                restart_btn.add_css_class("suggested-action")
                restart_btn.connect("clicked", lambda b: os.execv(sys.executable, ['python3'] + sys.argv))
                GLib.idle_add(vbox2.append, restart_btn)
            else:
                GLib.idle_add(status_label.set_markup, "<b>❌ Installation fehlgeschlagen!</b>")
        threading.Thread(target=install_thread, daemon=True).start()

    dialog.present()
    from gi.repository import GLib
    context = GLib.main_context_default()
    while dialog.get_visible():
        context.iteration(True)
    return False

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gst", "1.0")
    from gi.repository import Gtk, Gdk, Gst
except ImportError as e:
    print("\n" + "="*60)
    print("FEHLER: GTK4 oder GStreamer ist nicht installiert!")
    print("="*60)
    print(f"\nFehler: {e}")
    sys.exit(1)

if not check_deps_gui():
    sys.exit(1)

import gi
gi.require_version("Gtk",       "4.0")
gi.require_version("Gdk",       "4.0")
gi.require_version("Gst",       "1.0")
gi.require_version("GstPbutils","1.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("Pango",     "1.0")
gi.require_version("PangoCairo","1.0")
from gi.repository import Gtk, Gdk, Gst, GstPbutils, GLib, GdkPixbuf, Pango, PangoCairo, Gio, GObject
import cairo

Gst.init(None)

def _fix_encoding(s):
    """Korrigiert falsch dekodierte Umlaute (Mojibake).
    Unterstützt: Latin-1/CP1252 als UTF-8, UTF-8 als Latin-1."""
    if not s or not isinstance(s, str):
        return s
    # Schnelltest: enthält typische Mojibake-Muster wie Ã, Â, Ã¼, etc.
    if not any(c in s for c in ("Ã", "Â", "", "", "", "", "Ã", "Â")):
        return s  # wahrscheinlich schon korrekt
    # Strategie 1: Latin-1 → UTF-8 (häufigster Fall bei ID3v2.3)
    try:
        fixed = s.encode("latin-1").decode("utf-8")
        if fixed != s and "Ã" not in fixed and "�" not in fixed:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    # Strategie 2: CP1252 → UTF-8 (Windows-Variante)
    try:
        fixed = s.encode("cp1252").decode("utf-8")
        if fixed != s and "Ã" not in fixed and "�" not in fixed:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    # Strategie 3: Bytes direkt als UTF-8 mit errors=replace
    try:
        fixed = s.encode("latin-1").decode("utf-8", errors="replace")
        if "�" not in fixed and fixed != s:
            return fixed
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


SUPPORTED = ('.mp3','.ogg','.flac','.wav','.aac','.m4a',
             '.opus','.wma','.ape','.mp4','.webm','.mka','.alac')

CONFIG_PATH = Path.home() / ".config" / "helga" / "config.json"
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

COVER_CACHE = Path.home() / ".cache" / "helga" / "covers"
COVER_CACHE.mkdir(parents=True, exist_ok=True)

# ─── System-Theme Farben ─────────────────────────────────────────────────────
def get_system_colors():
    try:
        display = Gdk.Display.get_default()
        if display:
            return {
                "bg":       (0.2, 0.2, 0.24),
                "surface":  (0.25, 0.25, 0.3),
                "surface2": (0.3, 0.3, 0.35),
                "accent":   (0.4, 0.6, 0.8),
                "accent2":  (0.6, 0.4, 0.8),
                "text":     (0.95, 0.95, 0.95),
                "muted":    (0.6, 0.6, 0.65),
                "red":      (0.9, 0.3, 0.3),
                "border":   (0.35, 0.35, 0.4),
            }
    except:
        pass
    return {
        "bg":       (0.2, 0.2, 0.24),
        "surface":  (0.25, 0.25, 0.3),
        "surface2": (0.3, 0.3, 0.35),
        "accent":   (0.118, 0.678, 0.957),   # #1eadf4
        "accent2":  (0.06, 0.45, 0.75),       # etwas dunkler für Verläufe
        "text":     (0.95, 0.95, 0.95),
        "muted":    (0.6, 0.6, 0.65),
        "red":      (0.9, 0.3, 0.3),
        "border":   (0.35, 0.35, 0.4),
    }

C = get_system_colors()

# ─── Cover Downloader ────────────────────────────────────────────────────────
class CoverDownloader:
    def __init__(self):
        self.user_agent = "Helga Music Player/1.0"
        self.session = None
        self._setup_session()

    def _setup_session(self):
        try:
            import requests
            self.session = requests.Session()
            self.session.headers.update({'User-Agent': self.user_agent})
            self.requests_available = True
        except ImportError:
            self.requests_available = False

    def search_cover(self, artist, album, track_path):
        if not artist or not album or artist == "Unbekannt" or album == "":
            return None
        cache_key = hashlib.md5(f"{artist}_{album}".encode()).hexdigest()
        cache_file = COVER_CACHE / f"{cache_key}.jpg"
        if cache_file.exists():
            try:
                return GdkPixbuf.Pixbuf.new_from_file(str(cache_file))
            except:
                pass
        if self.requests_available:
            return self._download_with_requests(artist, album, cache_file)
        else:
            return self._download_with_urllib(artist, album, cache_file)

    def _download_with_requests(self, artist, album, cache_file):
        try:
            encoded_artist = urllib.parse.quote(artist)
            encoded_album = urllib.parse.quote(album)
            search_url = f"https://musicbrainz.org/ws/2/release/?query=artist:{encoded_artist}%20AND%20release:{encoded_album}&fmt=json"
            response = self.session.get(search_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('releases') and len(data['releases']) > 0:
                    release_id = data['releases'][0]['id']
                    cover_url = f"https://coverartarchive.org/release/{release_id}/front-500"
                    cover_response = self.session.get(cover_url, timeout=5)
                    if cover_response.status_code == 200:
                        with open(cache_file, 'wb') as f:
                            f.write(cover_response.content)
                        return self._scale_cover(GdkPixbuf.Pixbuf.new_from_file(str(cache_file)))
            itunes_url = f"https://itunes.apple.com/search?term={encoded_artist}+{encoded_album}&entity=album&limit=1"
            response = self.session.get(itunes_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    artwork_url = data['results'][0].get('artworkUrl100', '')
                    if artwork_url:
                        artwork_url = artwork_url.replace('100x100bb.jpg', '600x600bb.jpg').replace('100x100', '600x600')
                        img_response = self.session.get(artwork_url, timeout=5)
                        if img_response.status_code == 200:
                            with open(cache_file, 'wb') as f:
                                f.write(img_response.content)
                            return self._scale_cover(GdkPixbuf.Pixbuf.new_from_file(str(cache_file)))
        except Exception as e:
            print(f"Fehler beim Cover-Download: {e}")
        return None

    def _download_with_urllib(self, artist, album, cache_file):
        try:
            encoded = urllib.parse.quote(f"{artist} {album}")
            url = f"https://itunes.apple.com/search?term={encoded}&entity=album&limit=1"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get('results') and len(data['results']) > 0:
                    artwork_url = data['results'][0].get('artworkUrl100', '')
                    if artwork_url:
                        artwork_url = artwork_url.replace('100x100bb.jpg', '600x600bb.jpg')
                        with urllib.request.urlopen(artwork_url, timeout=5) as img_response:
                            img_data = img_response.read()
                            with open(cache_file, 'wb') as f:
                                f.write(img_data)
                            return self._scale_cover(GdkPixbuf.Pixbuf.new_from_file(str(cache_file)))
        except:
            pass
        return None

    def _scale_cover(self, pixbuf):
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width < 300 or height < 300:
            return None
        if width > 600 or height > 600:
            if width > height:
                new_width = 600; new_height = int(600 * height / width)
            else:
                new_height = 600; new_width = int(600 * width / height)
            return pixbuf.scale_simple(new_width, new_height, GdkPixbuf.InterpType.BILINEAR)
        return pixbuf


# ─── Smart Playlist Generator ─────────────────────────────────────────────────
class SmartPlaylistGenerator:
    def __init__(self, player):
        self.player = player
        self.metadata_cache = {}

    def get_metadata(self, path):
        if path in self.metadata_cache:
            return self.metadata_cache[path]
        try:
            uri = Gst.filename_to_uri(os.path.abspath(path))
            info = GstPbutils.Discoverer.new(5 * Gst.SECOND).discover_uri(uri)
            stream_info = info.get_stream_list()
            tags = None
            for stream in stream_info:
                tags = stream.get_tags()
                if tags: break
            meta = {"title": Path(path).stem, "artist": "Unbekannt", "album": "",
                    "year": "", "genre": "", "duration": info.get_duration() if info.get_duration() > 0 else 0, "path": path}
            if tags:
                for gkey, mkey in [(Gst.TAG_TITLE,"title"),(Gst.TAG_ARTIST,"artist"),
                                    (Gst.TAG_ALBUM,"album"),(Gst.TAG_DATE_TIME,"year"),(Gst.TAG_GENRE,"genre")]:
                    ok, v = tags.get_string(gkey)
                    if ok: meta[mkey] = _fix_encoding(str(v))
            self.metadata_cache[path] = meta
            return meta
        except:
            return None

    def generate_never_played(self, limit=50):
        if not hasattr(self.player, 'parent') or not hasattr(self.player.parent, '_play_count'): return []
        never = [p for p in self.player.playlist if self.player.parent._play_count.get(p, 0) == 0]
        random.shuffle(never); return never[:limit]

    def generate_most_played(self, count=50):
        if not hasattr(self.player, 'parent') or not hasattr(self.player.parent, '_play_count'): return []
        sorted_tracks = sorted([(p, c) for p, c in self.player.parent._play_count.items() if p in self.player.playlist],
                               key=lambda x: x[1], reverse=True)[:count]
        return [p for p, _ in sorted_tracks]

    def generate_least_played(self, count=50):
        if not hasattr(self.player, 'parent') or not hasattr(self.player.parent, '_play_count'): return []
        tracks_with_count = [(p, self.player.parent._play_count.get(p, 0)) for p in self.player.playlist]
        return [p for p, _ in sorted(tracks_with_count, key=lambda x: x[1])[:count]]

    def generate_newest(self, count=50):
        tracks = [(p, os.path.getmtime(p)) for p in self.player.playlist if os.path.exists(p)]
        return [p for p, _ in sorted(tracks, key=lambda x: x[1], reverse=True)[:count]]

    def generate_oldest(self, count=50):
        tracks = [(p, os.path.getmtime(p)) for p in self.player.playlist if os.path.exists(p)]
        return [p for p, _ in sorted(tracks, key=lambda x: x[1])[:count]]

    def generate_recently_added(self, days=30, count=50):
        cutoff = time.time() - (days * 24 * 60 * 60)
        recent = [p for p in self.player.playlist if os.path.exists(p) and os.path.getctime(p) > cutoff]
        recent.sort(key=lambda p: os.path.getctime(p), reverse=True)
        return recent[:count]

    def generate_by_rating(self, min_rating=4):
        if not hasattr(self.player, 'parent') or not hasattr(self.player.parent, '_rating'): return []
        return [p for p in self.player.playlist if self.player.parent._rating.get(p, 0) >= min_rating]

    def generate_by_artist(self, artist):
        return [p for p in self.player.playlist if
                (self.get_metadata(p) or {}).get("artist","").lower() == artist.lower()]

    def generate_by_genre(self, genre):
        return [p for p in self.player.playlist if
                (self.get_metadata(p) or {}).get("genre","").lower() == genre.lower()]

    def generate_by_year(self, year):
        return [p for p in self.player.playlist if
                (self.get_metadata(p) or {}).get("year","").startswith(str(year))]

    def generate_by_decade(self, decade):
        result = []
        for p in self.player.playlist:
            try:
                year = int((self.get_metadata(p) or {}).get("year","")[:4])
                if decade <= year <= decade + 9: result.append(p)
            except: pass
        return result

    def generate_favorites(self, count=50):
        if not hasattr(self.player, 'parent'): return []
        scores = [(p, self.player.parent._rating.get(p,0)*10 + self.player.parent._play_count.get(p,0)/10)
                  for p in self.player.playlist]
        return [p for p, _ in sorted(scores, key=lambda x: x[1], reverse=True)[:count]]

    def generate_random(self, count=20):
        if len(self.player.playlist) <= count: return self.player.playlist.copy()
        return random.sample(self.player.playlist, count)


# ─── Fade Controller ──────────────────────────────────────────────────────────
class FadeController:
    def __init__(self, player, duration=2000):
        self.player = player
        self.duration = duration / 1000.0
        self.fade_active = False
        self.target_vol = 1.0
        self.start_vol = 1.0
        self.fade_start = 0
        self.fade_lock = threading.Lock()
        self.on_fade_complete = None
        self.fade_enabled = True
        self.fade_curve = "linear"

    def set_fade_enabled(self, enabled): self.fade_enabled = enabled
    def set_fade_duration(self, ms): self.duration = ms / 1000.0
    def set_fade_curve(self, curve): self.fade_curve = curve

    def _calc(self, p):
        if self.fade_curve == "smooth": return p * p * (3 - 2 * p)
        elif self.fade_curve == "exponential": return 1 - math.exp(-p * 4) / math.exp(4)
        return p

    def fade_in(self, callback=None):
        desired_vol = self.player.target_vol if hasattr(self.player, 'target_vol') else 1.0
        if not self.fade_enabled:
            self.player.set_vol(desired_vol)
            if callback: GLib.idle_add(callback)
            return
        with self.fade_lock:
            if self.fade_active:
                self.fade_active = False
                time.sleep(0.05)
            self.on_fade_complete = callback
            self.fade_active = True
            self.start_vol = 0.0
            self.target_vol = desired_vol
            self.player.set_vol(0.0)
            self.fade_start = time.time()
        def fade_loop():
            while self.fade_active:
                elapsed = time.time() - self.fade_start
                if elapsed >= self.duration:
                    with self.fade_lock:
                        self.player.set_vol(self.target_vol)
                        self.fade_active = False
                        if self.on_fade_complete: GLib.idle_add(self.on_fade_complete)
                    break
                progress = self._calc(elapsed / self.duration)
                vol = self.start_vol + (self.target_vol - self.start_vol) * progress
                self.player.set_vol(vol)
                time.sleep(0.02)
        threading.Thread(target=fade_loop, daemon=True).start()

    def fade_out(self, callback=None):
        if not self.fade_enabled:
            self.player.set_vol(0.0)
            self.player.pl.set_state(Gst.State.PAUSED)
            if callback: GLib.idle_add(callback)
            return
        with self.fade_lock:
            if self.fade_active: self.fade_active = False; time.sleep(0.1)
            self.on_fade_complete = callback
            self.fade_active = True
            self.start_vol = self.player.pl.get_property('volume')
            self.target_vol = 0.0
            self.fade_start = time.time()
        def fade_loop():
            while self.fade_active:
                elapsed = time.time() - self.fade_start
                if elapsed >= self.duration:
                    with self.fade_lock:
                        self.player.set_vol(0.0)
                        self.player.pl.set_state(Gst.State.PAUSED)
                        self.fade_active = False
                        if self.on_fade_complete: GLib.idle_add(self.on_fade_complete)
                    break
                progress = self._calc(elapsed / self.duration)
                self.player.set_vol(self.start_vol + (self.target_vol - self.start_vol) * progress)
                time.sleep(0.02)
        threading.Thread(target=fade_loop, daemon=True).start()

    def is_fading(self): return self.fade_active


# ─── Metadata ─────────────────────────────────────────────────────────────────
def get_meta(path, cover_downloader=None):
    m = {"title": Path(path).stem, "artist":"Unbekannt",
         "album":"", "year":"", "genre":"", "cover":None, "duration":0}
    try:
        uri = Gst.filename_to_uri(os.path.abspath(path))
        info = GstPbutils.Discoverer.new(5 * Gst.SECOND).discover_uri(uri)
        m["duration"] = info.get_duration() if info.get_duration() > 0 else 0
        stream_info = info.get_stream_list()
        tags = None
        for stream in stream_info:
            tags = stream.get_tags()
            if tags: break
        if tags:
            for gkey, mkey in [(Gst.TAG_TITLE,"title"),(Gst.TAG_ARTIST,"artist"),
                                (Gst.TAG_ALBUM,"album"),(Gst.TAG_DATE_TIME,"year"),(Gst.TAG_GENRE,"genre")]:
                ok, v = tags.get_string(gkey)
                if ok: m[mkey] = _fix_encoding(str(v))
            for itag in (Gst.TAG_IMAGE, Gst.TAG_PREVIEW_IMAGE):
                ok, sample = tags.get_sample(itag)
                if ok and sample:
                    buf = sample.get_buffer()
                    ok2, map_info = buf.map(Gst.MapFlags.READ)
                    if ok2:
                        try:
                            loader = GdkPixbuf.PixbufLoader.new()
                            loader.write(bytes(map_info.data)); loader.close()
                            m["cover"] = loader.get_pixbuf()
                        except: pass
                        buf.unmap(map_info)
                if m["cover"]: break
        if not m["cover"] and cover_downloader and m["artist"] != "Unbekannt" and m["album"]:
            m["cover"] = cover_downloader.search_cover(m["artist"], m["album"], path)
    except Exception as e:
        print(f"Fehler beim Lesen der Metadaten: {e}")
    return m


# ─── Equalizer Manager ───────────────────────────────────────────────────────
# ─── Player backend ───────────────────────────────────────────────────────────
class Player:
    def __init__(self):
        self.pl = Gst.ElementFactory.make("playbin", "player")
        if not self.pl:
            print("FEHLER: Konnte playbin nicht erstellen!")
            return

        self.playlist = []
        self.current = -1
        self.current_pos = 0
        self.shuffle = False
        self.repeat = "none"
        self._hist = []
        self._dur = 0
        self.on_eos = None
        self.on_load = None
        self._eq_element   = None   # wird in _setup_audio_pipeline gesetzt
        self._eq_enabled   = True
        self._eq_preset    = "Flat"
        self.target_vol = 0.8
        self.parent = None
        self._spectrum = None
        self._vis_callback = None
        self._volume_elem = None
        self._muted = False
        self._last_vol = 0.8

        self._setup_audio_pipeline()

        bus = self.pl.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos",           self._eos)
        bus.connect("message::error",         self._err)
        bus.connect("message::element",       self._on_element_msg)
        bus.connect("message::state-changed", self._on_state_changed_msg)


    def _setup_audio_pipeline(self):
        try:
            # Vollständige Pipeline als String — zuverlässigste Methode
            # volume → equalizer-10bands → audioconvert → spectrum → autoaudiosink
            # Sink-Reihenfolge: pulsesink (EQ-kompatibel) → autoaudiosink → alsasink
            sink_name = "autoaudiosink"
            for sn in ["pulsesink", "autoaudiosink", "alsasink"]:
                test = Gst.ElementFactory.make(sn, None)
                if test:
                    sink_name = sn
                    break
            spec_desc = (
                "volume name=helga-volume ! "
                "equalizer-10bands name=helga-eq ! "
                "audioconvert name=helga-convert ! "
                "spectrum name=helga-spectrum bands=48 threshold=-60 "
                f"    interval=33000000 post-messages=true message-magnitude=true ! "
                f"{sink_name} name=helga-sink"
            )
            try:
                bin_ = Gst.parse_bin_from_description(spec_desc, True)
                self.pl.set_property("audio-sink", bin_)
                # Referenzen auf die einzelnen Elemente holen
                self._volume_elem = bin_.get_by_name("helga-volume")
                self._eq_element  = bin_.get_by_name("helga-eq")
                self._spectrum    = bin_.get_by_name("helga-spectrum")
                if self._volume_elem:
                    self._volume_elem.set_property("volume", self.target_vol)
                if self._eq_element:
                    print("Audio-Pipeline mit EQ, volume und Spectrum eingerichtet")
                    return
            except Exception as e:
                print(f"Pipeline-String Fehler: {e}, versuche manuellen Aufbau")

            # Fallback: manueller Aufbau ohne Spectrum
            self._volume_elem = Gst.ElementFactory.make("volume", "helga-volume")
            self._eq_element  = Gst.ElementFactory.make("equalizer-10bands", "helga-eq")
            convert           = Gst.ElementFactory.make("audioconvert", "helga-convert")
            audio_sink        = None
            for name in ["autoaudiosink", "pulsesink", "alsasink"]:
                audio_sink = Gst.ElementFactory.make(name, "helga-sink")
                if audio_sink:
                    print(f"Fallback Audio-Sink: {name}")
                    break
            if not self._volume_elem or not convert or not audio_sink:
                return
            bin2 = Gst.Bin.new("helga-audio-bin")
            elems = [self._volume_elem, convert, audio_sink]
            if self._eq_element:
                elems = [self._volume_elem, self._eq_element, convert, audio_sink]
            for e in elems:
                bin2.add(e)
            for i in range(len(elems)-1):
                if not elems[i].link(elems[i+1]):
                    print(f"Link fehlgeschlagen: {elems[i]} → {elems[i+1]}")
                    return
            ghost = Gst.GhostPad.new("sink", self._volume_elem.get_static_pad("sink"))
            bin2.add_pad(ghost)
            self.pl.set_property("audio-sink", bin2)
            self._volume_elem.set_property("volume", self.target_vol)
            print(f"Fallback Audio-Pipeline eingerichtet {'mit' if self._eq_element else 'ohne'} EQ")

        except Exception as e:
            print(f"Fehler beim Audio-Pipeline Setup: {e}")

    def setup_spectrum(self, vis_callback):
        self._vis_callback = vis_callback

    def set_eq_preset(self, preset_name, gains):
        if not getattr(self, '_eq_element', None): return
        self._eq_preset = preset_name
        props = ["band0","band1","band2","band3","band4",
                 "band5","band6","band7","band8","band9"]
        try:
            for i, g in enumerate(gains[:10]):
                self._eq_element.set_property(props[i], float(g))
            # Readback: prüfen ob Werte wirklich gesetzt wurden
            actual = [round(self._eq_element.get_property(p), 2) for p in props]
            print(f"EQ '{preset_name}' gesetzt: {gains[:4]}... | tatsächlich: {actual[:4]}...")
        except Exception as e:
            print(f"EQ set_preset Fehler: {e}")

    def set_eq_enabled(self, enabled):
        self._eq_enabled = enabled
        if not getattr(self, '_eq_element', None): return
        if not enabled:
            props = ["band0","band1","band2","band3","band4",
                     "band5","band6","band7","band8","band9"]
            try:
                for p in props:
                    self._eq_element.set_property(p, 0.0)
            except Exception as e:
                print(f"EQ disable Fehler: {e}")

    def load(self, idx, resume_pos=0, paused=False):
        if not (0 <= idx < len(self.playlist)): 
            return
        self.current = idx
        self.pl.set_state(Gst.State.NULL)
        self.pl.set_property("uri", Gst.filename_to_uri(os.path.abspath(self.playlist[idx])))
        self.current_pos = resume_pos
        self._load_paused = paused

        GLib.timeout_add(100, self._start_playback)
        self._dur = 0
        if self.on_load: 
            GLib.idle_add(self.on_load, idx)

    def _start_playback(self):
        if getattr(self, "_load_paused", False):
            # Nur in PAUSED laden — kein Ton, aber Position ist bereit
            self.pl.set_state(Gst.State.PAUSED)
            if self.current_pos > 0:
                GLib.timeout_add(200, lambda: self.seek_to_position(self.current_pos))
        else:
            self.pl.set_state(Gst.State.PLAYING)
            if self.current_pos > 0:
                GLib.timeout_add(200, lambda: self.seek_to_position(self.current_pos))
        return False

    def seek_to_position(self, pos_ns):
        if pos_ns > 0:
            self.pl.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, pos_ns)
        return False

    def play_pause(self):
        _, state, _ = self.pl.get_state(0)
        if state == Gst.State.PLAYING:
            self.pl.set_state(Gst.State.PAUSED)
            return False
        else:
            self.pl.set_state(Gst.State.PLAYING)
            return True

    def stop(self): 
        self.pl.set_state(Gst.State.NULL)

    def next(self, auto=False):
        if not self.playlist: 
            return
        if auto and self.repeat == "one":
            self.load(self.current)
            return
        self._hist.append(self.current)
        if self.shuffle:
            n = random.randint(0, len(self.playlist)-1)
            while n == self.current and len(self.playlist) > 1:
                n = random.randint(0, len(self.playlist)-1)
        else:
            n = (self.current + 1) % len(self.playlist)
        if auto and n == 0 and self.repeat == "none":
            self.stop()
            return
        self.load(n)

    def prev(self):
        if not self.playlist: 
            return
        if self.shuffle and self._hist:
            n = self._hist.pop()
        else:
            n = (self.current - 1) % len(self.playlist)
        self.load(n)

    def seek(self, frac):
        dur = self.get_dur()
        if dur > 0:
            self.pl.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, int(frac * dur))

    def get_pos(self):
        try:
            ok, pos = self.pl.query_position(Gst.Format.TIME)
            return pos if ok else 0
        except: 
            return 0

    def get_dur(self):
        try:
            ok, dur = self.pl.query_duration(Gst.Format.TIME)
            if ok and dur > 0: 
                self._dur = dur
            return self._dur
        except: 
            return self._dur

    def set_vol(self, v):
        self.target_vol = max(0.0, min(1.5, v))
        if self._muted:
            self._last_vol = self.target_vol
        else:
            if self._volume_elem:
                try:
                    self._volume_elem.set_property("volume", self.target_vol)
                    return
                except Exception as e:
                    print(f"Volume-Element Fehler: {e}")
            try:
                self.pl.set_property("volume", self.target_vol)
            except:
                pass

    def mute(self):
        self._muted = not self._muted
        if self._muted:
            self._last_vol = self.target_vol
            self.set_vol(0.0)
        else:
            self.set_vol(self._last_vol)
        return self._muted

    def is_muted(self):
        return self._muted

    def is_playing(self):
        try:
            _, state, _ = self.pl.get_state(0)
            return state == Gst.State.PLAYING
        except: 
            return False

    def _eos(self, bus, msg):
        if self.on_eos: 
            GLib.idle_add(self.on_eos)

    def _err(self, bus, msg):
        err, debug = msg.parse_error()
        print(f"GStreamer Fehler: {err}")

    def _on_state_changed_msg(self, bus, msg):
        if msg.src == self.pl:
            old, new, _ = msg.parse_state_changed()
            if new == Gst.State.PLAYING:
                GLib.idle_add(self._reapply_volume)
                GLib.idle_add(self._reapply_eq)

    def _reapply_volume(self):
        # Nur Volume setzen wenn gerade kein Fade läuft —
        # sonst würde _reapply den laufenden fade_in auf target_vol
        # hochspringen und der Fade-Effekt geht verloren.
        if self.parent and hasattr(self.parent, 'fader'):
            if self.parent.fader.is_fading():
                return False
        self.set_vol(self.target_vol)
        return False

    def _reapply_eq(self):
        if self._eq_element and self._eq_enabled and self._eq_preset in EQ_PRESETS:
            self.set_eq_preset(self._eq_preset, EQ_PRESETS[self._eq_preset])
        return False

    def _on_element_msg(self, bus, msg):
        try:
            s = msg.get_structure()
            if s and s.get_name() == "spectrum" and self._vis_callback:
                magnitudes = s.get_value("magnitude")
                if magnitudes:
                    mag_list = list(magnitudes)
                    GLib.idle_add(self._vis_callback, mag_list)
        except Exception as e:
            print(f"Spectrum Fehler: {e}")


# ─── Visualiser mit echtem GStreamer-Spektrum ─────────────────────────────────
VIS_MODES = ["Balken", "Spiegel", "Punkte", "Würfel", "Aus"]

class Visualiser(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_content_height(64)
        self.set_hexpand(True)
        self._n = 48
        self._bars      = [0.02] * self._n
        self._peaks     = [0.0]  * self._n
        self._peak_hold = [0]    * self._n
        self._phase     = 0.0
        self._phase2    = 0.0
        self.playing    = False
        self._color1    = (0.4, 0.6, 0.8)
        self._color2    = (0.6, 0.4, 0.8)
        self._mode      = 0
        self._spectrum_buf = []
        self._last_update = time.time()
        self._lock = threading.Lock()
        self.set_draw_func(self._draw)
        GLib.timeout_add(33, self._animate)

    def apply_theme_colors(self, accent, accent2):
        self._color1 = accent
        self._color2 = (
            min(1.0, accent[0] * 0.6 + accent2[0] * 0.4),
            min(1.0, accent[1] * 0.7 + accent2[1] * 0.3),
            min(1.0, accent[2] * 0.8 + accent2[2] * 0.2),
        )

    def set_mode(self, idx):
        self._mode = idx % len(VIS_MODES)

    def feed_spectrum(self, magnitudes):
        if not magnitudes: 
            return
        with self._lock:
            self._spectrum_buf = list(magnitudes)
            self._last_update = time.time()

    def _animate(self):
        current_time = time.time()
        with self._lock:
            raw = list(self._spectrum_buf) if self._spectrum_buf else []

        if raw and self.playing and (current_time - self._last_update) < 0.5:
            n = self._n
            step = max(1, len(raw) // n)
            for i in range(n):
                idx = i * step
                if idx < len(raw):
                    db = raw[idx]
                    normalized = max(0.0, min(1.0, (db + 60.0) / 60.0))
                    if normalized > self._bars[i]:
                        self._bars[i] = normalized * 0.7 + self._bars[i] * 0.3
                    else:
                        self._bars[i] = normalized * 0.15 + self._bars[i] * 0.85
                    if self._bars[i] >= self._peaks[i]:
                        self._peaks[i] = self._bars[i]
                        self._peak_hold[i] = 18
                    else:
                        if self._peak_hold[i] > 0:
                            self._peak_hold[i] -= 1
                        else:
                            self._peaks[i] = max(0, self._peaks[i] - 0.015)
        elif not self.playing or (current_time - self._last_update) >= 0.5:
            for i in range(self._n):
                self._bars[i] = max(0.01, self._bars[i] * 0.88)
                self._peaks[i] = max(0, self._peaks[i] * 0.92)

        self._phase  += 0.06
        self._phase2 += 0.03
        self.queue_draw()
        return True

    def _draw(self, _, cr, W, H):
        mode_name = VIS_MODES[self._mode % len(VIS_MODES)]
        if mode_name == "Aus":
            return
        r1, g1, b1 = self._color1
        r2, g2, b2 = self._color2

        if mode_name == "Balken":
            self._draw_bars(cr, W, H, r1, g1, b1, r2, g2, b2)
        elif mode_name == "Spiegel":
            self._draw_mirror(cr, W, H, r1, g1, b1, r2, g2, b2)
        elif mode_name == "Punkte":
            self._draw_dots(cr, W, H, r1, g1, b1, r2, g2, b2)
        elif mode_name == "Würfel":
            self._draw_cubes(cr, W, H, r1, g1, b1, r2, g2, b2)

    def _draw_bars(self, cr, W, H, r1, g1, b1, r2, g2, b2):
        n = self._n
        bar_w = W / (n * 1.5)
        gap   = bar_w * 0.5
        total = bar_w + gap
        offset = (W - total * n) / 2
        for i, v in enumerate(self._bars):
            h = max(2, v * (H - 4))
            x = offset + i * total
            y = H - h
            grad = cairo.LinearGradient(x, y, x, H)
            t = i / n
            grad.add_color_stop_rgba(0.0, r2+t*(r1-r2), g2+t*(g1-g2), b2+t*(b1-b2), 0.95)
            grad.add_color_stop_rgba(1.0, r2, g2, b2, 0.3)
            cr.set_source(grad)
            self._rr(cr, x, y, bar_w, h, min(bar_w/2, 3))
            cr.fill()
            if self._peaks[i] > 0.05:
                py = H - self._peaks[i] * (H - 4) - 2
                cr.rectangle(x, py, bar_w, 2)
                cr.set_source_rgba(r1, g1, b1, 0.9)
                cr.fill()

    def _draw_cubes(self, cr, W, H, r1, g1, b1, r2, g2, b2):
        n = self._n
        cols = n
        cell_w = W / cols
        rows = 7
        cell_h = H / rows
        cube_pad = max(1.0, cell_w * 0.12)
        cw = cell_w - cube_pad * 2
        ch = cell_h - cube_pad * 1.5
        depth = max(2.0, cw * 0.35)

        for i in range(cols):
            v = self._bars[i]
            lit = max(1, int(v * rows))
            t = i / cols
            for row in range(rows):
                active = row >= (rows - lit)
                x = i * cell_w + cube_pad
                y = row * cell_h + cube_pad

                if active:
                    brightness = 0.6 + (rows - row) / rows * 0.4
                    fr = min(1.0, (r1 + t*(r2-r1)) * brightness)
                    fg = min(1.0, (g1 + t*(g2-g1)) * brightness)
                    fb = min(1.0, (b1 + t*(b2-b1)) * brightness)
                    alpha = 0.92

                    cr.rectangle(x, y, cw, ch)
                    cr.set_source_rgba(fr, fg, fb, alpha)
                    cr.fill()

                    cr.move_to(x,          y)
                    cr.line_to(x + depth,  y - depth * 0.5)
                    cr.line_to(x + cw + depth, y - depth * 0.5)
                    cr.line_to(x + cw,     y)
                    cr.close_path()
                    cr.set_source_rgba(min(1.0,fr*1.4), min(1.0,fg*1.4), min(1.0,fb*1.4), alpha)
                    cr.fill()

                    cr.move_to(x + cw,     y)
                    cr.line_to(x + cw + depth, y - depth * 0.5)
                    cr.line_to(x + cw + depth, y + ch - depth * 0.5)
                    cr.line_to(x + cw,     y + ch)
                    cr.close_path()
                    cr.set_source_rgba(fr*0.55, fg*0.55, fb*0.55, alpha)
                    cr.fill()

                else:
                    cr.rectangle(x + 0.5, y + 0.5, cw - 1, ch - 1)
                    cr.set_source_rgba(r1, g1, b1, 0.07)
                    cr.fill()

    def _draw_mirror(self, cr, W, H, r1, g1, b1, r2, g2, b2):
        n = self._n
        bar_w = W / (n * 1.5)
        total = bar_w + bar_w * 0.5
        offset = (W - total * n) / 2
        for i, v in enumerate(self._bars):
            h = max(2, v * (H/2 - 4))
            x = offset + i * total
            t = i / n
            grad = cairo.LinearGradient(x, H/2 - h, x, H/2 + h)
            grad.add_color_stop_rgba(0.0, r1, g1, b1, 0.2)
            grad.add_color_stop_rgba(0.5, r2+t*(r1-r2), g2+t*(g1-g2), b2+t*(b1-b2), 0.95)
            grad.add_color_stop_rgba(1.0, r1, g1, b1, 0.2)
            cr.set_source(grad)
            self._rr(cr, x, H/2 - h, bar_w, h * 2, min(bar_w/2, 3))
            cr.fill()

    def _draw_dots(self, cr, W, H, r1, g1, b1, r2, g2, b2):
        n = self._n
        cols = n
        cell_w = W / cols
        rows = 8
        cell_h = H / rows
        for i in range(cols):
            v = self._bars[i]
            lit = max(1, int(v * rows))
            for row in range(rows):
                active = row >= (rows - lit)
                x = i * cell_w + cell_w/2
                y = row * cell_h + cell_h/2
                r = cell_w * 0.3
                t = i / cols
                if active:
                    brightness = 1.0 - (rows - row - 1) / rows * 0.4
                    cr.arc(x, y, r, 0, 2*math.pi)
                    cr.set_source_rgba(
                        (r1+t*(r2-r1))*brightness,
                        (g1+t*(g2-g1))*brightness,
                        (b1+t*(b2-b1))*brightness, 0.9)
                    cr.fill()
                else:
                    cr.arc(x, y, r*0.5, 0, 2*math.pi)
                    cr.set_source_rgba(r1, g1, b1, 0.08)
                    cr.fill()

    def _rr(self, cr, x, y, w, h, r):
        if w <= 0 or h <= 0: return
        r = min(r, w/2, h/2)
        cr.new_sub_path()
        cr.arc(x+r,   y+r,   r, math.pi,     3*math.pi/2)
        cr.arc(x+w-r, y+r,   r, 3*math.pi/2, 0)
        cr.arc(x+w-r, y+h-r, r, 0,           math.pi/2)
        cr.arc(x+r,   y+h-r, r, math.pi/2,   math.pi)
        cr.close_path()


# ─── Cover Widget ───────────────────────────────────────────────────────────
class CoverWidget(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_content_width(200)
        self.set_content_height(200)
        self.pixbuf   = None
        self._spin    = 0.0
        self.playing  = False
        self.set_draw_func(self._draw)
        GLib.timeout_add(33, self._tick)

    def _tick(self):
        if self.playing:
            self._spin = (self._spin + 0.4) % 360
            self.queue_draw()
        return True

    def _draw(self, _, cr, W, H):
        pad = 6
        x, y = pad, pad
        w, h = W - 2*pad, H - 2*pad
        r = 8

        cr.save()
        cr.translate(3, 4)
        self._rr(cr, x, y, w, h, r)
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.fill()
        cr.restore()

        if self.playing:
            for i in range(4, 0, -1):
                self._rr(cr, x-i*2, y-i*2, w+i*4, h+i*4, r+i)
                cr.set_source_rgba(*C["accent"], 0.04*i)
                cr.fill()

        self._rr(cr, x, y, w, h, r)
        cr.clip()

        if self.pixbuf:
            pw, ph = self.pixbuf.get_width(), self.pixbuf.get_height()
            sc = max(w/pw, h/ph)
            ox = x + (w - pw*sc)/2
            oy = y + (h - ph*sc)/2
            cr.translate(ox, oy)
            cr.scale(sc, sc)
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 0, 0)
            cr.paint()
        else:
            cr.reset_clip()
            self._rr(cr, x, y, w, h, r); cr.clip()
            ang = math.radians(self._spin)
            g = cairo.LinearGradient(
                W/2 + math.cos(ang)*w/2, H/2 + math.sin(ang)*h/2,
                W/2 - math.cos(ang)*w/2, H/2 - math.sin(ang)*h/2)
            g.add_color_stop_rgb(0, *C["surface2"])
            g.add_color_stop_rgb(0.5, *C["surface"])
            g.add_color_stop_rgb(1, *C["bg"])
            cr.set_source(g)
            cr.paint()
            cr.reset_clip()
            self._rr(cr, x, y, w, h, r); cr.clip()
            cr.set_source_rgba(*C["muted"], 0.4)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(min(w, h) * 0.4)
            te = cr.text_extents("♫")
            cr.move_to(W/2 - te.width/2 - te.x_bearing,
                       H/2 - te.height/2 - te.y_bearing)
            cr.show_text("♫")

    def _rr(self, cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x+r,   y+r,   r, math.pi,     3*math.pi/2)
        cr.arc(x+w-r, y+r,   r, 3*math.pi/2, 0)
        cr.arc(x+w-r, y+h-r, r, 0,           math.pi/2)
        cr.arc(x+r,   y+h-r, r, math.pi/2,   math.pi)
        cr.close_path()

    def set_pixbuf(self, pixbuf):
        self.pixbuf = pixbuf
        self.queue_draw()


# ─── Progress bar ──────────────────────────────────────────────────────────────
class ProgressBar(Gtk.DrawingArea):
    def __init__(self, on_seek):
        super().__init__()
        self.set_content_height(22)
        self.set_hexpand(True)
        self._frac = 0.0
        self._hover = False
        self._hover_frac = 0.0
        self._dragging = False
        self.on_seek = on_seek
        self.set_draw_func(self._draw)
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        gc = Gtk.GestureClick.new()
        gc.connect("pressed", self._press)
        gc.connect("released", self._release)
        self.add_controller(gc)

        gd = Gtk.GestureDrag.new()
        gd.connect("drag-begin",  self._drag_begin)
        gd.connect("drag-update", self._drag_update)
        gd.connect("drag-end",    self._drag_end)
        self.add_controller(gd)

        mc = Gtk.EventControllerMotion.new()
        mc.connect("motion", self._motion)
        mc.connect("enter",  lambda c,x,y: self._set_hover(True))
        mc.connect("leave",  lambda c: self._set_hover(False))
        self.add_controller(mc)

    def set_fraction(self, f):
        if not self._dragging:
            self._frac = max(0, min(1, f))
            self.queue_draw()

    def _set_hover(self, v):
        self._hover = v; self.queue_draw()

    def _motion(self, ctrl, x, y):
        self._hover_frac = max(0, min(1, x / max(self.get_width(), 1)))
        if self._dragging:
            self._frac = self._hover_frac
            self.queue_draw()

    def _press(self, g, n, x, y):
        self._frac = max(0, min(1, x / max(self.get_width(), 1)))
        self.queue_draw()
        self.on_seek(self._frac)

    def _release(self, g, n, x, y):
        pass

    def _drag_begin(self, g, x, y):
        self._dragging = True

    def _drag_update(self, g, ox, oy):
        res = g.get_start_point()
        start_x = res[1] if len(res) > 1 else res[0]
        x = start_x + ox
        self._frac = max(0, min(1, x / max(self.get_width(), 1)))
        self.queue_draw()
        self.on_seek(self._frac)

    def _drag_end(self, g, ox, oy):
        self._dragging = False
        self.on_seek(self._frac)

    def _draw(self, _, cr, W, H):
        h  = 5 if not self._hover else 7
        y0 = (H - h) / 2
        r  = h / 2

        self._rr(cr, 0, y0, W, h, r)
        cr.set_source_rgba(*C["surface2"], 1)
        cr.fill()

        if self._frac > 0:
            pw = self._frac * W
            self._rr(cr, 0, y0, pw, h, r)
            g = cairo.LinearGradient(0, 0, pw, 0)
            g.add_color_stop_rgb(0, *C["accent2"])
            g.add_color_stop_rgb(1, *C["accent"])
            cr.set_source(g)
            cr.fill()

        if self._hover and self._hover_frac > self._frac:
            pw2 = self._hover_frac * W
            pw  = self._frac * W
            self._rr(cr, pw, y0, pw2 - pw, h, r)
            cr.set_source_rgba(*C["accent"], 0.25)
            cr.fill()

        tx = self._frac * W
        thumb_r = 7 if self._hover or self._dragging else 5
        cr.arc(tx, H/2, thumb_r, 0, 2*math.pi)
        cr.set_source_rgb(*C["text"])
        cr.fill()
        cr.arc(tx, H/2, 3, 0, 2*math.pi)
        cr.set_source_rgb(*C["accent"])
        cr.fill()

    def _rr(self, cr, x, y, w, h, r):
        if w <= 0: return
        r = min(r, w/2, h/2)
        cr.new_sub_path()
        cr.arc(x+r,   y+r,   r, math.pi,     3*math.pi/2)
        cr.arc(x+w-r, y+r,   r, 3*math.pi/2, 0)
        cr.arc(x+w-r, y+h-r, r, 0,           math.pi/2)
        cr.arc(x+r,   y+h-r, r, math.pi/2,   math.pi)
        cr.close_path()


def icon_btn(icon, tip="", size=Gtk.IconSize.NORMAL):
    b = Gtk.Button()
    b.set_icon_name(icon)
    b.set_tooltip_text(tip)
    b.set_css_classes(["flat"])
    return b


# ─── Smart Playlist Dialog ────────────────────────────────────────────────────
class SmartPlaylistDialog(Gtk.Dialog):
    def __init__(self, parent, generator):
        super().__init__(title="Intelligente Playlist erstellen", transient_for=parent, modal=True)
        self.set_default_size(450, 400)
        self.generator = generator
        self.result_playlist = None
        box = self.get_content_area()
        box.set_spacing(12); box.set_margin_start(18); box.set_margin_end(18)
        box.set_margin_top(12); box.set_margin_bottom(12)
        type_frame = Gtk.Frame(); type_frame.set_label("Playlist-Typ"); box.append(type_frame)
        type_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        type_box.set_margin_top(8); type_box.set_margin_bottom(8)
        type_box.set_margin_start(8); type_box.set_margin_end(8)
        type_frame.set_child(type_box)
        self.type_combo = Gtk.DropDown.new_from_strings([
            "Noch nie gehört","Meistgehört (Top 50)","Meistgehört (Top 100)","Wenig gehört (Bottom 50)",
            "Neueste Songs","Älteste Songs","Kürzlich hinzugefügt","Favoriten",
            "Nach Bewertung (4+ Sterne)","Nach Bewertung (5 Sterne)",
            "Nach Künstler","Nach Genre","Nach Jahr","Nach Dekade",
            "Zufällig (20)","Zufällig (50)","Zufällig (100)"])
        type_box.append(self.type_combo)
        param_frame = Gtk.Frame(); param_frame.set_label("Parameter"); box.append(param_frame)
        self.param_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.param_box.set_margin_top(8); self.param_box.set_margin_bottom(8)
        self.param_box.set_margin_start(8); self.param_box.set_margin_end(8)
        param_frame.set_child(self.param_box)
        self.param_entry = Gtk.Entry(); self.param_entry.set_placeholder_text("Wert eingeben...")
        self.param_box.append(self.param_entry)
        self.limit_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.limit_box.set_margin_top(6); self.param_box.append(self.limit_box)
        self.limit_box.append(Gtk.Label(label="Max. Anzahl:"))
        self.limit_spin = Gtk.SpinButton()
        self.limit_spin.set_range(5, 500); self.limit_spin.set_value(50); self.limit_spin.set_increments(5, 20)
        self.limit_box.append(self.limit_spin)
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END); btn_box.set_margin_top(20); box.append(btn_box)
        cancel_btn = Gtk.Button(label="Abbrechen"); cancel_btn.connect("clicked", lambda b: self.close())
        btn_box.append(cancel_btn)
        create_btn = Gtk.Button(label="Erstellen"); create_btn.add_css_class("suggested-action")
        create_btn.connect("clicked", self._create); btn_box.append(create_btn)
        self.type_combo.connect("notify::selected", self._on_type_changed); self._on_type_changed()

    def _on_type_changed(self, *args):
        selected = self.type_combo.get_selected()
        self.param_entry.set_visible(selected in [10,11,12,13])
        self.limit_box.set_visible(selected in [2,3,14,15,16])
        tips = {10:"Künstlername...",11:"Genre...",12:"Jahr (z.B. 2020)...",13:"Dekade (z.B. 1990 für 90er)..."}
        if selected in tips: self.param_entry.set_placeholder_text(tips[selected])
        defaults = {2:100,3:50,14:20,15:50,16:100}
        if selected in defaults: self.limit_spin.set_value(defaults[selected])

    def _create(self, btn):
        selected = self.type_combo.get_selected()
        limit = self.limit_spin.get_value_as_int()
        try:
            actions = {
                0: lambda: self.generator.generate_never_played(50),
                1: lambda: self.generator.generate_most_played(50),
                2: lambda: self.generator.generate_most_played(limit),
                3: lambda: self.generator.generate_least_played(limit),
                4: lambda: self.generator.generate_newest(50),
                5: lambda: self.generator.generate_oldest(50),
                6: lambda: self.generator.generate_recently_added(30, 50),
                7: lambda: self.generator.generate_favorites(50),
                8: lambda: self.generator.generate_by_rating(4),
                9: lambda: self.generator.generate_by_rating(5),
                10: lambda: self.generator.generate_by_artist(self.param_entry.get_text()),
                11: lambda: self.generator.generate_by_genre(self.param_entry.get_text()),
                12: lambda: self.generator.generate_by_year(self.param_entry.get_text()),
                13: lambda: self.generator.generate_by_decade(int(self.param_entry.get_text())),
                14: lambda: self.generator.generate_random(limit),
                15: lambda: self.generator.generate_random(limit),
                16: lambda: self.generator.generate_random(limit),
            }
            self.result_playlist = actions[selected]()
            self.emit("response", Gtk.ResponseType.OK)
            self.close()
        except Exception as e:
            print(f"Fehler: {e}")


class AddToPlaylistDialog(Gtk.Dialog):
    def __init__(self, parent, song_paths):
        super().__init__(title="Zu Playlist hinzufügen", transient_for=parent, modal=True)
        self.set_default_size(350, 200)
        self.song_paths = song_paths; self.result = None
        box = self.get_content_area()
        box.set_spacing(12); box.set_margin_start(18); box.set_margin_end(18)
        box.set_margin_top(12); box.set_margin_bottom(12)
        q = f"Wie möchten Sie die {len(song_paths)} Songs hinzufügen?" if len(song_paths) > 1 else "Wie möchten Sie den Song hinzufügen?"
        box.append(Gtk.Label(label=q))
        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); btn_box.set_margin_top(10); box.append(btn_box)
        for label, action in [("Jetzt abspielen (aktuelle Playlist ersetzen)","replace"),
                               ("Zur aktuellen Playlist hinzufügen","add"),
                               ("Als neue Playlist anlegen","new")]:
            b = Gtk.Button(label=label)
            if action == "replace": b.add_css_class("suggested-action")
            b.connect("clicked", lambda btn, a=action: self._set_result(a))
            btn_box.append(b)
        cancel_btn = Gtk.Button(label="Abbrechen"); cancel_btn.connect("clicked", lambda b: self.close())
        btn_box.append(cancel_btn)

    def _set_result(self, action):
        self.result = action; self.emit("response", Gtk.ResponseType.OK); self.close()


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent, config):
        super().__init__(title="Einstellungen", transient_for=parent, modal=True)
        self.set_default_size(450, 450)
        self.config = config
        box = self.get_content_area()
        box.set_spacing(12); box.set_margin_start(18); box.set_margin_end(18)
        box.set_margin_top(12); box.set_margin_bottom(12)

        fade_frame = Gtk.Frame(); fade_frame.set_label("Fade-Einstellungen"); box.append(fade_frame)
        fade_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        fade_box.set_margin_top(8); fade_box.set_margin_bottom(8)
        fade_box.set_margin_start(8); fade_box.set_margin_end(8)
        fade_frame.set_child(fade_box)
        self.fade_enabled = Gtk.CheckButton(label="Fade-Effekte aktivieren")
        self.fade_enabled.set_active(config.get("fade_enabled", False)); fade_box.append(self.fade_enabled)
        dur_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); dur_box.set_margin_start(20); fade_box.append(dur_box)
        dur_box.append(Gtk.Label(label="Fade-Dauer (ms):"))
        self.fade_duration = Gtk.SpinButton()
        self.fade_duration.set_range(100, 5000); self.fade_duration.set_increments(100, 500)
        self.fade_duration.set_value(config.get("fade_duration", 2000)); dur_box.append(self.fade_duration)
        curve_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); curve_box.set_margin_start(20); fade_box.append(curve_box)
        curve_box.append(Gtk.Label(label="Fade-Kurve:"))
        self.fade_curve = Gtk.DropDown.new_from_strings(["Linear", "Sanft (Smooth)", "Exponentiell"])
        curves = ["linear","smooth","exponential"]
        current = config.get("fade_curve", "smooth")
        if current in curves: self.fade_curve.set_selected(curves.index(current))
        curve_box.append(self.fade_curve)

        cover_frame = Gtk.Frame(); cover_frame.set_label("Cover-Einstellungen"); box.append(cover_frame)
        cover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        cover_box.set_margin_top(8); cover_box.set_margin_bottom(8)
        cover_box.set_margin_start(8); cover_box.set_margin_end(8)
        cover_frame.set_child(cover_box)
        self.auto_cover = Gtk.CheckButton(label="Automatische Cover-Suche aktivieren")
        self.auto_cover.set_active(config.get("auto_cover", True)); cover_box.append(self.auto_cover)
        sources_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10); sources_box.set_margin_start(20); cover_box.append(sources_box)
        sources_box.append(Gtk.Label(label="Cover-Quellen:"))
        self.source_mb = Gtk.CheckButton(label="MusicBrainz"); self.source_mb.set_active(config.get("source_musicbrainz", True)); sources_box.append(self.source_mb)
        self.source_itunes = Gtk.CheckButton(label="iTunes"); self.source_itunes.set_active(config.get("source_itunes", True)); sources_box.append(self.source_itunes)

        resume_frame = Gtk.Frame(); resume_frame.set_label("Wiedergabe-Fortsetzung"); box.append(resume_frame)
        resume_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        resume_box.set_margin_top(8); resume_box.set_margin_bottom(8)
        resume_box.set_margin_start(8); resume_box.set_margin_end(8)
        resume_frame.set_child(resume_box)
        self.resume_enabled = Gtk.CheckButton(label="Wiedergabe an letzter Position fortsetzen")
        self.resume_enabled.set_active(config.get("resume_enabled", True)); resume_box.append(self.resume_enabled)

        pl_frame = Gtk.Frame(); pl_frame.set_label("Playlist-Verhalten"); box.append(pl_frame)
        pl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        pl_box.set_margin_top(8); pl_box.set_margin_bottom(8)
        pl_box.set_margin_start(8); pl_box.set_margin_end(8)
        pl_frame.set_child(pl_box)
        self.queue_on_click = Gtk.CheckButton(label="Klick auf Song: als Nächstes spielen (nach aktuellem Song)")
        self.queue_on_click.set_active(config.get("queue_on_click", False)); pl_box.append(self.queue_on_click)

        scan_frame = Gtk.Frame(); scan_frame.set_label("Ordner automatisch scannen"); box.append(scan_frame)
        scan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scan_box.set_margin_top(8); scan_box.set_margin_bottom(8)
        scan_box.set_margin_start(8); scan_box.set_margin_end(8)
        scan_frame.set_child(scan_box)
        self.auto_scan = Gtk.CheckButton(label="Musik-Ordner automatisch nach neuen Dateien durchsuchen")
        self.auto_scan.set_active(config.get("auto_scan", True)); scan_box.append(self.auto_scan)
        interval_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        interval_row.set_margin_start(20); scan_box.append(interval_row)
        interval_row.append(Gtk.Label(label="Intervall (Minuten):"))
        self.scan_interval = Gtk.SpinButton()
        self.scan_interval.set_range(1, 120); self.scan_interval.set_increments(1, 5)
        self.scan_interval.set_value(config.get("scan_interval_min", 10))
        interval_row.append(self.scan_interval)
        self.auto_scan.connect("toggled", lambda b: self.scan_interval.set_sensitive(b.get_active()))
        self.scan_interval.set_sensitive(config.get("auto_scan", True))

        # Hörbuch / Hörspiel Auto-Scan
        ab_scan_frame = Gtk.Frame(); ab_scan_frame.set_label("Hörbuch/Hörspiel-Ordner automatisch scannen"); box.append(ab_scan_frame)
        ab_scan_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ab_scan_box.set_margin_top(8); ab_scan_box.set_margin_bottom(8)
        ab_scan_box.set_margin_start(8); ab_scan_box.set_margin_end(8)
        ab_scan_frame.set_child(ab_scan_box)
        self.ab_auto_scan = Gtk.CheckButton(label="~/Hörbuch und ~/Hörspiel automatisch nach neuen Dateien durchsuchen")
        self.ab_auto_scan.set_active(config.get("ab_auto_scan", True)); ab_scan_box.append(self.ab_auto_scan)
        # Info-Label welche Ordner gescannt werden
        import os as _os
        hb_dir = config.get("ab_dirs", [_os.path.expanduser("~/Hörbuch")])[0] if config.get("ab_dirs") else _os.path.expanduser("~/Hörbuch")
        hs_dir = config.get("hoerspiel_dir", _os.path.expanduser("~/Hörspiel"))
        scan_info = Gtk.Label(label=f"Hörbuch: {hb_dir}\nHörspiel: {hs_dir}")
        scan_info.set_halign(Gtk.Align.START)
        scan_info.set_margin_start(20)
        scan_info.set_css_classes(["dim-label"])
        scan_info.set_wrap(True)
        ab_scan_box.append(scan_info)
        ab_interval_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ab_interval_row.set_margin_start(20); ab_scan_box.append(ab_interval_row)
        ab_interval_row.append(Gtk.Label(label="Intervall (Minuten):"))
        self.ab_scan_interval = Gtk.SpinButton()
        self.ab_scan_interval.set_range(1, 120); self.ab_scan_interval.set_increments(1, 5)
        self.ab_scan_interval.set_value(config.get("ab_scan_interval_min", 15))
        ab_interval_row.append(self.ab_scan_interval)
        self.ab_auto_scan.connect("toggled", lambda b: self.ab_scan_interval.set_sensitive(b.get_active()))
        self.ab_scan_interval.set_sensitive(config.get("ab_auto_scan", True))

        # ── Schriftgröße ──────────────────────────────────────────
        font_frame = Gtk.Frame(); font_frame.set_label("Schriftgröße"); box.append(font_frame)
        font_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        font_box.set_margin_top(8); font_box.set_margin_bottom(8)
        font_box.set_margin_start(8); font_box.set_margin_end(8)
        font_frame.set_child(font_box)

        font_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        font_row.append(Gtk.Label(label="Playlist & Benutzeroberfläche:"))
        self.font_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 8, 22, 1)
        self.font_scale.set_value(config.get("font_size", 16))
        self.font_scale.set_hexpand(True)
        self.font_scale.set_draw_value(True)
        self.font_scale.set_digits(0)
        for v in [8, 10, 12, 14, 16, 18, 20, 22]:
            self.font_scale.add_mark(v, Gtk.PositionType.BOTTOM, str(v))
        font_row.append(self.font_scale)
        font_box.append(font_row)

        hint = Gtk.Label(label="Standard: 12px  |  Für schlechte Sicht empfohlen: 16–18px")
        hint.set_css_classes(["dim-label"])
        hint.set_halign(Gtk.Align.START)
        font_box.append(hint)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END); btn_box.set_margin_top(20); box.append(btn_box)
        cancel_btn = Gtk.Button(label="Abbrechen"); cancel_btn.connect("clicked", lambda b: self.close()); btn_box.append(cancel_btn)
        save_btn = Gtk.Button(label="Speichern"); save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._save); btn_box.append(save_btn)

    def _save(self, btn):
        self.config["fade_enabled"] = self.fade_enabled.get_active()
        self.config["fade_duration"] = self.fade_duration.get_value_as_int()
        curves = ["linear","smooth","exponential"]
        sel = self.fade_curve.get_selected()
        if 0 <= sel < len(curves): self.config["fade_curve"] = curves[sel]
        self.config["auto_cover"] = self.auto_cover.get_active()
        self.config["source_musicbrainz"] = self.source_mb.get_active()
        self.config["source_itunes"] = self.source_itunes.get_active()
        self.config["resume_enabled"] = self.resume_enabled.get_active()
        self.config["queue_on_click"] = self.queue_on_click.get_active()
        self.config["auto_scan"]          = self.auto_scan.get_active()
        self.config["scan_interval_min"]  = self.scan_interval.get_value_as_int()
        self.config["ab_auto_scan"]       = self.ab_auto_scan.get_active()
        self.config["ab_scan_interval_min"] = self.ab_scan_interval.get_value_as_int()
        self.config["font_size"] = int(self.font_scale.get_value())
        self.emit("response", Gtk.ResponseType.OK); self.close()


class SleepDialog(Gtk.Dialog):
    def __init__(self, parent, on_set):
        super().__init__(title="Sleep-Timer", transient_for=parent, modal=True)
        self.set_default_size(280, 160); self.on_set = on_set
        box = self.get_content_area()
        box.set_spacing(12); box.set_margin_start(18); box.set_margin_end(18)
        box.set_margin_top(12); box.set_margin_bottom(12)
        lbl = Gtk.Label(label="Pause nach … Minuten:"); lbl.set_halign(Gtk.Align.START); box.append(lbl)
        self.spin = Gtk.SpinButton()
        self.spin.set_range(1, 240); self.spin.set_value(30); self.spin.set_increments(5, 15); box.append(self.spin)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8); row.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Abbrechen"); cancel.connect("clicked", lambda *_: self.close()); row.append(cancel)
        ok = Gtk.Button(label="Starten"); ok.add_css_class("suggested-action")
        ok.connect("clicked", self._ok); row.append(ok); box.append(row); self.present()

    def _ok(self, *_): self.on_set(int(self.spin.get_value())); self.close()


class PlaylistPanel(Gtk.Box):
    """Playlist-Panel mit 4 Ansichtsmodi: Liste / Interpret / Album / Jahr."""

    VIEWS = [
        ("view-list-symbolic",         "Liste",     "list"),
        ("avatar-default-symbolic",    "Interpret", "artist"),
        ("media-optical-symbolic",     "Album",     "album"),
        ("x-office-calendar-symbolic", "Jahr",      "year"),
    ]

    def __init__(self, on_select, on_remove):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_vexpand(True)
        self.on_select  = on_select
        self.on_remove  = on_remove
        self._playlist  = []
        self._current   = -1
        self._rows      = []          # parallele Liste → playlist-Index je Song-Zeile
        self._view_mode  = "list"      # "list" | "artist" | "album" | "year"
        self._sort_alpha         = True    # alphabetisch nach Bandname sortieren
        self.on_sort_alpha_changed = None  # Callback → Album-Grid sync
        self._meta               = {}          # path → {artist, album, year, title}
        self._meta_lock  = threading.Lock()

        # ── View-Umschalter ───────────────────────────────────────
        view_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        view_bar.set_margin_start(0); view_bar.set_margin_bottom(4)
        self._view_btns = {}
        for icon, tip, mode in self.VIEWS:
            b = Gtk.Button(icon_name=icon)
            b.set_tooltip_text(tip)
            b.set_css_classes(["vis-btn", "vis-btn-active" if mode == "list" else "flat"])
            b.connect("clicked", lambda _, m=mode: self._set_view(m))
            view_bar.append(b)
            self._view_btns[mode] = b

        # Trennlinie
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(4); sep.set_margin_end(4)
        sep.set_margin_top(4);   sep.set_margin_bottom(4)
        view_bar.append(sep)

        # Alle ein-/ausklappen
        self._collapse_all_btn = Gtk.Button(icon_name="pan-end-symbolic")
        self._collapse_all_btn.set_tooltip_text("Alle einrollen")
        self._collapse_all_btn.set_css_classes(["vis-btn", "flat"])
        self._collapse_all_btn.connect("clicked", self._toggle_all_groups)
        view_bar.append(self._collapse_all_btn)

        self._collapse_all_btn.set_visible(False)  # nur in Gruppenansichten sichtbar

        sep2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep2.set_margin_start(4); sep2.set_margin_end(4)
        sep2.set_margin_top(4);   sep2.set_margin_bottom(4)
        view_bar.append(sep2)

        self._sort_alpha_btn = Gtk.Button(label="A→Z ✓")
        self._sort_alpha_btn.set_tooltip_text("Alphabetisch nach Bandname sortieren")
        self._sort_alpha_btn.set_css_classes(["vis-btn", "vis-btn-active"])
        self._sort_alpha_btn.connect("clicked", self._toggle_sort_alpha)
        view_bar.append(self._sort_alpha_btn)

        self.append(view_bar)

        # ── Scrollbare ListBox ────────────────────────────────────
        self._scroll = Gtk.ScrolledWindow(); self._scroll.set_vexpand(True)
        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list.connect("row-activated", self._on_row_activated)
        self._scroll.set_child(self._list)
        self.append(self._scroll)

    # ── Öffentliche API ───────────────────────────────────────────
    def set_playlist(self, playlist, current):
        self._playlist = list(playlist)
        self._current  = current
        self._rows     = []
        # Metadaten für neue Pfade nachladen
        new_paths = [p for p in playlist if p not in self._meta]
        if new_paths:
            threading.Thread(target=self._load_meta_bulk,
                             args=(new_paths,), daemon=True).start()
        self._rebuild()

    def highlight(self, idx):
        self._current = idx
        # In Gruppenansicht: NUR die Gruppe des aktuellen Songs aufgeklappt lassen
        if self._view_mode != "list" and 0 <= idx < len(self._playlist):
            active = self._get_active_groups(self._view_mode)
            if active:
                all_names = set(self._all_group_names)
                new_collapsed = all_names - active
                # Rebuild wenn sich die aufgeklappte Gruppe geändert hat
                # ODER wenn noch andere Gruppen offen sind
                if new_collapsed != self._collapsed:
                    self._collapsed = new_collapsed
                    GLib.idle_add(self._rebuild)
                    return
        # CSS aller Song-Zeilen aktualisieren
        for pl_idx, row in self._rows:
            child = row.get_child()
            if not child: continue
            css = [c for c in child.get_css_classes() if c != "playing-row"]
            if pl_idx == idx:
                css.append("playing-row")
            child.set_css_classes(css)
        # Zur aktiven Zeile scrollen
        for pl_idx, row in self._rows:
            if pl_idx == idx:
                self._list.select_row(row)
                GLib.idle_add(self._scroll_to_row, row)
                break

    # ── Metadaten-Cache ───────────────────────────────────────────
    def _load_meta_bulk(self, paths):
        for path in paths:
            if path in self._meta: continue
            meta = {"title": Path(path).stem,
                    "artist": "Unbekannt", "album": "", "year": ""}
            try:
                uri  = Gst.filename_to_uri(os.path.abspath(path))
                info = GstPbutils.Discoverer.new(2 * Gst.SECOND).discover_uri(uri)
                tags = None
                for s in info.get_stream_list():
                    tags = s.get_tags()
                    if tags: break
                if tags:
                    for gkey, mkey in [
                        (Gst.TAG_TITLE,  "title"),
                        (Gst.TAG_ARTIST, "artist"),
                        (Gst.TAG_ALBUM,  "album"),
                    ]:
                        ok, v = tags.get_string(gkey)
                        if ok and v: meta[mkey] = str(v)
                    ok, v = tags.get_string(Gst.TAG_DATE_TIME)
                    if ok and v: meta["year"] = str(v)[:4]
            except: pass
            with self._meta_lock:
                self._meta[path] = meta
        # Nach dem Laden neu aufbauen
        GLib.idle_add(self._rebuild)
        if callable(getattr(self, "on_meta_ready", None)):
            GLib.idle_add(self.on_meta_ready)

    def _get_meta(self, path):
        with self._meta_lock:
            return self._meta.get(path, {
                "title": Path(path).stem,
                "artist": "Unbekannt", "album": "", "year": ""})

    # ── Alle ein-/ausklappen ──────────────────────────────────────
    def _toggle_all_groups(self, *_):
        if self._view_mode == "list": return
        # Entscheide Richtung: wenn alles eingeklappt → aufklappen, sonst einrollen
        all_collapsed = all(g in self._collapsed for g in self._all_group_names)
        if all_collapsed:
            self._collapsed.clear()
            self._collapse_all_btn.set_icon_name("pan-end-symbolic")
            self._collapse_all_btn.set_tooltip_text("Alle einrollen")
        else:
            self._collapsed = set(self._all_group_names)
            self._collapse_all_btn.set_icon_name("pan-start-symbolic")
            self._collapse_all_btn.set_tooltip_text("Alle aufklappen")
        self._rebuild()

    def _toggle_sort_alpha(self, *_):
        self._sort_alpha = not self._sort_alpha
        if self._sort_alpha:
            self._sort_alpha_btn.set_label("A→Z ✓")
            self._sort_alpha_btn.set_css_classes(["vis-btn", "vis-btn-active"])
        else:
            self._sort_alpha_btn.set_label("A→Z")
            self._sort_alpha_btn.set_css_classes(["vis-btn", "flat"])
        self._rebuild()
        if callable(getattr(self, "on_sort_alpha_changed", None)):
            self.on_sort_alpha_changed(self._sort_alpha)

    # ── View-Umschalten ───────────────────────────────────────────
    def _set_view(self, mode):
        self._view_mode = mode
        self._collapse_all_btn.set_visible(mode != "list")
        for m, b in self._view_btns.items():
            b.set_css_classes(["vis-btn", "vis-btn-active" if m == mode else "flat"])
        # Bei Gruppenansicht: alle einklappen, nur aktive Gruppe aufklappen
        if mode != "list":
            self._collapsed = self._get_all_group_names(mode) - self._get_active_groups(mode)
        self._rebuild()

    def _get_all_group_names(self, group_key):
        """Gibt alle Gruppennamen für den gegebenen Schlüssel zurück."""
        groups = set()
        for path in self._playlist:
            meta = self._get_meta(path)
            key = meta.get(group_key, "") or "Unbekannt"
            if group_key == "year":
                key = key[:4] if key else "Unbekannt"
            groups.add(key)
        return groups

    def _get_active_groups(self, group_key):
        """Gibt die Gruppe des aktuell spielenden Songs zurück."""
        if self._current < 0 or self._current >= len(self._playlist):
            return set()
        path = self._playlist[self._current]
        meta = self._get_meta(path)
        key = meta.get(group_key, "") or "Unbekannt"
        if group_key == "year":
            key = key[:4] if key else "Unbekannt"
        return {key}

    # ── Liste aufbauen ────────────────────────────────────────────
    def _rebuild(self):
        while r := self._list.get_row_at_index(0):
            self._list.remove(r)
        self._rows = []

        if self._view_mode == "list":
            self._build_flat()
        else:
            self._build_grouped(self._view_mode)
            # Button-Icon anpassen je nach aktuellem Zustand
            all_collapsed = bool(self._all_group_names) and all(
                g in self._collapsed for g in self._all_group_names)
            self._collapse_all_btn.set_icon_name(
                "pan-start-symbolic" if all_collapsed else "pan-end-symbolic")
            self._collapse_all_btn.set_tooltip_text(
                "Alle aufklappen" if all_collapsed else "Alle einrollen")

        if self._current >= 0:
            self.highlight(self._current)

    def _build_flat(self):
        items = [(i, path, self._get_meta(path)) for i, path in enumerate(self._playlist)]
        if self._sort_alpha:
            items.sort(key=lambda x: (x[2].get("artist","") or "").lower())
        for i, path, meta in items:
            row = self._make_song_row(i, path, meta, show_num=True)
            self._rows.append((i, row))

    def _build_grouped(self, group_key):
        """Baut eine nach artist/album/year gruppierte Ansicht auf (einklappbar)."""
        groups = {}
        for i, path in enumerate(self._playlist):
            meta = self._get_meta(path)
            key  = meta.get(group_key, "") or "Unbekannt"
            if group_key == "year":
                key = key[:4] if key else "Unbekannt"
            groups.setdefault(key, []).append((i, path, meta))

        if self._sort_alpha:
            for k in groups:
                groups[k].sort(key=lambda x: (x[2].get("artist","") or "").lower())

        if not hasattr(self, "_collapsed"):
            self._collapsed = set()

        # Aktive Gruppe bestimmen BEVOR _all_group_names aufgebaut wird
        _active_now = self._get_active_groups(group_key)

        self._all_group_names = []   # für Alle-ein/ausklappen

        reverse = (group_key == "year")
        icons_map = {"artist": "avatar-default-symbolic",
                     "album":  "media-optical-symbolic",
                     "year":   "x-office-calendar-symbolic"}

        # Alle Gruppen einklappen außer der aktiven — IMMER erzwingen
        if _active_now:
            all_g = set(groups.keys())
            self._collapsed = all_g - _active_now

        for group_name in sorted(groups.keys(),
                                 key=lambda s: s.lower() if s != "Unbekannt" else "zzz",
                                 reverse=reverse):
            collapsed = group_name in self._collapsed
            self._all_group_names.append(group_name)

            # ── Header-Row: NICHT selektierbar, Klick via GestureClick ──
            hdr = Gtk.ListBoxRow()
            hdr.set_selectable(False)
            hdr.set_activatable(False)
            hdr.set_css_classes(["pl-group-header"])

            hdr_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            hdr_box.set_margin_start(8); hdr_box.set_margin_end(8)
            hdr_box.set_margin_top(6);   hdr_box.set_margin_bottom(6)

            arrow_lbl = Gtk.Label(label="▶" if collapsed else "▼")
            arrow_lbl.set_css_classes(["pl-group-arrow"])
            hdr_box.append(arrow_lbl)

            ico = Gtk.Image.new_from_icon_name(icons_map.get(group_key, "folder-symbolic"))
            ico.set_pixel_size(16)
            ico.set_css_classes(["pl-group-icon"])
            hdr_box.append(ico)

            name_lbl = Gtk.Label(label=group_name)
            name_lbl.set_css_classes(["pl-group-name"])
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_hexpand(True)
            name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            hdr_box.append(name_lbl)

            count = len(groups[group_name])
            cnt_lbl = Gtk.Label(label=f"{count} Song{'s' if count != 1 else ''}")
            cnt_lbl.set_css_classes(["pl-group-count"])
            hdr_box.append(cnt_lbl)

            hdr.set_child(hdr_box)
            self._list.append(hdr)

            # ── Song-Rows der Gruppe ──────────────────────────────
            song_rows = []
            for pl_idx, path, meta in groups[group_name]:
                row = self._make_song_row(pl_idx, path, meta,
                                          show_num=False, hide_key=group_key)
                row.set_visible(not collapsed)
                song_rows.append(row)
                self._rows.append((pl_idx, row))

            # ── GestureClick direkt auf hdr_box binden ────────────
            def _make_toggle(gname, arrow, rows, hdr_box):
                def _on_click(gesture, n, x, y):
                    if gname in self._collapsed:
                        self._collapsed.discard(gname)
                        arrow.set_label("▼")
                        for r in rows: r.set_visible(True)
                        hdr_box.set_css_classes(["pl-group-header"])
                    else:
                        self._collapsed.add(gname)
                        arrow.set_label("▶")
                        for r in rows: r.set_visible(False)
                return _on_click

            gc = Gtk.GestureClick.new()
            gc.connect("released", _make_toggle(group_name, arrow_lbl, song_rows, hdr))
            hdr.add_controller(gc)
            # Cursor als Pointer damit klar ist: klickbar
            hdr.set_cursor(Gdk.Cursor.new_from_name("pointer"))

    def _make_song_row(self, pl_idx, path, meta, show_num=True, hide_key=None):
        """Erstellt eine Song-Zeile. hide_key: welches Feld nicht angezeigt wird."""
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hbox.set_margin_start(8 if show_num else 20)
        hbox.set_margin_end(4); hbox.set_margin_top(3); hbox.set_margin_bottom(3)

        if show_num:
            num = Gtk.Label(label=f"{pl_idx+1:>3}")
            num.set_width_chars(4); num.set_css_classes(["dim-label"])
            hbox.append(num)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        info_box.set_hexpand(True)

        # Zeile 1: Bandname (fett)
        artist_val = meta.get("artist", "") if hide_key != "artist" else ""
        if artist_val and artist_val != "Unbekannt":
            artist_row = Gtk.Label(label=artist_val)
            artist_row.set_halign(Gtk.Align.START)
            artist_row.set_ellipsize(Pango.EllipsizeMode.END)
            artist_row.set_css_classes(["pl-row-title", "pl-row-artist"])
            info_box.append(artist_row)

        # Zeile 2: Songname
        title_lbl = Gtk.Label(label=meta.get("title", Path(path).stem))
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.set_css_classes(["pl-row-title"])
        info_box.append(title_lbl)

        # Zeile 3: Albumname (gedimmt)
        album_val = meta.get("album", "") if hide_key != "album" else ""
        if album_val:
            album_row = Gtk.Label(label=album_val)
            album_row.set_halign(Gtk.Align.START)
            album_row.set_ellipsize(Pango.EllipsizeMode.END)
            album_row.set_css_classes(["pl-row-sub"])
            info_box.append(album_row)

        hbox.append(info_box)

        rm = Gtk.Button(icon_name="list-remove-symbolic")
        rm.set_css_classes(["flat"]); rm.set_opacity(0.4)
        rm.connect("clicked", lambda *_: self.on_remove(pl_idx))
        hbox.append(rm)

        if pl_idx == self._current:
            hbox.add_css_class("playing-row")

        row = Gtk.ListBoxRow(); row.set_child(hbox)
        self._list.append(row)
        return row

    def _on_row_activated(self, listbox, row):
        for pl_idx, r in self._rows:
            if r == row:
                self.on_select(pl_idx)
                return

    # ── Scroll ────────────────────────────────────────────────────
    def _scroll_to_row(self, row):
        adj = self._scroll.get_vadjustment()
        if not adj: return
        try:
            result = row.translate_coordinates(self._list, 0, 0)
            if result is None: return
            row_y = result[1] if len(result) >= 2 else result[0]
        except Exception:
            return
        row_h     = row.get_height()
        page_size = adj.get_page_size()
        current   = adj.get_value()
        if row_y < current:
            adj.set_value(max(0, row_y - 8))
        elif row_y + row_h > current + page_size:
            adj.set_value(row_y + row_h - page_size + 8)


EQ_PRESETS = {
    "Flat":       [0,0,0,0,0,0,0,0,0,0],
    "Bass Boost": [6,5,4,2,0,0,0,0,0,0],
    "Treble":     [0,0,0,0,0,2,3,4,5,5],
    "Vocal":      [-2,-1,0,2,4,4,2,1,0,-1],
    "Rock":       [4,3,0,-1,-2,0,2,4,5,5],
    "Electronic": [5,4,1,0,-2,2,3,4,4,5],
    "Jazz":       [3,2,1,2,0,-1,-1,0,1,2],
    "Classical":  [4,3,2,1,0,0,-1,-1,0,1],
    "Podcast":    [-3,-2,0,3,5,5,3,1,0,-1],
}

CSS = b"""
window { background-color: @theme_bg_color; color: @theme_fg_color; }
.playing-row { font-weight: bold; color: @accent_color; }
.ctrl-btn {
    min-width: 36px;
    min-height: 36px;
    border-radius: 6px;
}
.ctrl-btn-primary {
    background-color: @accent_bg_color;
    color: @accent_fg_color;
    border-radius: 6px;
    min-width: 48px;
    min-height: 48px;
}
.ctrl-btn-primary:hover { filter: brightness(1.15); }
.active-toggle { color: @accent_color; }
.section-label { font-size: 10px; color: @theme_unfocused_fg_color; letter-spacing: 2px; }
.sleep-active { color: @theme_warning_color; }
.helga-tag { font-size: 10px; background-color: @theme_base_color; border-radius: 4px; padding: 1px 6px; }
.helga-artist { font-size: 22px; font-weight: bold; color: @theme_fg_color; }
.helga-title  { font-size: 20px; color: @theme_fg_color; }
.helga-album  { font-size: 18px; color: @theme_unfocused_fg_color; }
.helga-time { font-size: 11px; color: @accent_color; }
.vol-popover { padding: 12px; }
.vis-btn { min-width: 28px; min-height: 24px; border-radius: 4px; font-size: 10px; padding: 2px 6px; }
.vis-btn-active { background-color: @accent_bg_color; color: @accent_fg_color; border-radius: 4px; }
.ab-filter-btn { min-height: 34px; border-radius: 5px; font-size: 13px; padding: 2px 10px; }
.ab-filter-btn-active { background-color: @accent_bg_color; color: @accent_fg_color; border-radius: 5px; font-size: 13px; min-height: 34px; padding: 2px 10px; }
.eq-off { color: @theme_error_color; }
.radio-row-active { background-color: alpha(@accent_color, 0.18); border-left: 3px solid @accent_color; }
.radio-row-paused { background-color: alpha(@accent_color, 0.08); border-left: 3px solid alpha(@accent_color, 0.4); }
.radio-name { font-size: 13px; }
.radio-name-active { font-size: 15px; font-weight: bold; color: @accent_color; }
.radio-info { font-size: 11px; color: @theme_unfocused_fg_color; }
.radio-live-dot { font-size: 14px; color: @theme_error_color; }
.radio-live-label { font-size: 11px; font-weight: bold; color: @accent_color; }
.tab-btn { min-width: 100px; min-height: 32px; border-radius: 0; }
.tab-btn-active { background-color: @accent_bg_color; color: @accent_fg_color; border-radius: 0; }
.now-playing-bar { background-color: alpha(@accent_color, 0.12); border-radius: 6px; padding: 6px 10px; }
.suggested-action { background-color: @accent_bg_color; color: @accent_fg_color; }
.suggested-action:hover { filter: brightness(1.15); }
checkbutton check { background-color: @theme_base_color; border-color: alpha(@accent_color, 0.6); }
checkbutton check:checked { background-color: @accent_bg_color; border-color: @accent_bg_color; color: @accent_fg_color; }
checkbutton check:checked:hover { filter: brightness(1.15); }
.radio-quick-btn { min-height: 36px; border-radius: 5px; font-size: 13px; padding: 2px 10px; }
.ab-shelf-item { border-radius: 8px; padding: 8px; }
.ab-shelf-item:hover { background-color: alpha(@accent_color, 0.08); }
.ab-shelf-active { background-color: alpha(@accent_color, 0.18); border: 1px solid alpha(@accent_color, 0.5); border-radius: 8px; }
.ab-shelf-done { opacity: 0.6; }
.ab-title { font-size: 13px; font-weight: bold; }
.ab-author { font-size: 11px; color: @theme_unfocused_fg_color; }
.ab-progress-done { font-size: 10px; color: @accent_color; font-weight: bold; }
.ab-chapter-active { font-weight: bold; color: @accent_color; }
.ab-chapter { font-size: 12px; }
.ab-bookmark { font-size: 11px; color: @theme_unfocused_fg_color; border-left: 2px solid @accent_color; padding-left: 6px; }
.ab-speed-btn { min-width: 52px; min-height: 36px; font-size: 13px; border-radius: 5px; }
.ab-speed-active { background-color: @accent_bg_color; color: @accent_fg_color; border-radius: 5px; }
.ab-shelf-playing { background-color: alpha(@accent_color, 0.22); border-left: 3px solid @accent_color; border-radius: 8px; }
.ab-shelf-selected { background-color: alpha(@error_color, 0.18); border-left: 3px solid @error_color; border-radius: 8px; }
.pl-group-header { background-color: alpha(@accent_color, 0.10); border-left: 3px solid @accent_color; }
.pl-group-header:hover { background-color: alpha(@accent_color, 0.20); }
.pl-group-name { font-size: 13px; font-weight: bold; color: @accent_color; }
.pl-row-title { font-size: 12px; }
.pl-row-sub   { font-size: 10px; color: @theme_unfocused_fg_color; }
.pl-group-arrow { font-size: 11px; color: @accent_color; min-width: 14px; }
.pl-group-icon { color: @accent_color; }
.pl-group-count { font-size: 11px; color: alpha(@accent_color, 0.7); }
.album-tile { border-radius: 8px; padding: 4px; }
.album-tile:hover { background-color: alpha(@accent_color, 0.12); }
.album-tile-active { background-color: alpha(@accent_color, 0.22); border: 1px solid alpha(@accent_color, 0.6); border-radius: 8px; }
.album-tile-title { font-size: 11px; font-weight: bold; }
.album-tile-sub { font-size: 10px; color: @theme_unfocused_fg_color; }
.album-grid-size-btn { min-width: 26px; min-height: 22px; font-size: 10px; border-radius: 4px; padding: 0 4px; }
.lyrics-text { font-size: 13px; line-height: 1.6; }
.lyrics-active { font-weight: bold; color: @accent_color; font-size: 15px; }
.lyrics-listbox row { padding: 2px 4px; border: none; }
.lyrics-listbox { background: transparent; }
.album-grid-size-active { background-color: @accent_bg_color; color: @accent_fg_color; border-radius: 4px; }
.eq-band-lbl { font-size: 9px; color: @theme_unfocused_fg_color; }
.eq-band-val  { font-size: 9px; color: @accent_color; min-width: 28px; }
.eq-manual-row { background-color: alpha(@accent_color, 0.05); border-radius: 6px; padding: 4px; }
"""

# ─── Album-Cover-Grid ────────────────────────────────────────────────────────
class AlbumGridWidget(Gtk.Box):
    """Scrollbares Kachel-Grid aller Alben mit Cover, einstellbare Größe."""

    SIZES = [("S", 80), ("M", 120), ("L", 160), ("XL", 200)]

    def __init__(self, on_album_click):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_vexpand(True)
        self._on_album_click = on_album_click
        self._tile_size      = 160              # Start: L (160px)
        self._albums         = {}
        self._tiles          = {}
        self._active_album   = ""
        self._cover_cache    = {}
        self._pending        = set()
        self._auto_size      = True             # Größe automatisch an Breite anpassen
        self._sort_alpha     = True             # alphabetisch nach Bandname

        # ── Kopfzeile: Label + Größen-Buttons ────────────────────
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr.set_margin_start(2); hdr.set_margin_bottom(4)

        lbl = Gtk.Label(label="ALBEN")
        lbl.set_css_classes(["section-label"])
        lbl.set_hexpand(True); lbl.set_halign(Gtk.Align.START)
        hdr.append(lbl)

        self._size_btns = {}
        for label, size in self.SIZES:
            b = Gtk.Button(label=label)
            b.set_css_classes(
                ["album-grid-size-btn", "album-grid-size-active"
                 if size == self._tile_size else "album-grid-size-btn"])
            b.set_tooltip_text(f"Kachelgröße {label} ({size}px)")
            b.connect("clicked", lambda _, s=size: self._set_size_manual(s))
            hdr.append(b)
            self._size_btns[size] = b
        self.append(hdr)

        # ── Scrollbares FlowBox-Grid ──────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.append(scroll)

        self._flow = Gtk.FlowBox()
        self._flow.set_valign(Gtk.Align.START)
        self._flow.set_max_children_per_line(50)
        self._flow.set_min_children_per_line(1)
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_row_spacing(6)
        self._flow.set_column_spacing(6)
        self._flow.set_margin_start(2); self._flow.set_margin_end(2)
        scroll.set_child(self._flow)

        # GTK4: Breiten-Änderung über notify::natural-width-request nicht verfügbar,
        # daher SizeGroup-Trick: einfach auf measure-Änderung via idle prüfen
        self._flow.connect("notify::width", self._on_flow_width_changed)

    # ── Öffentliche API ───────────────────────────────────────────
    def update_from_playlist(self, playlist, meta_dict):
        """Playlist + Meta-Dict (path→{artist,album,…}) → Grid neu aufbauen."""
        albums = {}
        for path in playlist:
            meta   = meta_dict.get(path, {})
            album  = meta.get("album", "") or "Unbekanntes Album"
            artist = meta.get("artist", "") or "Unbekannt"
            albums.setdefault(album, {"paths": [], "artist": artist, "cover": None})
            albums[album]["paths"].append(path)
            # Ersten Künstler als Repräsentant merken
            if albums[album]["artist"] == "Unbekannt" and artist != "Unbekannt":
                albums[album]["artist"] = artist
        self._albums = albums
        self._rebuild_grid()

    def set_active_album(self, album_name):
        """Hebt das aktuell spielende Album hervor."""
        old = self._active_album
        self._active_album = album_name
        for alb, child in self._tiles.items():
            box = child.get_child()
            if not box: continue
            if alb == album_name:
                box.set_css_classes(["album-tile-active"])
            elif alb == old:
                box.set_css_classes(["album-tile"])

    # ── Intern ───────────────────────────────────────────────────
    def _set_size(self, size):
        self._tile_size = size
        for s, b in self._size_btns.items():
            b.set_css_classes(
                ["album-grid-size-btn", "album-grid-size-active"
                 if s == size else "album-grid-size-btn"])
        self._rebuild_grid()

    def set_sort_alpha(self, enabled):
        """Wird von der Playlist aufgerufen wenn A→Z umgeschaltet wird."""
        self._sort_alpha = enabled
        self._rebuild_grid()

    def _set_size_manual(self, size):
        """Manuell gewählte Größe — Auto-Anpassung deaktivieren."""
        self._auto_size = False
        self._set_size(size)

    def _on_flow_width_changed(self, widget, _param):
        """Wenn Auto-Modus: optimale Kachelgröße an Breite und Albumanzahl anpassen."""
        if not self._auto_size: return
        width = widget.get_width()
        if width < 10: return
        n_albums = max(1, len(self._albums))

        # Wähle größte Größe bei der mind. 3 nebeneinander passen UND mind. 100px
        best = 100
        for _, size in self.SIZES:
            if size < 100: continue          # nie kleiner als 100px
            tiles_per_row = max(1, (width - 4) // (size + 6))
            if tiles_per_row >= 3:
                best = size                  # nimm die größte die noch passt

        # Bei sehr vielen Alben lieber kleiner damit mehr sichtbar sind
        if n_albums > 30 and best > 120:
            best = 120
        elif n_albums > 60 and best > 100:
            best = 100

        if best != self._tile_size:
            self._tile_size = best
            self._update_size_btn_highlight()
            GLib.idle_add(self._rebuild_grid)

    def _update_size_btn_highlight(self):
        for s, b in self._size_btns.items():
            b.set_css_classes(
                ["album-grid-size-btn", "album-grid-size-active"
                 if s == self._tile_size else "album-grid-size-btn"])

    def _rebuild_grid(self):
        # Alle Kacheln entfernen
        while child := self._flow.get_child_at_index(0):
            self._flow.remove(child)
        self._tiles.clear()

        album_keys = sorted(self._albums.keys(), key=str.lower)
        if self._sort_alpha:
            album_keys = sorted(album_keys,
                key=lambda a: (self._albums[a].get("artist","") or "").lower())
        for album in album_keys:
            info   = self._albums[album]
            child  = self._make_tile(album, info)
            self._flow.append(child)
            self._tiles[album] = child
            # Cover asynchron laden
            if info["cover"] is None and album not in self._pending:
                self._pending.add(album)
                first_path = info["paths"][0] if info["paths"] else None
                if first_path:
                    threading.Thread(
                        target=self._load_cover,
                        args=(album, first_path),
                        daemon=True).start()

        # Aktives Album markieren
        if self._active_album:
            self.set_active_album(self._active_album)

    def _make_tile(self, album, info):
        """Erstellt eine Kachel als FlowBoxChild."""
        sz = self._tile_size

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        outer.set_size_request(sz + 8, sz + 34)
        css = "album-tile-active" if album == self._active_album else "album-tile"
        outer.set_css_classes([css])
        outer.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        # Cover-Bild
        cover_box = Gtk.Box()
        cover_box.set_halign(Gtk.Align.CENTER)
        cover_box.set_size_request(sz, sz)

        pixbuf = info.get("cover")
        if pixbuf:
            scaled = pixbuf.scale_simple(sz, sz, GdkPixbuf.InterpType.BILINEAR)
            texture = Gdk.Texture.new_for_pixbuf(scaled)  # type: ignore
            pic = Gtk.Picture.new_for_paintable(texture)
            pic.set_size_request(sz, sz)
            pic.set_content_fit(Gtk.ContentFit.COVER)
        else:
            pic = Gtk.Image.new_from_icon_name("media-optical-symbolic")
            pic.set_pixel_size(sz // 2)
            pic.set_size_request(sz, sz)

        cover_box.append(pic)
        outer.append(cover_box)

        # Bandname (fett, oben)
        artist_lbl = Gtk.Label(label=info.get("artist", ""))
        artist_lbl.set_css_classes(["album-tile-title"])
        artist_lbl.set_halign(Gtk.Align.CENTER)
        artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        artist_lbl.set_max_width_chars(sz // 7 + 2)
        outer.append(artist_lbl)

        # Albumname (gedimmt, unten)
        title_lbl = Gtk.Label(label=album)
        title_lbl.set_css_classes(["album-tile-sub"])
        title_lbl.set_halign(Gtk.Align.CENTER)
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.set_max_width_chars(sz // 7 + 2)
        outer.append(title_lbl)

        # Klick → Callback
        gc = Gtk.GestureClick.new()
        gc.connect("released", lambda g, n, x, y, alb=album:
                   self._on_album_click(alb, self._albums[alb]["paths"]))
        outer.add_controller(gc)

        child = Gtk.FlowBoxChild()
        child.set_child(outer)
        child.set_focusable(False)
        return child

    def _load_cover(self, album, path):
        """Cover aus GStreamer-Tags laden (Hintergrund-Thread)."""
        pixbuf = None
        try:
            uri  = Gst.filename_to_uri(os.path.abspath(path))
            info = GstPbutils.Discoverer.new(3 * Gst.SECOND).discover_uri(uri)
            tags = info.get_audio_streams()[0].get_tags() if info.get_audio_streams() else None
            if not tags:
                stream_list = info.get_stream_list()
                for s in stream_list:
                    tags = s.get_tags()
                    if tags: break
            if tags:
                for itag in (Gst.TAG_IMAGE, Gst.TAG_PREVIEW_IMAGE):
                    ok, sample = tags.get_sample(itag)
                    if ok and sample:
                        buf = sample.get_buffer()
                        ok2, mi = buf.map(Gst.MapFlags.READ)
                        if ok2:
                            try:
                                loader = GdkPixbuf.PixbufLoader()
                                loader.write(bytes(mi.data))
                                loader.close()
                                pixbuf = loader.get_pixbuf()
                            except: pass
                            buf.unmap(mi)
                    if pixbuf: break
            # Fallback: cover.jpg im selben Ordner
            if not pixbuf:
                folder = Path(path).parent
                for fname in ["cover.jpg","cover.png","folder.jpg","folder.png",
                               "Cover.jpg","Cover.png"]:
                    p = folder / fname
                    if p.exists():
                        try: pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(p)); break
                        except: pass
        except: pass

        self._pending.discard(album)
        if pixbuf and album in self._albums:
            self._albums[album]["cover"] = pixbuf
            GLib.idle_add(self._update_tile_cover, album, pixbuf)

    def _update_tile_cover(self, album, pixbuf):
        """Kachel-Cover im GUI-Thread aktualisieren."""
        if album not in self._tiles: return
        child = self._tiles[album]
        outer = child.get_child()
        if not outer: return

        sz      = self._tile_size
        cover_box = outer.get_first_child()  # erstes Kind = cover_box
        if not cover_box: return

        # Altes Bild entfernen
        old = cover_box.get_first_child()
        if old: cover_box.remove(old)

        # Neues Bild einfügen
        scaled = pixbuf.scale_simple(sz, sz, GdkPixbuf.InterpType.BILINEAR)
        texture = Gdk.Texture.new_for_pixbuf(scaled)  # type: ignore
        pic = Gtk.Picture.new_for_paintable(texture)
        pic.set_size_request(sz, sz)
        pic.set_content_fit(Gtk.ContentFit.COVER)
        cover_box.append(pic)
        return False


# ─── Internet Radio ───────────────────────────────────────────────────────────
class RadioPlayer:
    """Radio-Stream-Player mit GStreamer-Tag-Auslese für Song-Benachrichtigungen."""
    def __init__(self):
        self.pl = Gst.ElementFactory.make("playbin", "radio-player")
        self._volume_elem = Gst.ElementFactory.make("volume", "radio-vol")
        self._playing = False
        self.target_vol = 0.8
        self.on_tag = None          # Callback(title, artist) bei Song-Wechsel
        self._last_tag_title = ""

        if self._volume_elem:
            convert = Gst.ElementFactory.make("audioconvert", "radio-convert")
            audio_sink = None
            for name in ["autoaudiosink", "pulsesink", "alsasink"]:
                audio_sink = Gst.ElementFactory.make(name, "radio-sink")
                if audio_sink: break
            if convert and audio_sink:
                bin_ = Gst.Bin.new("radio-audio-bin")
                bin_.add(self._volume_elem); bin_.add(convert); bin_.add(audio_sink)
                self._volume_elem.link(convert); convert.link(audio_sink)
                ghost = Gst.GhostPad.new("sink", self._volume_elem.get_static_pad("sink"))
                bin_.add_pad(ghost)
                self.pl.set_property("audio-sink", bin_)

        bus = self.pl.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_error)
        bus.connect("message::tag",   self._on_tag_msg)

    def play(self, url, vol=0.8):
        self.pl.set_state(Gst.State.NULL)
        self.pl.set_property("uri", url)
        self._last_tag_title = ""
        self.set_vol(vol)
        self.pl.set_state(Gst.State.PLAYING)
        self._playing = True

    def stop(self):
        self.pl.set_state(Gst.State.NULL)
        self._playing = False

    def set_vol(self, v):
        self.target_vol = max(0.0, min(1.5, v))
        if self._volume_elem:
            try: self._volume_elem.set_property("volume", self.target_vol); return
            except: pass
        try: self.pl.set_property("volume", self.target_vol)
        except: pass

    def is_playing(self): return self._playing

    def _on_error(self, bus, msg):
        err, _ = msg.parse_error()
        print(f"Radio-Fehler: {err}")
        self._playing = False

    def _on_tag_msg(self, bus, msg):
        """Liest ICY-Metadaten (Titel/Interpret) aus dem Stream."""
        try:
            taglist = msg.parse_tag()
            title = ""; artist = ""
            ok, v = taglist.get_string(Gst.TAG_TITLE)
            if ok: title = _fix_encoding(v)
            ok, v = taglist.get_string(Gst.TAG_ARTIST)
            if ok: artist = _fix_encoding(v)
            # ICY-Streams liefern oft "Artist - Title" in TAG_TITLE
            if title and " - " in title and not artist:
                parts = title.split(" - ", 1)
                artist, title = parts[0].strip(), parts[1].strip()
            if title and title != self._last_tag_title:
                self._last_tag_title = title
                if self.on_tag:
                    GLib.idle_add(self.on_tag, title, artist)
        except: pass


class RadioPanel(Gtk.Box):
    """Radio-Panel — wird als Reiter in den Haupt-Stack eingebettet."""
    API_BASE = "https://de1.api.radio-browser.info/json"
    _FAV_PATH = Path.home() / ".config" / "helga" / "radio_favorites.json"

    def __init__(self, radio_player, vol_getter, notify_cb):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.radio_player = radio_player
        self.vol_getter   = vol_getter
        self.notify_cb    = notify_cb   # fn(title, station_name)
        self._stations    = []
        self._favorites   = self._load_favorites()
        self._current_uuid = None
        self._current_name = ""
        self._current_url  = ""   # URL des zuletzt gespielten Senders
        self._blink_state  = False
        self._logo_size    = 50   # Standard-Logo-Größe (50x50, aktiver Sender 80x80)

        # Tag-Callback im Player setzen
        self.radio_player.on_tag = self._on_stream_tag

        self._build()
        # Startet Top-100 beim ersten Aufbau
        GLib.timeout_add(300, lambda: self._quick_search(None, "top") or False)
        GLib.timeout_add(900, self._blink_tick)

    def _build(self):
        # ── Suchzeile ─────────────────────────────────────────────
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        top.set_margin_start(12); top.set_margin_end(12)
        top.set_margin_top(10);   top.set_margin_bottom(4)
        self.append(top)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("Sender suchen …")
        self._search.set_hexpand(True)
        self._search.connect("activate", self._do_search)
        search_row.append(self._search)
        go = Gtk.Button(label="Suchen")
        go.add_css_class("suggested-action")
        go.connect("clicked", self._do_search)
        search_row.append(go)
        top.append(search_row)

        # ── Schnellwahl — scrollbare Leiste, im maximierten Fenster mehrreihig ──
        self._quick_scroll = Gtk.ScrolledWindow()
        self._quick_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self._quick_scroll.set_margin_bottom(2)

        self._quick_flowbox = Gtk.FlowBox()
        self._quick_flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._quick_flowbox.set_homogeneous(False)
        self._quick_flowbox.set_row_spacing(4)
        self._quick_flowbox.set_column_spacing(4)
        self._quick_flowbox.set_max_children_per_line(50)
        self._quick_flowbox.set_min_children_per_line(3)

        self._quick_entries = [
            ("🔖 Favoriten",      None,            "fav"),
            ("⭐ Top 100",        None,             "top"),
            ("🎸 Rock",           "rock",           "tag"),
            ("⚡ Metal",          "metal",          "tag"),
            ("🤘 Hard Rock",      "hard rock",      "tag"),
            ("🎵 Pop",            "pop",            "tag"),
            ("🎤 Top 40",         "top 40",         "tag"),
            ("📅 2000er",         "2000s",          "tag"),
            ("📼 90er",           "90s",            "tag"),
            ("📻 80er",           "80s",            "tag"),
            ("🕺 70er",           "70s",            "tag"),
            ("🎷 Jazz",           "jazz",           "tag"),
            ("🎻 Klassik",        "classical",      "tag"),
            ("🌍 World",          "world",          "tag"),
            ("🎧 Electronic",     "electronic",     "tag"),
            ("🏠 House",          "house",          "tag"),
            ("🥁 Techno",         "techno",         "tag"),
            ("🎺 Blues",          "blues",          "tag"),
            ("🤠 Country",        "country",        "tag"),
            ("🎙 Talk",           "talk",           "tag"),
            ("📰 News",           "news",           "tag"),
            ("🇩🇪 Deutsch",       "german",         "lang"),
            ("🇩🇪 Deutsch Rock",  "deutsch rock",   "tag"),
            ("🤘 Wacken Radio",   "wacken",         "name"),
            ("🎸 Classic Rock",   "classic rock",   "tag"),
            ("🎵 Hits",           "hits",           "tag"),
            ("💎 Oldies",         "oldies",         "tag"),
            ("🌙 Schlager",       "schlager",       "tag"),
            ("🎤 Indie",          "indie",          "tag"),
            ("🎸 Alternative",    "alternative",    "tag"),
            ("🎼 Soundtrack",     "soundtrack",     "tag"),
        ]
        for label, query, qtype in self._quick_entries:
            b = Gtk.Button(label=label)
            b.set_css_classes(["radio-quick-btn", "flat"])
            b.connect("clicked", lambda _, q=query, t=qtype: self._quick_search(q, t))
            self._quick_flowbox.append(b)

        self._quick_scroll.set_child(self._quick_flowbox)
        top.append(self._quick_scroll)

        # Scrollbereich: eine Zeile im Normalfall, FlowBox bricht automatisch um
        # wenn mehr Platz da ist (max_children_per_line=50 erlaubt viele pro Zeile)
        self._quick_scroll.set_min_content_height(48)
        self._quick_scroll.set_max_content_height(200)

        # ── Genre-Auswahl: kompakt rechtsbündig ──────────────────
        genre_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        genre_row.set_margin_top(2)

        # Leerraum links damit Dropdown ganz rechts landet
        spacer = Gtk.Label(label="")
        spacer.set_hexpand(True)
        genre_row.append(spacer)

        # Kleines Suchfeld für Genre-Dropdown
        self._genre_search = Gtk.SearchEntry()
        self._genre_search.set_placeholder_text("Genre …")
        self._genre_search.set_size_request(130, -1)
        self._genre_search.connect("search-changed", self._on_genre_search_changed)
        self._genre_search.connect("activate", self._on_genre_search_activate)
        genre_row.append(self._genre_search)

        self._genre_model = Gtk.StringList.new(["— Genre wählen —"])
        self._genre_drop = Gtk.DropDown(model=self._genre_model)
        self._genre_drop.set_size_request(160, -1)
        self._genre_drop.set_tooltip_text("Genre aus Liste wählen")
        self._genre_drop.connect("notify::selected", self._on_genre_selected)
        genre_row.append(self._genre_drop)

        reload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        reload_btn.set_css_classes(["flat"])
        reload_btn.set_tooltip_text("Genre-Liste neu laden")
        reload_btn.connect("clicked", lambda _: self._load_genres())
        genre_row.append(reload_btn)
        top.append(genre_row)

        # Genres beim Start laden
        self._genres_loaded = []      # alle Tags aus API
        self._genres_filtered = []    # nach Suche gefiltert
        GLib.timeout_add(800, lambda: self._load_genres() or False)

        # ── Status ────────────────────────────────────────────────
        self._status_lbl = Gtk.Label(label="")
        self._status_lbl.set_halign(Gtk.Align.START)
        self._status_lbl.set_css_classes(["helga-artist"])
        self._status_lbl.set_margin_start(12)
        self._status_lbl.set_margin_bottom(2)
        self.append(self._status_lbl)

        # ── Senderliste ───────────────────────────────────────────
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        self.append(scroll)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-activated", self._on_row_activated)
        scroll.set_child(self._listbox)

        # ── Now-Playing-Bar ───────────────────────────────────────
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.set_css_classes(["now-playing-bar"])
        bar.set_margin_start(10); bar.set_margin_end(10)
        bar.set_margin_top(6);    bar.set_margin_bottom(8)
        self.append(bar)

        self._live_dot = Gtk.Label(label="")
        self._live_dot.set_css_classes(["radio-live-dot"])
        bar.append(self._live_dot)

        info_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        info_col.set_hexpand(True)
        bar.append(info_col)

        self._now_station = Gtk.Label(label="Kein Sender aktiv")
        self._now_station.set_halign(Gtk.Align.START)
        self._now_station.set_css_classes(["radio-live-label"])
        self._now_station.set_ellipsize(Pango.EllipsizeMode.END)
        info_col.append(self._now_station)

        self._now_song = Gtk.Label(label="")
        self._now_song.set_halign(Gtk.Align.START)
        self._now_song.set_css_classes(["radio-info"])
        self._now_song.set_ellipsize(Pango.EllipsizeMode.END)
        info_col.append(self._now_song)



        # ── Logo-Größen-Buttons ───────────────────────────────────
        sep0 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep0.set_margin_start(4); sep0.set_margin_end(4)
        bar.append(sep0)

        self._logo_size_btns = {}
        for lbl, sz in [("XS", 32), ("S", 50), ("M", 70), ("L", 90)]:
            b = Gtk.Button(label=lbl)
            b.set_css_classes(
                ["album-grid-size-btn", "album-grid-size-active"]
                if sz == self._logo_size else ["album-grid-size-btn"])
            b.set_tooltip_text(f"Logo-Größe {lbl} ({sz}px)")
            b.connect("clicked", lambda _, s=sz: self._set_logo_size(s))
            bar.append(b)
            self._logo_size_btns[sz] = b

        # Lautstärkeregler
        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep.set_margin_start(4); sep.set_margin_end(4)
        bar.append(sep)

        vol_ico = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
        vol_ico.set_opacity(0.7)
        bar.append(vol_ico)

        self._vol_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._vol_scale.set_range(0.0, 1.0)
        self._vol_scale.set_value(self.vol_getter())
        self._vol_scale.set_size_request(110, -1)
        self._vol_scale.set_draw_value(False)
        self._vol_scale.set_tooltip_text("Lautstärke")
        self._vol_scale.connect("value-changed", self._on_vol_changed)
        bar.append(self._vol_scale)

    # ── Genre-Dropdown ────────────────────────────────────────────
    def _load_genres(self):
        self._set_status("Lade Genres …")
        self._api_get(
            "tags?order=stationcount&reverse=true&limit=300&hidebroken=true",
            self._on_genres_loaded)

    def _on_genres_loaded(self, data):
        if not isinstance(data, list): return
        self._genres_loaded = sorted(
            [t["name"] for t in data if t.get("stationcount", 0) >= 5 and t.get("name", "").strip()],
            key=str.lower
        )
        self._genres_filtered = list(self._genres_loaded)
        self._rebuild_genre_dropdown(self._genres_filtered)
        self._set_status(f"{len(self._genres_loaded)} Genres geladen")

    def _rebuild_genre_dropdown(self, tags):
        self._genre_drop.disconnect_by_func(self._on_genre_selected)
        while self._genre_model.get_n_items() > 0:
            self._genre_model.remove(0)
        self._genre_model.append("— Genre wählen —")
        for tag in tags:
            self._genre_model.append(tag.capitalize())
        self._genre_drop.set_selected(0)
        self._genre_drop.connect("notify::selected", self._on_genre_selected)

    def _on_genre_search_changed(self, entry):
        q = entry.get_text().strip().lower()
        if not q:
            self._genres_filtered = list(self._genres_loaded)
        else:
            self._genres_filtered = [t for t in self._genres_loaded if q in t.lower()]
        self._rebuild_genre_dropdown(self._genres_filtered)
        if len(self._genres_filtered) == 1:
            self._genre_drop.set_selected(1)

    def _on_genre_search_activate(self, entry):
        """Enter im Genre-Suchfeld → direkt ersten Treffer laden."""
        if self._genres_filtered:
            tag = self._genres_filtered[0]
            self._set_status(f"Lade {tag.capitalize()} …")
            self._api_get(
                f"stations/search?limit=80&hidebroken=true&tag={urllib.parse.quote(tag)}&order=clickcount&reverse=true",
                self._on_stations)

    def _on_genre_selected(self, drop, _):
        idx = drop.get_selected()
        if idx == 0 or idx > len(self._genres_filtered): return
        tag = self._genres_filtered[idx - 1]
        self._set_status(f"Lade {tag.capitalize()} …")
        self._api_get(
            f"stations/search?limit=80&hidebroken=true&tag={urllib.parse.quote(tag)}&order=clickcount&reverse=true",
            self._on_stations)

    # ── Favoriten ─────────────────────────────────────────────────
    def _load_favorites(self):
        try: return json.loads(self._FAV_PATH.read_text())
        except: return []

    def _save_favorites(self):
        try: self._FAV_PATH.write_text(json.dumps(self._favorites, indent=2))
        except: pass

    def _toggle_fav(self, station):
        uuid = station.get("stationuuid", "")
        if self._is_fav(uuid):
            self._favorites = [s for s in self._favorites if s.get("stationuuid") != uuid]
            return False
        self._favorites.append(station)
        self._save_favorites()
        return True

    def _is_fav(self, uuid):
        return any(s.get("stationuuid") == uuid for s in self._favorites)

    # ── API ───────────────────────────────────────────────────────
    def _api_get(self, path, callback):
        def _fetch():
            try:
                req = urllib.request.Request(
                    f"{self.API_BASE}/{path}",
                    headers={"User-Agent": "Helga Music Player/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = json.loads(r.read().decode())
                GLib.idle_add(callback, data)
            except Exception as e:
                GLib.idle_add(self._set_status, f"Fehler: {e}")
        threading.Thread(target=_fetch, daemon=True).start()

    def _quick_search(self, query, qtype):
        self._set_status("Lade …")
        if qtype == "top":
            self._api_get("stations/search?limit=100&hidebroken=true&order=clickcount&reverse=true",
                          self._on_stations)
        elif qtype == "lang":
            self._api_get(f"stations/search?limit=80&hidebroken=true&language={query}&order=clickcount&reverse=true",
                          self._on_stations)
        elif qtype == "tag":
            self._api_get(f"stations/search?limit=80&hidebroken=true&tag={urllib.parse.quote(query)}&order=clickcount&reverse=true",
                          self._on_stations)
        elif qtype == "name":
            self._api_get(f"stations/search?limit=80&hidebroken=true&name={urllib.parse.quote(query)}&order=clickcount&reverse=true",
                          self._on_stations)
        elif qtype == "fav":
            self._on_stations(self._favorites)

    def _do_search(self, *_):
        q = self._search.get_text().strip()
        if not q: return
        self._set_status("Suche …")
        # Fokus auf Suche behalten damit Eingabe weiterläuft
        self._search.grab_focus()
        self._api_get(
            f"stations/search?limit=60&hidebroken=true&name={urllib.parse.quote(q)}&order=clickcount&reverse=true",
            self._on_stations)

    def _on_stations(self, data):
        self._stations = data if isinstance(data, list) else []
        self._set_status(f"{len(self._stations)} Sender gefunden")
        self._fill_list()

    # ── Liste füllen ──────────────────────────────────────────────
    def _fill_list(self):
        while row := self._listbox.get_row_at_index(0):
            self._listbox.remove(row)

        for s in self._stations:
            uuid    = s.get("stationuuid", "")
            is_live = (uuid == self._current_uuid and self._current_uuid is not None)
            logo_sz = int(self._logo_size * 1.6) if is_live else self._logo_size
            row_pad = 8  if is_live else 5

            row = Gtk.ListBoxRow()
            row.set_tooltip_text(s.get("homepage", ""))
            if is_live:
                if self.radio_player.is_playing():
                    row.set_css_classes(["radio-row-active"])
                else:
                    row.set_css_classes(["radio-row-paused"])

            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            hbox.set_margin_start(8); hbox.set_margin_end(8)
            hbox.set_margin_top(row_pad); hbox.set_margin_bottom(row_pad)
            row.set_child(hbox)

            # ── Sender-Logo ──────────────────────────────────────────
            favicon_url = s.get("favicon", "")
            logo_box = Gtk.Box()
            logo_box.set_size_request(logo_sz, logo_sz)
            logo_box.set_valign(Gtk.Align.CENTER)
            # Platzhalter-Icon sofort setzen
            placeholder = Gtk.Image.new_from_icon_name("audio-x-generic")
            placeholder.set_pixel_size(logo_sz)
            placeholder.set_opacity(0.4)
            logo_box.append(placeholder)
            hbox.append(logo_box)
            # Favicon asynchron laden
            if favicon_url:
                def _load_favicon(url=favicon_url, box=logo_box, sz=logo_sz):
                    def _fetch():
                        try:
                            import urllib.request, tempfile, os as _os
                            with urllib.request.urlopen(url, timeout=4) as r:
                                data = r.read(65536)
                            suffix = ".png" if b"PNG" in data[:8] else ".ico"
                            tmp = tempfile.mktemp(suffix=suffix)
                            open(tmp, "wb").write(data)
                            def _show():
                                try:
                                    pic = Gtk.Picture.new_for_filename(tmp)
                                    pic.set_size_request(sz, sz)
                                    pic.set_content_fit(Gtk.ContentFit.COVER)
                                    # Platzhalter entfernen, Bild einhängen
                                    old = box.get_first_child()
                                    if old: box.remove(old)
                                    box.append(pic)
                                except: pass
                                try: _os.unlink(tmp)
                                except: pass
                                return False
                            GLib.idle_add(_show)
                        except: pass
                    threading.Thread(target=_fetch, daemon=True).start()
                _load_favicon()

            # ── Name + Infos ─────────────────────────────────────────
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info.set_hexpand(True)
            info.set_valign(Gtk.Align.CENTER)

            name_lbl = Gtk.Label(label=s.get("name", "?"))
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_css_classes(["radio-name-active" if is_live else "radio-name"])
            name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            info.append(name_lbl)

            country = s.get("countrycode", "")
            bitrate = s.get("bitrate", 0)
            codec   = s.get("codec", "")
            tags    = (s.get("tags", "") or "")[:50]
            sub     = " · ".join(filter(None, [
                country,
                f"{bitrate} kbps" if bitrate else None,
                codec, tags,
            ]))
            if sub:
                sub_lbl = Gtk.Label(label=sub)
                sub_lbl.set_halign(Gtk.Align.START)
                sub_lbl.set_css_classes(["radio-info"])
                sub_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                info.append(sub_lbl)

            # ▶ bei aktivem Sender
            if is_live:
                live_lbl = Gtk.Label(label="▶  LIVE")
                live_lbl.set_halign(Gtk.Align.START)
                live_lbl.set_css_classes(["radio-live-label"])
                info.append(live_lbl)

            hbox.append(info)

            # ★ Favorit-Button
            fav_btn = Gtk.Button(label="★" if self._is_fav(uuid) else "☆")
            fav_btn.set_css_classes(["flat"])
            fav_btn.set_tooltip_text("Favorit hinzufügen / entfernen")
            fav_btn.connect("clicked", lambda b, st=s: self._on_fav_click(b, st))
            hbox.append(fav_btn)

            self._listbox.append(row)

        # Aktive Zeile ins Sichtfeld scrollen (kein grab_focus — stiehlt sonst Eingabefokus)
        if self._current_uuid:
            for i, s in enumerate(self._stations):
                if s.get("stationuuid") == self._current_uuid:
                    row = self._listbox.get_row_at_index(i)
                    if row:
                        def _scroll(r=row):
                            adj = self._listbox.get_parent().get_vadjustment() if self._listbox.get_parent() else None
                            if adj:
                                alloc = r.get_allocation()
                                adj.set_value(max(0, alloc.y - 40))
                        GLib.idle_add(_scroll)
                    break

    # ── Interaktion ───────────────────────────────────────────────
    def _on_fav_click(self, btn, station):
        now_fav = self._toggle_fav(station)
        btn.set_label("★" if now_fav else "☆")
        self._save_favorites()

    def _on_row_activated(self, listbox, row):
        idx = row.get_index()
        if not (0 <= idx < len(self._stations)): return
        s    = self._stations[idx]
        uuid = s.get("stationuuid", "")

        # Klick auf laufenden Sender = Stop (Toggle)
        if uuid and uuid == self._current_uuid and self.radio_player.is_playing():
            self._stop()
            return

        url = s.get("url_resolved") or s.get("url", "")
        if not url: return

        prev_uuid          = self._current_uuid
        self._current_uuid = uuid
        self._current_name = s.get("name", "?")
        self._current_url  = url
        self.radio_player.play(url, self.vol_getter())

        self._now_station.set_label(self._current_name)
        self._now_song.set_label("")
        self._live_dot.set_label("●")

        # Nur die zwei betroffenen Zeilen neu stylen — kein komplettes Rebuild
        self._update_row_style(prev_uuid, active=False)
        self._update_row_style(self._current_uuid, active=True)

        # API-Etikette: Click melden
        if self._current_uuid:
            self._api_get(f"url/{self._current_uuid}", lambda *_: None)

    def _update_row_style(self, uuid, active):
        """Aktualisiert Styling einer einzelnen Zeile — rebuildet sie komplett
        damit Logo-Größe und ▶ LIVE Label korrekt angezeigt werden."""
        if not uuid: return
        # Einfachster Weg: gesamte Liste neu aufbauen (Logo-Größe ändert sich)
        self._fill_list()

    def _stop(self, *_):
        self.radio_player.stop()
        # uuid + name behalten damit die Markierung erhalten bleibt
        self._live_dot.set_label("⏸")
        self._fill_list()

    def _clear_station(self):
        """Sender komplett abwählen (kein Resume möglich)."""
        self.radio_player.stop()
        self._current_uuid = None
        self._current_name = ""
        self._current_url  = ""
        self._now_station.set_label("Kein Sender aktiv")
        self._now_song.set_label("")
        self._live_dot.set_label("")
        self._fill_list()

    def _set_logo_size(self, size):
        """Setzt die Logo-Größe und baut die Liste neu auf."""
        self._logo_size = size
        for sz, btn in self._logo_size_btns.items():
            btn.set_css_classes(
                ["album-grid-size-btn", "album-grid-size-active"]
                if sz == size else ["album-grid-size-btn"])
        self._fill_list()

    def resume_if_needed(self, vol):
        """Beim Zurückwechseln auf Radio: Sender neu starten falls nicht mehr aktiv."""
        if self._current_url and not self.radio_player.is_playing():
            self.radio_player.play(self._current_url, vol)
            self._now_station.set_label(self._current_name)
            self._live_dot.set_label("●")
            self._fill_list()

    def _on_vol_changed(self, scale):
        vol = scale.get_value()
        self.radio_player.set_vol(vol)

    def set_volume(self, vol):
        """Lautstärke von außen setzen (z.B. Hauptregler)."""
        if hasattr(self, "_vol_scale"):
            self._vol_scale.set_value(vol)
        self.radio_player.set_vol(vol)

    def _set_status(self, text):
        self._status_lbl.set_label(text)

    def _on_stream_tag(self, title, artist):
        """Aufgerufen wenn der Stream einen neuen Song-Titel liefert."""
        display = f"{artist} – {title}" if artist else title
        self._now_song.set_label(display)
        # Benachrichtigung OHNE Ton: -t 0 = kein Timeout, --hint int:transient:1
        self.notify_cb(title, artist or self._current_name)

    def _blink_tick(self):
        if self.radio_player.is_playing():
            self._blink_state = not self._blink_state
            self._live_dot.set_label("●" if self._blink_state else "")
        else:
            self._live_dot.set_label("")
        return True  # immer wiederholen


# ─── Hörbuch / Hörspiel ───────────────────────────────────────────────────────
AB_DATA_PATH = Path.home() / ".config" / "helga" / "audiobooks.json"

class AudiobookLibrary:
    """Verwaltet alle Hörbücher: Metadaten, Fortschritt, Lesezeichen."""
    def __init__(self):
        self._data = {}   # uuid → dict
        self._load()

    def _load(self):
        try: self._data = json.loads(AB_DATA_PATH.read_text())
        except: self._data = {}

    def save(self):
        try:
            AB_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
            # Einträge ohne existierende Dateien bereinigen
            cleaned = {}
            for uuid, book in self._data.items():
                files = book.get("files", [])
                # Buch behalten wenn mind. eine Datei noch existiert
                if any(os.path.exists(f) for f in files):
                    cleaned[uuid] = book
            self._data = cleaned
            AB_DATA_PATH.write_text(json.dumps(self._data, indent=2))
        except Exception as e:
            print(f"Hörbuch-Daten konnten nicht gespeichert werden: {e}")

    def all_books(self):
        return list(self._data.values())

    def get(self, uuid):
        return self._data.get(uuid)

    def add_book(self, uuid, title, author, cover_path, files, total_duration,
                 category="hörbuch", series="", episode=0):
        if uuid not in self._data:
            self._data[uuid] = {
                "uuid": uuid,
                "title": title,
                "author": author,
                "cover_path": cover_path,
                "files": files,
                "total_duration": total_duration,
                "progress": 0.0,
                "current_file": 0,
                "current_pos": 0,
                "done": False,
                "bookmarks": [],
                "last_played": "",
                "category": category,   # "hörbuch" | "hörspiel"
                "series": series,       # z.B. "Die Drei ???"
                "episode": episode,     # Folgennummer (int)
            }
            self.save()
        return self._data[uuid]

    def update_progress(self, uuid, file_idx, pos, total_duration):
        if uuid not in self._data: return
        b = self._data[uuid]
        b["current_file"] = file_idx
        b["current_pos"]  = pos
        b["last_played"]  = datetime.now().isoformat()
        # Gesamtfortschritt berechnen
        files = b.get("files", [])
        if files and total_duration > 0:
            # Einfach: Dateien gleichgewichtet
            per_file = 1.0 / len(files)
            b["progress"] = min(1.0, (file_idx * per_file) + (pos / max(1, total_duration)) * per_file)
        self.save()

    def mark_done(self, uuid, done=True):
        if uuid not in self._data: return
        self._data[uuid]["done"] = done
        if done: self._data[uuid]["progress"] = 1.0
        self.save()

    def add_bookmark(self, uuid, file_idx, pos, note=""):
        if uuid not in self._data: return
        bm = {"file_idx": file_idx, "pos": int(pos), "note": note,
              "time": datetime.now().strftime("%d.%m.%Y %H:%M")}
        self._data[uuid]["bookmarks"].append(bm)
        self.save()
        return bm

    def remove_book(self, uuid):
        if uuid in self._data:
            del self._data[uuid]
            self.save()

    def add_folder(self, folder_path, files, category="hörbuch"):
        """Fügt einen Ordner als neues Hörbuch/Hörspiel hinzu (nur wenn noch nicht bekannt)."""
        for b in self._data.values():
            if b.get("files") and os.path.dirname(b["files"][0]) == folder_path:
                return  # schon vorhanden
            if any(f in (b.get("files") or []) for f in files[:1]):
                return
        import uuid as _uuid
        uid = str(_uuid.uuid4())
        folder_name = os.path.basename(folder_path)
        self.add_book(uid, folder_name, "", "", sorted(files), 0, category=category)
        return uid

    def remove_bookmark(self, uuid, idx):
        if uuid not in self._data: return
        bms = self._data[uuid]["bookmarks"]
        if 0 <= idx < len(bms):
            bms.pop(idx)
            self.save()


def _ab_uuid(files):
    """Stabile UUID aus Dateiliste."""
    key = "|".join(sorted(str(f) for f in files))
    return hashlib.md5(key.encode()).hexdigest()[:16]


def _ab_cover_from_file(path):
    """Extrahiert Cover aus MP3/M4A/M4B via GStreamer Discoverer."""
    try:
        uri  = Gst.filename_to_uri(os.path.abspath(str(path)))
        info = GstPbutils.Discoverer.new(3 * Gst.SECOND).discover_uri(uri)
        tags = info.get_audio_streams()[0].get_tags() if info.get_audio_streams() else None
        if tags:
            ok, sample = tags.get_sample(Gst.TAG_IMAGE)
            if not ok:
                ok, sample = tags.get_sample(Gst.TAG_PREVIEW_IMAGE)
            if ok and sample:
                buf    = sample.get_buffer()
                ok2, mi = buf.map(Gst.MapFlags.READ)
                if ok2:
                    loader = GdkPixbuf.PixbufLoader()
                    loader.write(bytes(mi.data))
                    loader.close()
                    buf.unmap(mi)
                    return loader.get_pixbuf()
    except: pass
    return None


def _ab_chapters_from_file(path):
    """Liest Kapitel-Tags aus M4B/MP3 — erst mutagen, dann GStreamer TOC."""
    chapters = []
    ext = Path(path).suffix.lower()

    # ── Versuch 1: mutagen (zuverlässigeres Encoding) ────────────
    try:
        import mutagen
        f = mutagen.File(path)
        if f is not None:
            # MP3 mit CHAP-Tags (ID3)
            if hasattr(f, 'tags') and f.tags:
                from mutagen.id3 import CHAP
                chap_tags = [v for k, v in f.tags.items() if k.startswith("CHAP")]
                if chap_tags:
                    chap_tags.sort(key=lambda c: c.start_time)
                    for ch in chap_tags:
                        title = "Kapitel"
                        if ch.sub_frames:
                            tit = ch.sub_frames.get("TIT2")
                            if tit: title = _fix_encoding(str(tit))
                        chapters.append({
                            "title": title,
                            "start": ch.start_time / 1000.0,
                            "stop":  ch.end_time  / 1000.0,
                        })
                    if chapters:
                        return chapters
    except Exception:
        pass

    # ── Versuch 2: GStreamer TOC ──────────────────────────────────
    try:
        uri  = Gst.filename_to_uri(os.path.abspath(str(path)))
        info = GstPbutils.Discoverer.new(3 * Gst.SECOND).discover_uri(uri)
        toc = info.get_toc()
        if toc:
            for entry in toc.get_entries():
                start, stop = entry.get_start_stop_times()
                tags = entry.get_tags()
                title = "Kapitel"
                if tags:
                    ok, t = tags.get_string(Gst.TAG_TITLE)
                    if ok: title = _fix_encoding(t)
                chapters.append({"title": title, "start": start / Gst.SECOND, "stop": stop / Gst.SECOND})
    except: pass
    return chapters


class AudiobookPlayerEngine:
    """GStreamer-Player für Hörbücher mit Geschwindigkeitssteuerung."""
    def __init__(self):
        self.pl = Gst.ElementFactory.make("playbin", "ab-player")
        self._vol_elem  = Gst.ElementFactory.make("volume", "ab-vol")
        self._pitch_elem = None
        self._playing   = False
        self.target_vol = 0.8
        self._speed     = 1.0
        self.on_eos     = None
        self.on_pos     = None   # Callback(pos_sec)

        # Audio-Bin mit optionalem Pitch-Element
        convert  = Gst.ElementFactory.make("audioconvert", "ab-conv")
        sink     = None
        for name in ["autoaudiosink","pulsesink","alsasink"]:
            sink = Gst.ElementFactory.make(name, "ab-sink")
            if sink: break

        if self._vol_elem and convert and sink:
            # scaletempo für Geschwindigkeit ohne Tonhöhenänderung
            self._pitch_elem = Gst.ElementFactory.make("scaletempo", "ab-tempo")
            bin_ = Gst.Bin.new("ab-audio-bin")
            if self._pitch_elem:
                bin_.add(self._vol_elem); bin_.add(self._pitch_elem)
                bin_.add(convert); bin_.add(sink)
                self._vol_elem.link(self._pitch_elem)
                self._pitch_elem.link(convert); convert.link(sink)
                ghost = Gst.GhostPad.new("sink", self._vol_elem.get_static_pad("sink"))
            else:
                bin_.add(self._vol_elem); bin_.add(convert); bin_.add(sink)
                self._vol_elem.link(convert); convert.link(sink)
                ghost = Gst.GhostPad.new("sink", self._vol_elem.get_static_pad("sink"))
            bin_.add_pad(ghost)
            self.pl.set_property("audio-sink", bin_)

        bus = self.pl.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos",   self._on_eos)
        bus.connect("message::error", self._on_err)

        GLib.timeout_add(500, self._pos_tick)

    def load(self, path, start_pos=0, vol=0.8):
        self.pl.set_state(Gst.State.NULL)
        uri = Gst.filename_to_uri(os.path.abspath(str(path)))
        self.pl.set_property("uri", uri)
        self.set_vol(vol)
        self.pl.set_state(Gst.State.PLAYING)
        self._playing = True
        if start_pos > 0:
            GLib.timeout_add(400, lambda: self._seek_to(start_pos) or False)
        self._apply_speed()

    def play_pause(self):
        if self._playing:
            self.pl.set_state(Gst.State.PAUSED)
            self._playing = False
        else:
            self.pl.set_state(Gst.State.PLAYING)
            self._playing = True

    def stop(self):
        self.pl.set_state(Gst.State.NULL)
        self._playing = False

    def seek(self, pos_sec):
        self._seek_to(pos_sec)

    def _seek_to(self, pos_sec):
        try:
            self.pl.seek_simple(Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                int(pos_sec * Gst.SECOND))
        except: pass

    def get_pos(self):
        try:
            ok, pos = self.pl.query_position(Gst.Format.TIME)
            return pos / Gst.SECOND if ok else 0
        except: return 0

    def get_duration(self):
        try:
            ok, dur = self.pl.query_duration(Gst.Format.TIME)
            return dur / Gst.SECOND if ok else 0
        except: return 0

    def set_vol(self, v):
        self.target_vol = max(0.0, min(1.5, v))
        if self._vol_elem:
            try: self._vol_elem.set_property("volume", self.target_vol); return
            except: pass
        try: self.pl.set_property("volume", self.target_vol)
        except: pass

    def set_speed(self, speed):
        self._speed = max(0.5, min(3.0, speed))
        self._apply_speed()

    def _apply_speed(self):
        if not self._playing: return
        try:
            pos = self.get_pos()
            self.pl.seek(self._speed,
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                Gst.SeekType.SET, int(pos * Gst.SECOND),
                Gst.SeekType.NONE, 0)
        except: pass

    def is_playing(self): return self._playing

    def _on_eos(self, *_):
        self._playing = False
        if self.on_eos: GLib.idle_add(self.on_eos)

    def _on_err(self, bus, msg):
        err, _ = msg.parse_error()
        print(f"Hörbuch-Fehler: {err}")
        self._playing = False

    def _pos_tick(self):
        if self._playing and self.on_pos:
            self.on_pos(self.get_pos(), self.get_duration())
        return True


class AudiobookShelfItem(Gtk.ListBoxRow):
    """Eine Buchkarte im Regal."""
    def __init__(self, book):
        super().__init__()
        self.book = book
        self._build(book)

    def _build(self, book):
        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        outer.set_margin_start(8); outer.set_margin_end(8)
        outer.set_margin_top(6);   outer.set_margin_bottom(6)

        # Cover — aktiv: 80px, inaktiv: 60px
        is_playing = getattr(self, "is_playing", False)
        csz = 160 if is_playing else 80
        cover_box = Gtk.Box()
        cover_box.set_size_request(csz, csz)
        cover_path = book.get("cover_path", "")
        if cover_path and Path(cover_path).exists():
            self._cover_img = Gtk.Picture()
            self._cover_img.set_size_request(csz, csz)
            self._cover_img.set_content_fit(Gtk.ContentFit.COVER)
            self._cover_img.set_filename(cover_path)
            cover_box.append(self._cover_img)
        else:
            self._cover_img = Gtk.Image.new_from_icon_name("audio-x-generic")
            self._cover_img.set_pixel_size(csz - 16)
            cover_box.append(self._cover_img)
        outer.append(cover_box)

        # Info
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info.set_hexpand(True); info.set_valign(Gtk.Align.CENTER)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        title_lbl = Gtk.Label(label=book.get("title","?"))
        title_lbl.set_halign(Gtk.Align.START)
        title_lbl.set_css_classes(["ab-title"])
        title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        title_lbl.set_hexpand(True)
        title_row.append(title_lbl)

        # Kategorie-Badge
        cat = book.get("category", "hörbuch")
        cat_lbl = Gtk.Label(label="🎭" if cat == "hörspiel" else "📚")
        cat_lbl.set_tooltip_text("Hörspiel" if cat == "hörspiel" else "Hörbuch")
        title_row.append(cat_lbl)

        if book.get("done"):
            done_lbl = Gtk.Label(label="✓")
            done_lbl.set_css_classes(["ab-progress-done"])
            done_lbl.set_tooltip_text("Fertig gehört")
            title_row.append(done_lbl)
        info.append(title_row)

        # Serien-Info wenn vorhanden
        series = book.get("series","")
        episode = book.get("episode", 0)
        if series:
            series_str = series
            if episode: series_str += f"  #{episode}"
            series_lbl = Gtk.Label(label=series_str)
            series_lbl.set_halign(Gtk.Align.START)
            series_lbl.set_css_classes(["ab-author"])
            series_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            info.append(series_lbl)
        elif book.get("author",""):
            author_lbl = Gtk.Label(label=book.get("author",""))
            author_lbl.set_halign(Gtk.Align.START)
            author_lbl.set_css_classes(["ab-author"])
            info.append(author_lbl)

        # Fortschrittsbalken
        prog = book.get("progress", 0.0)
        pb = Gtk.ProgressBar()
        pb.set_fraction(prog)
        pb.set_margin_top(2)
        info.append(pb)

        prog_lbl = Gtk.Label(label=f"{int(prog*100)}% gehört")
        prog_lbl.set_halign(Gtk.Align.START)
        prog_lbl.set_css_classes(["ab-author"])
        info.append(prog_lbl)

        outer.append(info)

        # Löschen-Button (Papierkorb) oder Checkbox im Multi-Modus
        multi   = getattr(self, "multi_mode",  False)
        checked = getattr(self, "is_selected", False)
        if multi:
            del_btn = Gtk.CheckButton()
            del_btn.set_active(checked)
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text("Zum Löschen markieren")
            del_btn.connect("toggled", lambda b: self._on_delete_clicked(b))
        else:
            del_btn = Gtk.Button(icon_name="user-trash-symbolic")
            del_btn.set_css_classes(["flat"])
            del_btn.set_opacity(0.5)
            del_btn.set_valign(Gtk.Align.CENTER)
            del_btn.set_tooltip_text("Aus Bibliothek entfernen")
            del_btn.connect("clicked", self._on_delete_clicked)
        outer.append(del_btn)

        if book.get("done"):
            self.set_css_classes(["ab-shelf-done"])
        else:
            self.set_css_classes([])

        self.set_child(outer)

    def _on_delete_clicked(self, btn):
        self._delete_triggered = True   # Flag: Row-Click soll ignorieren
        if callable(getattr(self, "on_delete", None)):
            self.on_delete(self.book["uuid"])

    def refresh(self, book):
        self.book = book
        child = self.get_child()
        if child: self.set_child(None)
        self._build(book)


class AudiobookPanel(Gtk.Box):
    """Hauptpanel für Hörbücher/Hörspiele: Regal oben, Player-Bar unten."""
    def __init__(self, ab_player, ab_lib, vol_getter, config=None, save_config_cb=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.ab_player      = ab_player
        self.ab_lib         = ab_lib
        self.vol_getter     = vol_getter
        self.config         = config or {}
        self._save_config   = save_config_cb or (lambda: None)
        self._current_book     = None
        self._current_file_idx = 0
        self._chapters  = []
        self._shelf_rows = []
        self._ab_scan_timer_id = None
        self._on_title_change  = None   # Callback → Hauptfenster setzt Fenstertitel
        self.cover_downloader  = CoverDownloader()

        ab_player.on_eos = self._on_eos
        ab_player.on_pos = self._on_pos

        self._build()
        self._schedule_ab_scan()

    def _build(self):
        # ══════════════════════════════════════════════════════════
        # TOOLBAR: BIBLIOTHEK-Label links, Buttons rechts — volle Breite
        # ══════════════════════════════════════════════════════════
        shelf_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        shelf_header.set_margin_start(10); shelf_header.set_margin_end(4)
        shelf_header.set_margin_top(8);    shelf_header.set_margin_bottom(4)

        shelf_lbl = Gtk.Label(label="BIBLIOTHEK")
        shelf_lbl.set_css_classes(["section-label"])
        shelf_lbl.set_hexpand(True)
        shelf_lbl.set_halign(Gtk.Align.START)
        shelf_header.append(shelf_lbl)

        # Buttons rechtsbündig — Datei | Ordner | Scan | Löschen
        add_file_btn = Gtk.Button(icon_name="document-open-symbolic")
        add_file_btn.set_css_classes(["flat"])
        add_file_btn.set_tooltip_text("Hörbuch-Datei(en) hinzufügen")
        add_file_btn.connect("clicked", self._add_files)
        shelf_header.append(add_file_btn)

        add_folder_btn = Gtk.Button(icon_name="folder-open-symbolic")
        add_folder_btn.set_css_classes(["flat"])
        add_folder_btn.set_tooltip_text("Ordner als Hörbuch/Hörspiel hinzufügen")
        add_folder_btn.connect("clicked", self._add_folder)
        shelf_header.append(add_folder_btn)

        ab_scan_btn = Gtk.Button(icon_name="folder-visiting-symbolic")
        ab_scan_btn.set_css_classes(["flat"])
        ab_scan_btn.set_tooltip_text("Hörbuch-Ordner jetzt scannen")
        ab_scan_btn.connect("clicked", lambda *_: self._do_ab_scan())
        shelf_header.append(ab_scan_btn)

        sep_hdr = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_hdr.set_margin_start(4); sep_hdr.set_margin_end(4)
        sep_hdr.set_margin_top(6);   sep_hdr.set_margin_bottom(6)
        shelf_header.append(sep_hdr)

        # Mehrfach-Löschen Toggle
        self._multi_del_btn = Gtk.ToggleButton(icon_name="user-trash-symbolic")
        self._multi_del_btn.set_css_classes(["flat"])
        self._multi_del_btn.set_tooltip_text("Mehrere löschen")
        self._multi_del_btn.connect("toggled", self._toggle_multi_delete)
        shelf_header.append(self._multi_del_btn)

        # „Ausgewählte löschen"-Button (nur im Multi-Modus sichtbar)
        self._confirm_del_btn = Gtk.Button(label="Löschen")
        self._confirm_del_btn.set_css_classes(["destructive-action"])
        self._confirm_del_btn.set_tooltip_text("Ausgewählte Einträge löschen")
        self._confirm_del_btn.set_visible(False)
        self._confirm_del_btn.connect("clicked", self._delete_selected)
        shelf_header.append(self._confirm_del_btn)

        self._multi_delete_mode = False
        self._delete_candidates  = set()
        self.append(shelf_header)

        # ══════════════════════════════════════════════════════════
        # HAUPTBEREICH: Regal links + Detail rechts (Paned)
        # ══════════════════════════════════════════════════════════
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_vexpand(True)
        paned.set_position(220)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        self.append(paned)

        # ── Linke Seite: Bibliothek ────────────────────────────────
        shelf_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        shelf_box.set_size_request(180, -1)

        # Tabs: Hörbuch | Hörspiel
        tab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_row.set_margin_start(8); tab_row.set_margin_end(8)
        tab_row.set_margin_bottom(4)
        self._filter_mode = "hörbuch"
        for label, mode in [("📚 Hörbuch", "hörbuch"), ("🎭 Hörspiel", "hörspiel")]:
            b = Gtk.Button(label=label)
            b.set_css_classes(["ab-filter-btn-active"] if mode == "hörbuch" else ["ab-filter-btn", "flat"])
            b.set_hexpand(True)
            b.connect("clicked", lambda _, m=mode: self._set_filter(m))
            tab_row.append(b)
            setattr(self, f"_filter_btn_{mode}", b)
        shelf_box.append(tab_row)

        # Suchfeld
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        search_row.set_margin_start(8); search_row.set_margin_end(8)
        search_row.set_margin_bottom(6)
        self._shelf_search = Gtk.SearchEntry()
        self._shelf_search.set_placeholder_text("Suchen …")
        self._shelf_search.set_hexpand(True)
        self._shelf_search.connect("search-changed", lambda *_: self._refresh_shelf())
        search_row.append(self._shelf_search)
        shelf_box.append(search_row)

        scroll_shelf = Gtk.ScrolledWindow(); scroll_shelf.set_vexpand(True)
        self._shelf_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scroll_shelf.set_child(self._shelf_list)
        shelf_box.append(scroll_shelf)
        paned.set_start_child(shelf_box)

        # ── Rechte Seite: Cover + Kapitel + Lesezeichen ───────────
        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        detail_box.set_margin_start(12); detail_box.set_margin_end(12)
        detail_box.set_margin_top(10);   detail_box.set_margin_bottom(6)

        # Cover links, Meta rechts — feste Reihenfolge ohne prepend
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        top_row.set_hexpand(True)
        top_row.set_vexpand(False)
        top_row.set_valign(Gtk.Align.START)
        detail_box.append(top_row)

        # ── Cover (links, fest 80×80px) ───────────────────────────
        cover_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        cover_col.set_valign(Gtk.Align.START)
        cover_col.set_halign(Gtk.Align.START)
        cover_col.set_hexpand(False)
        cover_col.set_vexpand(False)
        cover_col.set_size_request(90, -1)   # feste Mindestbreite verhindert Verschiebung
        top_row.append(cover_col)

        meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        meta_box.set_hexpand(True)
        meta_box.set_vexpand(False)
        meta_box.set_valign(Gtk.Align.CENTER)
        top_row.append(meta_box)

        # Cover als Gtk.Image — garantiert feste 80×80px
        self._cover_img_widget = Gtk.Image.new_from_icon_name("audio-x-generic")
        self._cover_img_widget.set_pixel_size(64)
        self._cover_img_widget.set_size_request(80, 80)
        self._cover_img_widget.set_halign(Gtk.Align.START)
        self._cover_img_widget.set_valign(Gtk.Align.START)
        self._cover_img_widget.set_hexpand(False)
        self._cover_img_widget.set_vexpand(False)
        self._cover_img_widget.set_overflow(Gtk.Overflow.HIDDEN)
        cover_col.append(self._cover_img_widget)

        # Cover-Buttons
        cover_btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        cover_btn_row.set_halign(Gtk.Align.CENTER)
        pick_cover_btn = Gtk.Button(icon_name="image-x-generic-symbolic")
        pick_cover_btn.set_css_classes(["flat"])
        pick_cover_btn.set_tooltip_text("Cover manuell auswählen")
        pick_cover_btn.connect("clicked", self._pick_cover)
        cover_btn_row.append(pick_cover_btn)

        search_cover_btn = Gtk.Button(icon_name="system-search-symbolic")
        search_cover_btn.set_css_classes(["flat"])
        search_cover_btn.set_tooltip_text("Cover online suchen")
        search_cover_btn.connect("clicked", self._search_cover_manual)
        cover_btn_row.append(search_cover_btn)
        cover_col.append(cover_btn_row)

        self._title_lbl = Gtk.Label(label="Kein Buch ausgewählt")
        self._title_lbl.set_halign(Gtk.Align.START)
        self._title_lbl.set_css_classes(["ab-title"])
        self._title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        meta_box.append(self._title_lbl)

        self._author_lbl = Gtk.Label(label="")
        self._author_lbl.set_halign(Gtk.Align.START)
        self._author_lbl.set_css_classes(["ab-author"])
        meta_box.append(self._author_lbl)

        self._file_lbl = Gtk.Label(label="")
        self._file_lbl.set_halign(Gtk.Align.START)
        self._file_lbl.set_css_classes(["ab-author"])
        meta_box.append(self._file_lbl)

        self._total_pb = Gtk.ProgressBar()
        self._total_pb.set_margin_top(4)
        self._total_pb.set_tooltip_text("Gesamtfortschritt")
        meta_box.append(self._total_pb)

        # Kapitel + Lesezeichen nebeneinander
        lower_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        lower_paned.set_vexpand(True)
        lower_paned.set_position(99999)   # wird nach realize auf 75% gesetzt
        lower_paned.set_shrink_start_child(False)
        lower_paned.set_shrink_end_child(True)
        detail_box.append(lower_paned)
        self._lower_paned = lower_paned

        # Position nach erstem Rendern auf 75% Kapitel / 25% Lesezeichen setzen
        def _init_paned_pos(*_):
            w = lower_paned.get_width()
            if w > 50:
                lower_paned.set_position(int(w * 0.75))
                return False   # einmalig
            return True        # nochmal versuchen
        lower_paned.connect("realize", lambda *_: GLib.idle_add(_init_paned_pos))

        # Kapitel
        chap_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        chap_lbl = Gtk.Label(label="KAPITEL"); chap_lbl.set_css_classes(["section-label"])
        chap_lbl.set_halign(Gtk.Align.START)
        chap_box.append(chap_lbl)
        chap_scroll = Gtk.ScrolledWindow(); chap_scroll.set_vexpand(True)
        self._chap_list = Gtk.ListBox()
        self._chap_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._chap_list.connect("row-activated", self._on_chapter_activated)
        chap_scroll.set_child(self._chap_list)
        chap_box.append(chap_scroll)
        lower_paned.set_start_child(chap_box)

        # Lesezeichen
        bm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bm_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bm_lbl = Gtk.Label(label="LESEZEICHEN"); bm_lbl.set_css_classes(["section-label"])
        bm_lbl.set_hexpand(True); bm_lbl.set_halign(Gtk.Align.START)
        bm_header.append(bm_lbl)
        add_bm_btn = Gtk.Button(icon_name="bookmark-new-symbolic")
        add_bm_btn.set_css_classes(["flat"])
        add_bm_btn.set_tooltip_text("Lesezeichen setzen")
        add_bm_btn.connect("clicked", self._add_bookmark_dialog)
        bm_header.append(add_bm_btn)
        bm_box.append(bm_header)
        bm_scroll = Gtk.ScrolledWindow(); bm_scroll.set_vexpand(True)
        self._bm_list = Gtk.ListBox()
        self._bm_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._bm_list.connect("row-activated", self._on_bm_activated)
        bm_scroll.set_child(self._bm_list)
        bm_box.append(bm_scroll)

        # Nachschlagen
        lookup_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lookup_row.set_margin_top(4)
        self._lookup_entry = Gtk.Entry()
        self._lookup_entry.set_placeholder_text("Begriff nachschlagen …")
        self._lookup_entry.set_hexpand(True)
        self._lookup_entry.connect("activate", self._do_lookup)
        lookup_row.append(self._lookup_entry)
        for icon, tip, cb in [
            ("applications-internet",  "Web-Suche",    lambda *_: self._lookup("web")),
            ("accessories-dictionary", "DeepL-Übersetzung", lambda *_: self._lookup("translate")),
        ]:
            b = Gtk.Button(icon_name=icon); b.set_css_classes(["flat"])
            b.set_tooltip_text(tip); b.connect("clicked", cb); lookup_row.append(b)
        bm_box.append(lookup_row)
        lower_paned.set_end_child(bm_box)

        paned.set_end_child(detail_box)

        # ══════════════════════════════════════════════════════════
        # UNTERER BEREICH: Player-Bar (fest, wie Musik-Tab)
        # ══════════════════════════════════════════════════════════
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.append(sep)

        player_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        player_bar.set_margin_start(14); player_bar.set_margin_end(14)
        player_bar.set_margin_top(8);    player_bar.set_margin_bottom(10)
        self.append(player_bar)

        # Geschwindigkeit
        speed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        speed_lbl = Gtk.Label(label="TEMPO"); speed_lbl.set_css_classes(["section-label"])
        speed_row.append(speed_lbl)
        self._speed_btns = []
        for spd in [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]:
            b = Gtk.Button(label=f"{spd}×")
            b.set_css_classes(["ab-speed-btn", "flat"])
            b.connect("clicked", lambda _, s=spd: self._set_speed(s))
            speed_row.append(b); self._speed_btns.append((spd, b))
        player_bar.append(speed_row)
        self._current_speed = 1.0
        self._update_speed_btns(1.0)

        # Fortschrittsbalken — vollständig draggable + klickbar
        self._prog_bar = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._prog_bar.set_range(0, 1); self._prog_bar.set_value(0)
        self._prog_bar.set_hexpand(True); self._prog_bar.set_draw_value(False)
        self._prog_bar.set_tooltip_text("Klicken oder ziehen zum Springen")
        self._seeking = False

        # GTK4: GestureClick für Mausknopf-Events
        _gc = Gtk.GestureClick.new()
        _gc.connect("pressed",  lambda *_: setattr(self, "_seeking", True))
        _gc.connect("released", lambda g, n, x, y: self._on_scale_release())
        self._prog_bar.add_controller(_gc)

        # Drag-Geste für live-Update während Ziehen
        _gd = Gtk.GestureDrag.new()
        _gd.connect("drag-begin",  lambda *_: setattr(self, "_seeking", True))
        _gd.connect("drag-end",    lambda *_: self._on_scale_release())
        self._prog_bar.add_controller(_gd)

        self._prog_bar.connect("value-changed", self._on_scale_drag)
        player_bar.append(self._prog_bar)

        time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._pos_lbl = Gtk.Label(label="0:00", halign=Gtk.Align.START, hexpand=True)
        self._dur_lbl = Gtk.Label(label="0:00", halign=Gtk.Align.END)
        for l in (self._pos_lbl, self._dur_lbl): l.set_css_classes(["helga-time"])
        time_row.append(self._pos_lbl); time_row.append(self._dur_lbl)
        player_bar.append(time_row)

        # Steuer-Buttons
        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ctrl.set_halign(Gtk.Align.CENTER)
        player_bar.append(ctrl)

        for icon, tip, cb in [
            ("media-skip-backward", "Vorheriges Kapitel/Datei", self._prev_chapter),
            ("media-seek-backward", "30 Sek. zurück",           lambda *_: self._skip(-30)),
        ]:
            b = Gtk.Button(icon_name=icon); b.set_css_classes(["flat","ctrl-btn"])
            b.set_tooltip_text(tip); b.connect("clicked", cb); ctrl.append(b)

        self._play_btn = Gtk.Button(icon_name="media-playback-start")
        self._play_btn.set_css_classes(["ctrl-btn-primary"])
        self._play_btn.connect("clicked", self._play_pause)
        ctrl.append(self._play_btn)

        for icon, tip, cb in [
            ("media-seek-forward",      "30 Sek. vor",            lambda *_: self._skip(30)),
            ("media-skip-forward",      "Nächstes Kapitel/Datei", self._next_chapter),
            ("emblem-default-symbolic", "Als fertig markieren",   self._toggle_done),
        ]:
            b = Gtk.Button(icon_name=icon); b.set_css_classes(["flat","ctrl-btn"])
            b.set_tooltip_text(tip); b.connect("clicked", cb); ctrl.append(b)

        # Lautstärkeregler
        vol_sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        vol_sep.set_margin_start(8); vol_sep.set_margin_end(4)
        ctrl.append(vol_sep)
        vol_ico = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
        vol_ico.set_opacity(0.7); ctrl.append(vol_ico)
        self._ab_vol_scale = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL)
        self._ab_vol_scale.set_range(0.0, 1.0)
        self._ab_vol_scale.set_value(self.vol_getter())
        self._ab_vol_scale.set_size_request(110, -1)
        self._ab_vol_scale.set_draw_value(False)
        self._ab_vol_scale.set_tooltip_text("Lautstärke")
        self._ab_vol_scale.connect("value-changed",
            lambda s: self.ab_player.set_vol(s.get_value()))
        ctrl.append(self._ab_vol_scale)

        # Regal füllen
        self._refresh_shelf()

    # ── Regal ──────────────────────────────────────────────────────
    def _attach_row_click(self, item, book):
        """Row-Klick — prüft ob Button-Klick bereits verarbeitet wurde."""
        gc = Gtk.GestureClick.new()
        gc.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        def _on_released(g, n, x, y, bk=book):
            if getattr(item, "_delete_triggered", False):
                item._delete_triggered = False
                return
            self._on_row_click(bk)
        gc.connect("released", _on_released)
        item.add_controller(gc)

    def _on_row_click(self, book):
        if self._multi_delete_mode:
            self._toggle_delete_candidate(book["uuid"])
        else:
            self._load_book(book)

    # ── Auto-Scan ──────────────────────────────────────────────────
    def _schedule_ab_scan(self):
        """Startet/neu-startet den Hörbuch-Auto-Scan-Timer."""
        if self._ab_scan_timer_id:
            GLib.source_remove(self._ab_scan_timer_id)
            self._ab_scan_timer_id = None
        if self.config.get("ab_auto_scan", True):
            interval_ms = int(self.config.get("ab_scan_interval_min", 15) * 60 * 1000)
            self._ab_scan_timer_id = GLib.timeout_add(interval_ms, self._ab_scan_tick)
            GLib.timeout_add(4000, self._ab_scan_once)  # Einmal beim Start

    def _ab_scan_once(self):
        self._do_ab_scan(); return False

    def _ab_scan_tick(self):
        self._do_ab_scan(); return True

    def _do_ab_scan(self):
        """Scannt Hörbuch- und Hörspiel-Ordner getrennt.
        Unterordner = je ein Buch. Category wird aus dem Quell-Ordner abgeleitet.
        """
        if not self.config.get("ab_auto_scan", True): return
        # Ordner-Paare: (pfad, category)
        scan_dirs = []
        for d in self.config.get("ab_dirs", []):
            scan_dirs.append((d, "hörbuch"))
        hs_dir = self.config.get("hoerspiel_dir", "")
        if hs_dir:
            scan_dirs.append((hs_dir, "hörspiel"))
        if not scan_dirs: return
        existing_files = set()
        for book in self.ab_lib.all_books():
            existing_files.update(book.get("files", []))
        def _scan():
            new_by_folder = {}  # folder_path → (files, category)
            for folder_path, cat in scan_dirs:
                if not os.path.isdir(folder_path): continue
                try:
                    entries = sorted(os.scandir(folder_path), key=lambda e: e.name.lower())
                except PermissionError:
                    continue
                for entry in entries:
                    if not entry.is_dir(): continue
                    files = []
                    for root, subdirs, names in os.walk(entry.path):
                        subdirs.sort()
                        for n in sorted(names):
                            if any(n.lower().endswith(e) for e in SUPPORTED):
                                p = os.path.join(root, n)
                                if p not in existing_files:
                                    files.append(p)
                    if files:
                        new_by_folder[entry.path] = (files, cat)
                # Dateien direkt im Stammordner
                direct_files = [
                    os.path.join(folder_path, n)
                    for n in sorted(os.listdir(folder_path))
                    if any(n.lower().endswith(e) for e in SUPPORTED)
                    and os.path.join(folder_path, n) not in existing_files
                ]
                if direct_files:
                    new_by_folder[folder_path] = (direct_files, cat)
            if new_by_folder:
                GLib.idle_add(self._ab_scan_add_new, new_by_folder)
        threading.Thread(target=_scan, daemon=True).start()

    def _ab_scan_add_new(self, new_by_folder):
        """Fügt neue Hörbuch/Hörspiel-Ordner zur Bibliothek hinzu und
        entfernt Einträge deren Dateien nicht mehr existieren."""
        for folder_path, (files, category) in new_by_folder.items():
            self.ab_lib.add_folder(folder_path, files, category=category)
        # Einträge mit fehlenden Dateien entfernen
        to_remove = []
        for book in self.ab_lib.all_books():
            files = book.get("files", [])
            if files and not any(os.path.exists(f) for f in files):
                to_remove.append(book["uuid"])
        for uid in to_remove:
            self.ab_lib.remove_book(uid)
            print(f"Auto-Scan: Hörbuch entfernt (Dateien fehlen): {uid}")
        self._refresh_shelf()
        return False

    def update_scan_config(self, config):
        """Wird vom Hauptfenster nach Settings-Speichern aufgerufen."""
        self.config = config
        self._schedule_ab_scan()

    def _remove_book(self, uuid):
        """Einzelnes Buch mit Bestätigungsdialog löschen."""
        book = self.ab_lib.get(uuid)
        if not book: return
        bm_count = len(book.get("bookmarks", []))
        bm_hint  = (f"\n\n⚠ {bm_count} Lesezeichen {'wird' if bm_count==1 else 'werden'} "
                    f"ebenfalls gelöscht.") if bm_count else ""
        dlg = Gtk.Dialog(title="Eintrag entfernen?", transient_for=self.get_root(), modal=True)
        dlg.set_default_size(380, -1)
        area = dlg.get_content_area()
        area.set_spacing(8); area.set_margin_start(18); area.set_margin_end(18)
        area.set_margin_top(16); area.set_margin_bottom(10)
        title_lbl = Gtk.Label()
        title_lbl.set_markup(f"<b>{GLib.markup_escape_text(book.get('title',''))}</b> entfernen?")
        title_lbl.set_halign(Gtk.Align.START); title_lbl.set_wrap(True)
        area.append(title_lbl)
        secondary = ("Der Eintrag wird aus der Bibliothek gelöscht. "
                     "Die Audiodateien bleiben auf der Festplatte erhalten." + bm_hint)
        sec_lbl = Gtk.Label(label=secondary)
        sec_lbl.set_halign(Gtk.Align.START); sec_lbl.set_wrap(True)
        sec_lbl.set_opacity(0.75); sec_lbl.set_margin_top(4)
        area.append(sec_lbl)
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END); btn_row.set_margin_top(12)
        cancel_b = Gtk.Button(label="Abbrechen"); cancel_b.connect("clicked", lambda *_: dlg.response(Gtk.ResponseType.CANCEL))
        del_b = Gtk.Button(label="Entfernen"); del_b.add_css_class("destructive-action")
        del_b.connect("clicked", lambda *_: dlg.response(Gtk.ResponseType.YES))
        btn_row.append(cancel_b); btn_row.append(del_b)
        area.append(btn_row)
        def _on_resp(d, r):
            if r == Gtk.ResponseType.YES:
                self.ab_lib.remove_book(uuid)
                if self._current_book and self._current_book.get("uuid") == uuid:
                    self._current_book = None
                self._refresh_shelf()
            d.destroy()
        dlg.connect("response", _on_resp)
        dlg.present()

    def _toggle_multi_delete(self, btn):
        """Mehrfach-Lösch-Modus ein-/ausschalten."""
        self._multi_delete_mode = btn.get_active()
        self._delete_candidates.clear()
        self._confirm_del_btn.set_visible(self._multi_delete_mode)
        if self._multi_delete_mode:
            self._multi_del_btn.set_css_classes(["flat", "active-toggle"])
            self._multi_del_btn.set_tooltip_text("Auswahl abbrechen")
        else:
            self._multi_del_btn.set_css_classes(["flat"])
            self._multi_del_btn.set_tooltip_text("Mehrere löschen")
        self._refresh_shelf()

    def _toggle_delete_candidate(self, uuid):
        """UUID zur Lösch-Auswahl hinzufügen oder entfernen."""
        if uuid in self._delete_candidates:
            self._delete_candidates.discard(uuid)
        else:
            self._delete_candidates.add(uuid)
        n = len(self._delete_candidates)
        self._confirm_del_btn.set_label(
            f"{n} löschen" if n > 0 else "Löschen")
        self._confirm_del_btn.set_sensitive(n > 0)
        self._refresh_shelf()

    def _delete_selected(self, *_):
        """Alle markierten Bücher nach Bestätigung löschen."""
        if not self._delete_candidates: return
        uuids  = list(self._delete_candidates)
        titles = [self.ab_lib.get(u).get("title","?")
                  for u in uuids if self.ab_lib.get(u)]
        total_bm = sum(len((self.ab_lib.get(u) or {}).get("bookmarks",[]))
                       for u in uuids)
        bm_hint = (f"\n\n⚠ Insgesamt {total_bm} Lesezeichen "
                   f"{'wird' if total_bm==1 else 'werden'} ebenfalls gelöscht."
                   ) if total_bm else ""
        names = "\n".join(f"• {t}" for t in titles[:8])
        if len(titles) > 8: names += f"\n… und {len(titles)-8} weitere"
        dlg = Gtk.Dialog(title=f"{len(uuids)} Einträge entfernen?", transient_for=self.get_root(), modal=True)
        dlg.set_default_size(420, -1)
        area = dlg.get_content_area()
        area.set_spacing(8); area.set_margin_start(18); area.set_margin_end(18)
        area.set_margin_top(16); area.set_margin_bottom(10)
        title_lbl = Gtk.Label()
        title_lbl.set_markup(f"<b>{len(uuids)} Einträge</b> aus der Bibliothek entfernen?")
        title_lbl.set_halign(Gtk.Align.START)
        area.append(title_lbl)
        body = names + "\n\nDie Audiodateien bleiben auf der Festplatte." + bm_hint
        body_lbl = Gtk.Label(label=body)
        body_lbl.set_halign(Gtk.Align.START); body_lbl.set_wrap(True)
        body_lbl.set_opacity(0.75); body_lbl.set_margin_top(4)
        area.append(body_lbl)
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END); btn_row.set_margin_top(12)
        cancel_b = Gtk.Button(label="Abbrechen"); cancel_b.connect("clicked", lambda *_: dlg.response(Gtk.ResponseType.CANCEL))
        del_b = Gtk.Button(label="Alle entfernen"); del_b.add_css_class("destructive-action")
        del_b.connect("clicked", lambda *_: dlg.response(Gtk.ResponseType.YES))
        btn_row.append(cancel_b); btn_row.append(del_b)
        area.append(btn_row)
        def _on_resp(d, r):
            if r == Gtk.ResponseType.YES:
                for u in uuids:
                    self.ab_lib.remove_book(u)
                    if self._current_book and self._current_book.get("uuid") == u:
                        self._current_book = None
                self._delete_candidates.clear()
                self._multi_del_btn.set_active(False)   # Modus beenden
                self._refresh_shelf()
            d.destroy()
        dlg.connect("response", _on_resp)
        dlg.present()

    def _set_filter(self, mode):
        self._filter_mode = mode
        for m in ["hörbuch", "hörspiel"]:
            btn = getattr(self, f"_filter_btn_{m}", None)
            if btn:
                btn.set_css_classes(["ab-filter-btn-active"] if m == mode
                                    else ["ab-filter-btn", "flat"])
        self._refresh_shelf()

    def _refresh_shelf(self):
        # Alle Kinder entfernen
        child = self._shelf_list.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self._shelf_list.remove(child)
            child = nxt
        self._shelf_rows.clear()

        q    = self._shelf_search.get_text().strip().lower() if hasattr(self, '_shelf_search') else ""
        mode = getattr(self, '_filter_mode', 'alle')

        def _matches(b):
            if q and q not in (b.get("title","") + b.get("author","")).lower():
                return False
            # Immer nach category filtern (Tab bestimmt was angezeigt wird)
            if b.get("category", "hörbuch") != mode:
                return False
            return True

        books = [b for b in self.ab_lib.all_books() if _matches(b)]

        def _add_book_row(b):
            """Erstellt eine Row als Overlay: unsichtbarer Select-Button + sichtbarer Trash-Button."""
            overlay = Gtk.Overlay()

            # Hintergrund-Button für Buchauswahl (volle Fläche, unsichtbar)
            sel_btn = Gtk.Button()
            sel_btn.set_has_frame(False)

            # Farbliche Markierung: aktiv spielend > ausgewählt zum Löschen > normal
            is_playing = (self._current_book and
                          self._current_book.get("uuid") == b["uuid"])
            is_selected = b["uuid"] in self._delete_candidates
            if is_selected:
                sel_btn.set_css_classes(["ab-shelf-selected"])
            elif is_playing:
                sel_btn.set_css_classes(["ab-shelf-playing"])
            else:
                sel_btn.set_css_classes(["flat"])

            # Item-Inhalt
            item = AudiobookShelfItem(b)
            item.multi_mode  = self._multi_delete_mode
            item.is_selected = is_selected
            item.is_playing  = is_playing
            sel_btn.set_child(item)

            if self._multi_delete_mode:
                sel_btn.connect("clicked", lambda *_, bk=b: self._toggle_delete_candidate(bk["uuid"]))
            else:
                sel_btn.connect("clicked", lambda *_, bk=b: self._load_book(bk))

            overlay.set_child(sel_btn)

            # Papierkorb-Button oben rechts im Overlay (immer klickbar)
            trash_btn = Gtk.Button(icon_name="user-trash-symbolic")
            trash_btn.set_css_classes(["flat"])
            trash_btn.set_opacity(0.55)
            trash_btn.set_valign(Gtk.Align.CENTER)
            trash_btn.set_halign(Gtk.Align.END)
            trash_btn.set_margin_end(8)
            trash_btn.set_tooltip_text("Aus Bibliothek entfernen")
            trash_btn.connect("clicked", lambda *_, uid=b["uuid"]: self._remove_book(uid))
            overlay.add_overlay(trash_btn)

            # Trennlinie
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            sep.set_opacity(0.2)

            wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            wrapper.append(overlay)
            wrapper.append(sep)
            self._shelf_list.append(wrapper)
            self._shelf_rows.append(sel_btn)

        if mode == "serien":
            series_map = {}
            for b in books:
                s = b.get("series","") or b.get("title","?")
                series_map.setdefault(s, []).append(b)
            for series_name in sorted(series_map.keys(), key=str.lower):
                hdr = Gtk.Label(label=f"  {series_name}")
                hdr.set_halign(Gtk.Align.START)
                hdr.set_css_classes(["section-label"])
                hdr.set_margin_top(10); hdr.set_margin_bottom(4); hdr.set_margin_start(8)
                self._shelf_list.append(hdr)
                for b in sorted(series_map[series_name],
                                key=lambda x: (x.get("episode",0), x.get("title",""))):
                    _add_book_row(b)
        else:
            def _sort_key(b):
                s = b.get("series","")
                return (0 if s else 1, s.lower(), b.get("episode",0), b.get("title","").lower())
            for b in sorted(books, key=_sort_key):
                _add_book_row(b)

    def _on_book_selected(self, listbox, row):
        if not isinstance(row, AudiobookShelfItem): return
        book = row.book
        self._load_book(book)

    def _load_book(self, book):
        self._current_book     = book
        self._current_file_idx = book.get("current_file", 0)
        files = book.get("files", [])
        if not files: return

        # Regal sofort neu aufbauen damit aktives Buch markiert wird
        self._refresh_shelf()

        # Fenstertitel aktualisieren
        author = book.get("author","") or ""
        title  = book.get("title","")  or ""
        if hasattr(self, '_on_title_change') and self._on_title_change:
            if author and title:
                self._on_title_change(f"{author} — {title}")
            elif title:
                self._on_title_change(title)

        self._title_lbl.set_label(book.get("title","?"))
        # Serien-Info oder Autor
        series  = book.get("series","")
        episode = book.get("episode",0)
        cat     = book.get("category","hörbuch")
        cat_icon = "🎭" if cat == "hörspiel" else "📚"
        if series:
            ep_str = f"  #{episode}" if episode else ""
            self._author_lbl.set_label(f"{cat_icon} {series}{ep_str}")
        else:
            self._author_lbl.set_label(f"{cat_icon} {book.get('author','')}")
        self._total_pb.set_fraction(book.get("progress", 0.0))

        # Cover laden + anzeigen
        cover_path = book.get("cover_path","")
        self._show_cover(cover_path)
        # Auto-Suche wenn kein Cover vorhanden
        if not (cover_path and Path(cover_path).exists()):
            if self.config.get("auto_cover", True):
                GLib.idle_add(lambda b=book: self._auto_search_cover(b) or False)

        # Kapitel laden (aus erster oder aktueller Datei)
        fi = min(self._current_file_idx, len(files)-1)
        path = files[fi]
        self._file_lbl.set_label(f"Datei {fi+1}/{len(files)}: {Path(path).name}")

        def _load_chapters():
            chaps = _ab_chapters_from_file(path)
            GLib.idle_add(self._set_chapters, chaps)
        threading.Thread(target=_load_chapters, daemon=True).start()

        # Abspielen ab gespeicherter Position
        pos = book.get("current_pos", 0) if fi == book.get("current_file",0) else 0
        self.ab_player.load(path, start_pos=pos, vol=self.vol_getter())
        self._update_play_btn(True)

    def _show_cover(self, cover_path):
        """Zeigt Cover-Bild (80×80px fest) oder Placeholder."""
        if cover_path and Path(cover_path).exists():
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(cover_path, 80, 80, True)
                self._cover_img_widget.set_from_pixbuf(pb)
                return
            except Exception as e:
                print(f"Cover laden fehlgeschlagen: {e}")
        self._cover_img_widget.set_from_icon_name("audio-x-generic")
        self._cover_img_widget.set_pixel_size(64)

    def _pick_cover(self, *_):
        """Manuell ein Cover-Bild auswählen."""
        if not self._current_book: return
        dlg = Gtk.FileDialog()
        dlg.set_title("Cover-Bild auswählen")
        filt = Gtk.FileFilter(); filt.set_name("Bilder")
        for p in ["*.jpg","*.jpeg","*.png","*.webp"]:
            filt.add_pattern(p)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filt)
        dlg.set_filters(filters)
        dlg.open(self.get_root(), None, self._on_cover_chosen)

    def _on_cover_chosen(self, dlg, result):
        try:
            gfile = dlg.open_finish(result)
        except: return
        path = gfile.get_path()
        if not path or not self._current_book: return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            self._save_cover_to_book(self._current_book, pixbuf)
        except Exception as e:
            print(f"Cover-Bild Fehler: {e}")

    def _search_cover_manual(self, *_):
        """Dialog: Name/Titel eingeben, dann online suchen."""
        if not self._current_book: return
        book = self._current_book

        dlg = Gtk.Dialog(title="Cover suchen", transient_for=self.get_root(), modal=True)
        dlg.set_default_size(360, 180)
        box = dlg.get_content_area()
        box.set_spacing(10); box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12); box.set_margin_bottom(12)

        grid = Gtk.Grid(row_spacing=8, column_spacing=10)
        box.append(grid)

        grid.attach(Gtk.Label(label="Interpret / Autor:", halign=Gtk.Align.START), 0, 0, 1, 1)
        author_entry = Gtk.Entry()
        author_entry.set_text(book.get("author",""))
        author_entry.set_hexpand(True)
        grid.attach(author_entry, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Titel:", halign=Gtk.Align.START), 0, 1, 1, 1)
        title_entry = Gtk.Entry()
        title_entry.set_text(book.get("title",""))
        title_entry.set_hexpand(True)
        grid.attach(title_entry, 1, 1, 1, 1)

        status_lbl = Gtk.Label(label="")
        status_lbl.set_halign(Gtk.Align.START)
        status_lbl.set_css_classes(["dim-label"])
        box.append(status_lbl)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END); btn_box.set_margin_top(8)
        cancel_btn = Gtk.Button(label="Abbrechen")
        cancel_btn.connect("clicked", lambda *_: dlg.close())
        btn_box.append(cancel_btn)
        search_btn = Gtk.Button(label="Suchen")
        search_btn.add_css_class("suggested-action")
        btn_box.append(search_btn)
        box.append(btn_box)

        def _do_search(*_):
            author = author_entry.get_text().strip()
            title  = title_entry.get_text().strip()
            if not title: return
            search_btn.set_sensitive(False)
            status_lbl.set_label("Suche läuft …")
            def _fetch():
                pixbuf = None
                if author:
                    pixbuf = self.cover_downloader.search_cover(author, title,
                        book.get("files",[""])[0])
                if not pixbuf:
                    pixbuf = self.cover_downloader.search_cover(title, title,
                        book.get("files",[""])[0])
                def _done():
                    if pixbuf:
                        self._save_cover_to_book(book, pixbuf)
                        dlg.close()
                    else:
                        status_lbl.set_label("Kein Cover gefunden.")
                        search_btn.set_sensitive(True)
                GLib.idle_add(_done)
            threading.Thread(target=_fetch, daemon=True).start()

        search_btn.connect("clicked", _do_search)
        title_entry.connect("activate", _do_search)
        dlg.present()

    def _auto_search_cover(self, book, force=False):
        """Sucht automatisch ein Cover online (im Hintergrund)."""
        title  = book.get("title","")
        author = book.get("author","")
        if not title: return
        def _fetch():
            pixbuf = None
            # Versuch 1: Titel + Autor via MusicBrainz/iTunes
            if author:
                pixbuf = self.cover_downloader.search_cover(author, title,
                    book.get("files",[""])[0])
            # Versuch 2: nur Titel
            if not pixbuf:
                pixbuf = self.cover_downloader.search_cover(title, title,
                    book.get("files",[""])[0])
            if pixbuf:
                GLib.idle_add(lambda: self._save_cover_to_book(book, pixbuf) or False)
        threading.Thread(target=_fetch, daemon=True).start()

    def _save_cover_to_book(self, book, pixbuf):
        """Speichert Cover als Datei im Buch-Ordner, trägt in Tags ein, aktualisiert Lib."""
        uuid = book.get("uuid","")
        files = book.get("files",[])
        if not uuid or not files: return

        # Skalieren auf max 600px
        w, h = pixbuf.get_width(), pixbuf.get_height()
        if w > 600 or h > 600:
            if w > h:
                pixbuf = pixbuf.scale_simple(600, int(600*h/w), GdkPixbuf.InterpType.BILINEAR)
            else:
                pixbuf = pixbuf.scale_simple(int(600*w/h), 600, GdkPixbuf.InterpType.BILINEAR)

        # Im Buch-Ordner speichern (cover.jpg)
        book_folder = str(Path(files[0]).parent)
        cover_path  = os.path.join(book_folder, "cover.jpg")
        try:
            pixbuf.savev(cover_path, "jpeg", ["quality"], ["90"])
        except Exception as e:
            print(f"Cover speichern fehlgeschlagen: {e}"); return

        # In Audio-Tags aller Dateien des Buches schreiben (im Hintergrund)
        def _write_tags():
            try:
                import mutagen
                from mutagen.id3 import ID3, APIC, error as ID3Error
                from mutagen.mp4 import MP4, MP4Cover
                from mutagen.flac import FLAC, Picture as FlacPic
                import struct
                with open(cover_path, "rb") as f:
                    cover_data = f.read()
                for fpath in files:
                    ext = Path(fpath).suffix.lower()
                    try:
                        if ext == ".mp3":
                            try: tags = ID3(fpath)
                            except ID3Error: tags = ID3(); tags.save(fpath)
                            tags["APIC"] = APIC(
                                encoding=3, mime="image/jpeg",
                                type=3, desc="Cover", data=cover_data)
                            tags.save(fpath)
                        elif ext in (".m4a",".m4b",".aac"):
                            tags = MP4(fpath)
                            tags["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                            tags.save()
                        elif ext == ".flac":
                            tags = FLAC(fpath)
                            pic = FlacPic()
                            pic.type = 3; pic.mime = "image/jpeg"
                            pic.data = cover_data
                            tags.clear_pictures(); tags.add_picture(pic); tags.save()
                    except Exception as e:
                        print(f"Tag-Schreiben fehlgeschlagen für {fpath}: {e}")
            except ImportError:
                print("mutagen nicht installiert — Tags werden nicht geschrieben")
        threading.Thread(target=_write_tags, daemon=True).start()

        # Bibliothek aktualisieren
        if uuid in self.ab_lib._data:
            self.ab_lib._data[uuid]["cover_path"] = cover_path
            self.ab_lib.save()

        # UI aktualisieren
        if self._current_book and self._current_book.get("uuid") == uuid:
            self._show_cover(cover_path)
        self._refresh_shelf()

    def _set_chapters(self, chapters):
        self._chapters = chapters
        while r := self._chap_list.get_row_at_index(0):
            self._chap_list.remove(r)
        if not chapters:
            # Keine Kapitel-Tags → Dateien als Kapitel zeigen
            if self._current_book:
                active_idx = self._current_file_idx
                for i, f in enumerate(self._current_book.get("files",[])):
                    row = Gtk.ListBoxRow()
                    lbl = Gtk.Label(label=f"{i+1}. {Path(f).stem}")
                    lbl.set_halign(Gtk.Align.START)
                    css = ["ab-chapter", "ab-chapter-active"] if i == active_idx else ["ab-chapter"]
                    lbl.set_css_classes(css)
                    lbl.set_margin_start(8); lbl.set_margin_top(4); lbl.set_margin_bottom(4)
                    row.set_child(lbl)
                    self._chap_list.append(row)
                # Zur aktiven Zeile scrollen
                active_row = self._chap_list.get_row_at_index(active_idx)
                if active_row:
                    self._chap_list.select_row(active_row)
                    GLib.idle_add(lambda r=active_row: self._chap_list.get_parent() and
                                  self._chap_list.get_parent().get_vadjustment() and
                                  self._chap_list.get_parent().get_vadjustment().set_value(
                                      max(0, r.get_allocation().y - 40)) or False)
            return
        for i, ch in enumerate(chapters):
            row = Gtk.ListBoxRow()
            lbl = Gtk.Label(label=f"{i+1}. {ch['title']}")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_css_classes(["ab-chapter"])
            lbl.set_margin_start(8); lbl.set_margin_top(4); lbl.set_margin_bottom(4)
            row.set_child(lbl)
            self._chap_list.append(row)
        # Sofort Kapitel-Highlight setzen
        pos = self.ab_player.get_pos()
        if pos > 0:
            self._highlight_chapter(pos)

    def _on_chapter_activated(self, listbox, row):
        idx = row.get_index()
        if not self._current_book: return
        if self._chapters:
            # Zu Kapitel-Startposition springen
            if 0 <= idx < len(self._chapters):
                self.ab_player.seek(self._chapters[idx]["start"])
        else:
            # Kapitel = Dateien
            files = self._current_book.get("files",[])
            if 0 <= idx < len(files):
                self._current_file_idx = idx
                self.ab_player.load(files[idx], vol=self.vol_getter())
                self._update_play_btn(True)

    # ── Steuerung ──────────────────────────────────────────────────
    def _play_pause(self, *_):
        if not self._current_book: return
        self.ab_player.play_pause()
        self._update_play_btn(self.ab_player.is_playing())

    def _update_play_btn(self, playing):
        self._play_btn.set_icon_name(
            "media-playback-pause" if playing else "media-playback-start")

    def _skip(self, secs):
        pos = self.ab_player.get_pos()
        dur = self.ab_player.get_duration()
        self.ab_player.seek(max(0, min(dur, pos + secs)))

    def _prev_chapter(self, *_):
        if not self._current_book: return
        if self._chapters:
            pos = self.ab_player.get_pos()
            # Vorheriges Kapitel oder Anfang
            for i in range(len(self._chapters)-1, -1, -1):
                if self._chapters[i]["start"] < pos - 2:
                    self.ab_player.seek(self._chapters[i]["start"]); return
            self.ab_player.seek(0)
        else:
            files = self._current_book.get("files",[])
            if self._current_file_idx > 0:
                self._current_file_idx -= 1
                self.ab_player.load(files[self._current_file_idx], vol=self.vol_getter())
                self._update_play_btn(True)

    def _next_chapter(self, *_):
        if not self._current_book: return
        if self._chapters:
            pos = self.ab_player.get_pos()
            for ch in self._chapters:
                if ch["start"] > pos + 1:
                    self.ab_player.seek(ch["start"]); return
        else:
            files = self._current_book.get("files",[])
            if self._current_file_idx < len(files)-1:
                self._current_file_idx += 1
                self.ab_player.load(files[self._current_file_idx], vol=self.vol_getter())
                self._update_play_btn(True)

    def _set_speed(self, spd):
        self._current_speed = spd
        self.ab_player.set_speed(spd)
        self._update_speed_btns(spd)

    def _update_speed_btns(self, active):
        for spd, btn in self._speed_btns:
            if abs(spd - active) < 0.01:
                btn.set_css_classes(["ab-speed-active"])
            else:
                btn.set_css_classes(["ab-speed-btn","flat"])

    def _on_scale_drag(self, scale):
        """Während des Ziehens: Zeit-Labels live aktualisieren."""
        if not self._seeking: return
        dur = self.ab_player.get_duration()
        pos = scale.get_value() * dur
        self._pos_lbl.set_label(_fmt_time(int(pos)))

    def _on_scale_release(self, *_):
        """Maustaste losgelassen → an neue Position springen."""
        if not self._current_book: self._seeking = False; return
        dur = self.ab_player.get_duration()
        if dur > 0:
            self.ab_player.seek(self._prog_bar.get_value() * dur)
        self._seeking = False

    def _on_pos(self, pos, dur):
        if not self._seeking:   # nicht überschreiben während User zieht
            if dur > 0:
                self._prog_bar.set_value(pos / dur)
            self._pos_lbl.set_label(_fmt_time(int(pos)))
        self._dur_lbl.set_label(_fmt_time(int(dur)))
        # Fortschritt speichern
        if self._current_book:
            self.ab_lib.update_progress(
                self._current_book["uuid"],
                self._current_file_idx, pos, dur)
            self._total_pb.set_fraction(
                self._current_book.get("progress",0.0))
            # Kapitel-Highlight aktualisieren
            self._highlight_chapter(pos)

    def _highlight_chapter(self, pos):
        if self._chapters:
            # Kapitel-Tags vorhanden: nach Position suchen
            active = 0
            for i, ch in enumerate(self._chapters):
                if ch["start"] <= pos:
                    active = i
            count = len(self._chapters)
        else:
            # Datei-Modus: aktuelle Datei hervorheben
            active = self._current_file_idx
            count = len(self._current_book.get("files",[])) if self._current_book else 0
        for i in range(count):
            row = self._chap_list.get_row_at_index(i)
            if not row: continue
            lbl = row.get_child()
            if not lbl: continue
            if i == active:
                lbl.set_css_classes(["ab-chapter", "ab-chapter-active"])
                self._chap_list.select_row(row)
            else:
                lbl.set_css_classes(["ab-chapter"])

    def _on_eos(self):
        """Nächste Datei oder Buch fertig."""
        if not self._current_book: return
        files = self._current_book.get("files",[])
        if self._current_file_idx < len(files)-1:
            self._current_file_idx += 1
            self.ab_player.load(files[self._current_file_idx], vol=self.vol_getter())
            self._update_play_btn(True)
            # Kapitel-Highlight auf neue Datei aktualisieren
            GLib.idle_add(lambda: self._highlight_chapter(0) or False)
        else:
            # Buch fertig
            self.ab_lib.mark_done(self._current_book["uuid"])
            self._total_pb.set_fraction(1.0)
            self._update_play_btn(False)
            self._refresh_shelf()

    def _toggle_done(self, *_):
        if not self._current_book: return
        done = not self._current_book.get("done", False)
        self.ab_lib.mark_done(self._current_book["uuid"], done)
        self._refresh_shelf()

    # ── Lesezeichen ────────────────────────────────────────────────
    def _refresh_bookmarks(self):
        while r := self._bm_list.get_row_at_index(0):
            self._bm_list.remove(r)
        if not self._current_book: return
        for i, bm in enumerate(self._current_book.get("bookmarks",[])):
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_start(6); box.set_margin_top(4); box.set_margin_bottom(4)
            time_lbl = Gtk.Label(label=_fmt_time(bm["pos"]))
            time_lbl.set_css_classes(["helga-time"]); box.append(time_lbl)
            note_lbl = Gtk.Label(label=bm.get("note","") or bm["time"])
            note_lbl.set_css_classes(["ab-bookmark"]); note_lbl.set_hexpand(True)
            note_lbl.set_halign(Gtk.Align.START); box.append(note_lbl)
            del_btn = Gtk.Button(icon_name="list-remove-symbolic")
            del_btn.set_css_classes(["flat"]); del_btn.set_opacity(0.5)
            del_btn.connect("clicked", lambda _, idx=i: self._del_bookmark(idx))
            box.append(del_btn)
            row.set_child(box)
            self._bm_list.append(row)

    def _add_bookmark_dialog(self, *_):
        if not self._current_book: return
        pos = self.ab_player.get_pos()
        # Einfacher Dialog für Notiz
        dlg = Gtk.Dialog(title="Lesezeichen", transient_for=self.get_root(), modal=True)
        dlg.set_default_size(320, 140)
        area = dlg.get_content_area()
        area.set_spacing(8); area.set_margin_start(14); area.set_margin_end(14)
        area.set_margin_top(10); area.set_margin_bottom(10)
        area.append(Gtk.Label(label=f"Lesezeichen bei {_fmt_time(int(pos))}"))
        entry = Gtk.Entry(); entry.set_placeholder_text("Notiz (optional)")
        area.append(entry)
        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Abbrechen"); cancel.connect("clicked", lambda *_: dlg.close())
        ok = Gtk.Button(label="Speichern"); ok.add_css_class("suggested-action")
        def _save(*_):
            self.ab_lib.add_bookmark(self._current_book["uuid"],
                                     self._current_file_idx, pos,
                                     entry.get_text().strip())
            self._refresh_bookmarks(); dlg.close()
        ok.connect("clicked", _save); entry.connect("activate", _save)
        btn_row.append(cancel); btn_row.append(ok); area.append(btn_row)
        dlg.present()

    def _on_bm_activated(self, listbox, row):
        if not self._current_book: return
        idx = row.get_index()
        bms = self._current_book.get("bookmarks",[])
        if 0 <= idx < len(bms):
            bm = bms[idx]
            fi = bm.get("file_idx", 0)
            files = self._current_book.get("files",[])
            if fi != self._current_file_idx and 0 <= fi < len(files):
                self._current_file_idx = fi
                self.ab_player.load(files[fi], start_pos=bm["pos"], vol=self.vol_getter())
                self._update_play_btn(True)
            else:
                self.ab_player.seek(bm["pos"])

    def _del_bookmark(self, idx):
        if not self._current_book: return
        self.ab_lib.remove_bookmark(self._current_book["uuid"], idx)
        self._refresh_bookmarks()

    # ── Textmarkierung / Suche ─────────────────────────────────────
    def _do_lookup(self, *_):
        self._lookup("web")

    def _lookup(self, mode):
        term = self._lookup_entry.get_text().strip()
        if not term: return
        if mode == "web":
            url = f"https://www.google.com/search?q={urllib.parse.quote(term)}"
        else:
            url = f"https://www.deepl.com/translator#auto/de/{urllib.parse.quote(term)}"
        try: subprocess.Popen(["xdg-open", url])
        except: pass

    # ── Bücher hinzufügen ──────────────────────────────────────────
    def _add_files(self, *_):
        dlg = Gtk.FileDialog()
        dlg.set_title("Hörbuch-Dateien auswählen")
        filt = Gtk.FileFilter(); filt.set_name("Audio")
        for p in ["*.mp3","*.m4a","*.m4b","*.ogg","*.flac","*.opus"]:
            filt.add_pattern(p)
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filt)
        dlg.set_filters(filters)
        dlg.open_multiple(self.get_root(), None, self._on_files_chosen)

    def _on_files_chosen(self, dlg, result):
        try:
            gfiles = dlg.open_multiple_finish(result)
        except: return
        paths = [gf.get_path() for gf in gfiles if gf.get_path()]
        if not paths: return
        threading.Thread(target=self._import_files, args=(paths,), daemon=True).start()

    def _add_folder(self, *_):
        dlg = Gtk.FileDialog(); dlg.set_title("Ordner als Hörbuch öffnen")
        dlg.select_folder(self.get_root(), None, self._on_folder_chosen)

    def _on_folder_chosen(self, dlg, result):
        try:
            gfile = dlg.select_folder_finish(result)
        except: return
        folder = gfile.get_path()
        if not folder: return
        # Den gewählten Ordner selbst für Auto-Scan merken (nicht den übergeordneten),
        # damit nur Unterordner dieses Ordners gescannt werden und nicht
        # benachbarte Musik-Ordner miterfasst werden.
        ab_dirs = self.config.get("ab_dirs", [])
        if folder not in ab_dirs:
            ab_dirs.append(folder)
            self.config["ab_dirs"] = ab_dirs
            self._save_config()
        exts = {".mp3",".m4a",".m4b",".ogg",".flac",".opus"}
        paths = sorted([str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in exts])
        if not paths: return
        threading.Thread(target=self._import_files, args=(paths,), daemon=True).start()

    def _import_files(self, paths):
        import re as _re
        uuid  = _ab_uuid(paths)
        folder = Path(paths[0]).parent
        # Category aus aktivem Tab ableiten
        _import_category = getattr(self, '_filter_mode', 'hörbuch')
        if _import_category not in ("hörbuch", "hörspiel"):
            _import_category = "hörbuch"

        # ── Titel & Autor aus Tags oder Ordnername ─────────────────
        title  = folder.name if len(paths) > 1 else Path(paths[0]).stem
        author = ""
        cover_pixbuf = None
        try:
            uri  = Gst.filename_to_uri(os.path.abspath(paths[0]))
            info = GstPbutils.Discoverer.new(3*Gst.SECOND).discover_uri(uri)
            tags = info.get_audio_streams()[0].get_tags() if info.get_audio_streams() else None
            if tags:
                ok, v = tags.get_string(Gst.TAG_ALBUM)
                if ok and v: title = v
                ok, v = tags.get_string(Gst.TAG_ARTIST)
                if ok and v: author = v
                ok, v = tags.get_string(Gst.TAG_COMPOSER)
                if ok and v and not author: author = v
            cover_pixbuf = _ab_cover_from_file(paths[0])
        except: pass

        # ── Cover aus Ordner-Bild wenn kein Tag-Cover ──────────────
        if not cover_pixbuf:
            for fname in ["cover.jpg","cover.png","folder.jpg","folder.png",
                          "Cover.jpg","Cover.png","Folder.jpg"]:
                p = folder / fname
                if p.exists():
                    try:
                        cover_pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(p))
                        break
                    except: pass

        # ── Cover speichern ────────────────────────────────────────
        cover_path = ""
        if cover_pixbuf:
            cover_path = str(Path.home() / ".config" / "helga" / f"ab_cover_{uuid}.jpg")
            try: cover_pixbuf.savev(cover_path, "jpeg", [], [])
            except: cover_path = ""

        # Category aus aktivem Tab (wurde oben in _import_category gesetzt)
        category = _import_category
        total_dur = len(paths) * 3600

        book = self.ab_lib.add_book(uuid, title, author, cover_path, paths, total_dur,
                                    category=category)
        GLib.idle_add(self._refresh_shelf)
        GLib.idle_add(self._load_book, book)


def _fmt_time(secs):
    secs = int(secs)
    h, m = divmod(secs, 3600)
    m, s = divmod(m, 60)
    if h: return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ─── Volume Button mit Mute ───────────────────────────────────────────────────
class VolumeButton(Gtk.MenuButton):
    def __init__(self, player):
        super().__init__()
        self.set_icon_name("audio-volume-medium")
        self.set_tooltip_text("Lautstärke (Scrollrad oder Klick)")
        self.set_css_classes(["flat"])
        self._player = player
        self._volume = 0.8
        self._muted = False

        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        popover_box.set_css_classes(["vol-popover"])
        popover_box.set_size_request(44, 200)

        self._mute_btn = Gtk.ToggleButton()
        self._mute_btn.set_icon_name("audio-volume-muted")
        self._mute_btn.set_tooltip_text("Stumm schalten")
        self._mute_btn.set_css_classes(["flat"])
        self._mute_btn.connect("toggled", self._on_mute_toggle)
        popover_box.append(self._mute_btn)

        self._vol_scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL)
        self._vol_scale.set_range(0, 1.5)
        self._vol_scale.set_value(0.8)
        self._vol_scale.set_inverted(True)
        self._vol_scale.set_draw_value(False)
        self._vol_scale.set_vexpand(True)
        self._vol_scale.set_size_request(44, 140)
        self._vol_scale.connect("value-changed", self._on_scale_change)
        popover_box.append(self._vol_scale)

        self._vol_lbl = Gtk.Label(label="80%")
        self._vol_lbl.set_css_classes(["helga-time"])
        popover_box.append(self._vol_lbl)

        popover = Gtk.Popover()
        popover.set_child(popover_box)
        self.set_popover(popover)

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

        self._update_mute_icon()

    def _on_scale_change(self, scale):
        self._volume = scale.get_value()
        if not self._muted:
            self._player.set_vol(self._volume)
        self._update_icon()
        self._vol_lbl.set_label(f"{int(self._volume * 100)}%")

    def _on_scroll(self, ctrl, dx, dy):
        step = -0.05 if dy > 0 else 0.05
        new_vol = max(0.0, min(1.5, self._volume + step))
        self._vol_scale.set_value(new_vol)
        if self._muted:
            self._mute_btn.set_active(False)
        return True

    def _on_mute_toggle(self, btn):
        self._muted = btn.get_active()
        if self._muted:
            self._player.set_vol(0.0)
        else:
            self._player.set_vol(self._volume)
        self._update_icon()
        self._update_mute_icon()

    def _update_icon(self):
        if self._muted:
            self.set_icon_name("audio-volume-muted")
        elif self._volume <= 0:
            self.set_icon_name("audio-volume-muted")
        elif self._volume < 0.5:
            self.set_icon_name("audio-volume-low")
        elif self._volume < 1.0:
            self.set_icon_name("audio-volume-medium")
        else:
            self.set_icon_name("audio-volume-high")

    def _update_mute_icon(self):
        if self._muted:
            self._mute_btn.set_icon_name("audio-volume-muted")
            self._mute_btn.set_tooltip_text("Stummschaltung aufheben")
        else:
            self._mute_btn.set_icon_name("audio-volume-high")
            self._mute_btn.set_tooltip_text("Stumm schalten")

    def get_volume(self): 
        return self._volume

    def set_volume(self, v):
        self._volume = max(0.0, min(1.5, v))
        self._vol_scale.set_value(self._volume)
        if not self._muted:
            self._player.set_vol(self._volume)
        self._update_icon()
        self._vol_lbl.set_label(f"{int(self._volume * 100)}%")


# ─── Main Window ──────────────────────────────────────────────────────────────
class Helga(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Helga")
        self.set_default_size(900, 600)

        self.player  = Player()
        self.player.parent = self
        self.fader = FadeController(self.player, duration=2000)
        self.cover_downloader = CoverDownloader()
        self.smart_gen = SmartPlaylistGenerator(self.player)
        self.radio_player = RadioPlayer()
        self._tab_switching = False
        self.ab_player = AudiobookPlayerEngine()
        self.ab_lib    = AudiobookLibrary()

        self.player.on_eos  = self._on_eos
        self.player.on_load = self._on_load
        self._cache  = {}
        self._sleep_timer_id = None
        self._sleep_end = 0
        self._show_playlist = True
        self._rating = {}
        self._play_count = {}
        self._last_position = {}
        self._last_played = []
        self._eos_triggered = False   # Flag für automatischen Song-Wechsel
        self._queued_next   = -1      # Index des als-nächstes-Wartenden Songs

        # ── Standard-Ordner ermitteln und anlegen ──
        _default_hoerbuch_dir  = str(Path.home() / "Hörbuch")
        _default_hoerspiel_dir = str(Path.home() / "Hörspiel")
        Path(_default_hoerbuch_dir).mkdir(exist_ok=True)
        Path(_default_hoerspiel_dir).mkdir(exist_ok=True)
        _default_ab_dir = _default_hoerbuch_dir  # Rückwärtskompatibilität

        # Standard-Musikordner: XDG-Verzeichnis (~/Musik, ~/Music o.ä.) oder ~/Musik als Fallback
        _xdg_music = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_MUSIC)
        _default_music_dir = str(Path(_xdg_music)) if _xdg_music else str(Path.home() / "Musik")
        # Ordner anlegen falls nicht vorhanden
        Path(_default_music_dir).mkdir(exist_ok=True)

        self.config = {
            "fade_enabled": False,
            "fade_duration": 2000,
            "fade_curve": "smooth",
            "auto_cover": True,
            "source_musicbrainz": True,
            "source_itunes": True,
            "resume_enabled": True,
            "eq_preset": 0,
            "eq_enabled": True,
            "volume": 0.8,
            "shuffle": False,
            "repeat": "none",
            "vis_mode": 0,
            "queue_on_click": False,
            "pl_view_mode": "album",
            "auto_scan": True,
            "scan_interval_min": 10,
            "music_dirs": [_default_music_dir],  # Standard-Musikordner
            "ab_dirs": [_default_hoerbuch_dir],    # Standard-Hörbuchordner
            "hoerspiel_dir": _default_hoerspiel_dir, # Standard-Hörspielordner
        }
        self._load_config()
        # Sicherstellen dass die Standard-Ordner immer enthalten sind
        # (auch nach dem Laden einer alten config ohne diese Einträge)
        ab_dirs = self.config.setdefault("ab_dirs", [])
        if _default_hoerbuch_dir not in ab_dirs:
            ab_dirs.insert(0, _default_hoerbuch_dir)
            self.config["ab_dirs"] = ab_dirs
        if "hoerspiel_dir" not in self.config:
            self.config["hoerspiel_dir"] = _default_hoerspiel_dir
        music_dirs = self.config.setdefault("music_dirs", [])
        if _default_music_dir not in music_dirs:
            music_dirs.insert(0, _default_music_dir)
            self.config["music_dirs"] = music_dirs
        self._scan_timer_id = None
        self._schedule_auto_scan()

        self.fader.set_fade_enabled(self.config["fade_enabled"])
        self.fader.set_fade_duration(self.config["fade_duration"])
        self.fader.set_fade_curve(self.config["fade_curve"])

        self._build_ui()
        self._apply_css()

        # Album-Grid nur bei maximiertem Fenster anzeigen
        self._album_grid.set_visible(False)
        self.connect("notify::maximized", self._on_maximized_changed)

        self.player.setup_spectrum(self._vis.feed_spectrum)

        self.connect("realize", self._on_realize)

        GLib.timeout_add(500, self._tick)

        self.connect("close-request", self._on_close)

        vol = self.config.get("volume", 0.8)
        self.player.set_vol(vol)
        if hasattr(self, '_vol_btn'):
            self._vol_btn.set_volume(vol)

        eq_idx = self.config.get("eq_preset", 0)
        eq_enabled = self.config.get("eq_enabled", True)
        keys = list(EQ_PRESETS.keys())
        if eq_enabled:
            if eq_idx == len(EQ_PRESETS):  # Manuell
                gains = self.config.get("eq_manual", [0]*10)
                self.player.set_eq_preset("Manuell", gains)
            elif 0 <= eq_idx < len(keys):
                self.player.set_eq_preset(keys[eq_idx], EQ_PRESETS[keys[eq_idx]])
        # Manuell-Slider nach UI-Build sichtbar schalten wenn nötig
        GLib.idle_add(lambda: self._eq_manual_box.set_visible(
            eq_idx == len(EQ_PRESETS)) or False)

        if self.config["resume_enabled"] and self.player.current >= 0:
            path = self.player.playlist[self.player.current]
            resume_pos = self._last_position.get(path, 0)
            if resume_pos > 0:
                self.player.current_pos = resume_pos
                self.player.load(self.player.current, resume_pos, paused=True)
            else:
                self.player.load(self.player.current, paused=True)
        elif self.player.current >= 0:
            self.player.load(self.player.current, paused=True)

        # Letzten Tab + Radio-Sender wiederherstellen
        last_tab = self.config.get("last_tab", "musik")
        if last_tab in ("musik", "radio", "hoerbuch"):
            GLib.idle_add(lambda: self._switch_tab(last_tab, None) or False)
        GLib.idle_add(lambda: self._apply_font_size(self.config.get('font_size', 16)) or False)
        # Radio-Sender vormerken (wird nach UI-Aufbau gesetzt)
        last_uuid = self.config.get("last_radio_uuid", "")
        last_name = self.config.get("last_radio_name", "")
        last_url  = self.config.get("last_radio_url",  "")
        if last_uuid and last_url:
            def _restore_radio():
                if hasattr(self, "_radio_panel"):
                    p = self._radio_panel
                    p._current_uuid = last_uuid
                    p._current_name = last_name
                    p._current_url  = last_url
                    p._now_station.set_label(last_name)
                    p._now_song.set_label("")
                    p._live_dot.set_label("")   # nicht live — noch nicht gestartet
                    p._fill_list()              # Sender in Liste markieren
                return False
            GLib.idle_add(_restore_radio)

    def _on_realize(self, *_):
        self._detect_theme_accent()

    def _detect_theme_accent(self):
        """Liest Systemakzentfarbe und Hell/Dunkel-Modus aus GTK4-Theme."""
        try:
            # Versuche Adwaita StyleManager (GNOME 42+)
            import gi
            gi.require_version("Adw", "1")
            from gi.repository import Adw
            sm = Adw.StyleManager.get_default()
            # Akzentfarbe auslesen
            try:
                ac = sm.get_accent_color()
                rgba = ac.to_rgba()
                accent  = (rgba.red, rgba.green, rgba.blue)
                accent2 = (max(0, rgba.red*0.7), max(0, rgba.green*0.7), max(0, rgba.blue*0.7))
            except:
                accent  = (0.118, 0.678, 0.957)
                accent2 = (0.06,  0.45,  0.75)
            C["accent"]  = accent
            C["accent2"] = accent2
            self._vis.apply_theme_colors(accent, accent2)
            # Auf Theme-Änderungen reagieren
            sm.connect("notify::accent-color", lambda *_: self._detect_theme_accent())
            sm.connect("notify::color-scheme", lambda *_: self._detect_theme_accent())
            return
        except Exception:
            pass
        # Fallback: GTK-Settings auslesen
        try:
            settings = Gtk.Settings.get_default()
            dark = settings.get_property("gtk-application-prefer-dark-theme")
            # Akzentfarbe aus Theme-Name ableiten (Yaru, Breeze, etc.)
            theme = (settings.get_property("gtk-theme-name") or "").lower()
            if "blue" in theme or "default" in theme or "adwaita" in theme:
                accent = (0.118, 0.678, 0.957)
            elif "green" in theme or "yaru" in theme:
                accent = (0.17, 0.67, 0.34)
            elif "orange" in theme:
                accent = (0.9, 0.5, 0.1)
            elif "purple" in theme or "breeze" in theme:
                accent = (0.47, 0.36, 0.8)
            elif "red" in theme:
                accent = (0.85, 0.2, 0.2)
            else:
                accent = (0.118, 0.678, 0.957)
            accent2 = (max(0, accent[0]*0.7), max(0, accent[1]*0.7), max(0, accent[2]*0.7))
            C["accent"]  = accent
            C["accent2"] = accent2
            self._vis.apply_theme_colors(accent, accent2)
            # Auf Theme-Änderungen reagieren
            settings.connect("notify::gtk-theme-name", lambda *_: self._detect_theme_accent())
            settings.connect("notify::gtk-application-prefer-dark-theme",
                             lambda *_: self._detect_theme_accent())
        except Exception as e:
            print(f"Theme-Erkennung fehlgeschlagen: {e}")
            accent  = (0.118, 0.678, 0.957)
            accent2 = (0.06,  0.45,  0.75)
            C["accent"]  = accent
            C["accent2"] = accent2
            self._vis.apply_theme_colors(accent, accent2)

    def _load_config(self):
        try:
            d = json.loads(CONFIG_PATH.read_text())
            self.player.playlist = d.get("playlist", [])
            self.player.current  = d.get("current", -1)
            self._rating = d.get("ratings", {})
            self._play_count = d.get("play_count", {})
            self._last_position = d.get("last_position", {})
            self.player.shuffle = d.get("shuffle", False)
            self.player.repeat = d.get("repeat", "none")
            if "config" in d:
                self.config.update(d["config"])
            vol = self.config.get("volume", 0.8)
            self.player.set_vol(vol)
            self.player.playlist = [p for p in self.player.playlist if os.path.exists(p)]
            if self.player.current >= len(self.player.playlist):
                self.player.current = -1
            # Gespeicherte Playlist beim Start still auf Hörbücher prüfen
            if self.player.playlist:
                saved = list(self.player.playlist)
                def _startup_filter():
                    ab_count = sum(1 for p in saved if self._is_audiobook_file(p))
                    clean    = [p for p in saved if not self._is_audiobook_file(p)]
                    def _apply():
                        if ab_count:
                            cur_path = (self.player.playlist[self.player.current]
                                        if 0 <= self.player.current < len(self.player.playlist) else None)
                            self.player.playlist = clean
                            self.player.current  = (clean.index(cur_path)
                                                     if cur_path and cur_path in clean else -1)
                            self._refresh_playlist()
                            self._show_audiobook_hint(ab_count)
                        return False
                    GLib.idle_add(_apply)
                GLib.timeout_add(1500, lambda: threading.Thread(
                    target=_startup_filter, daemon=True).start() or False)
        except Exception as e:
            print(f"Fehler beim Laden der Konfiguration: {e}")

    def _save_config(self):
        try:
            if self.config.get("resume_enabled", True) and self.player.current >= 0:
                if self.player.current < len(self.player.playlist):
                    path = self.player.playlist[self.player.current]
                    pos = self.player.get_pos()
                    if pos > 0:
                        self._last_position[path] = pos

            vol = self._vol_btn.get_volume() if hasattr(self, '_vol_btn') else 0.8
            eq_idx = self._eq_combo.get_selected() if hasattr(self, '_eq_combo') else 0
            vis_mode = self._vis._mode if hasattr(self, '_vis') else 0

            self.config["volume"]     = vol
            self.config["eq_preset"]  = eq_idx
            self.config["eq_enabled"] = self.config.get("eq_enabled", True)
            self.config["vis_mode"]   = vis_mode
            self.config["shuffle"]      = self.player.shuffle
            self.config["repeat"]       = self.player.repeat
            self.config["pl_view_mode"] = self._pl_panel._view_mode
            if hasattr(self, "_stack"):
                self.config["last_tab"] = self._stack.get_visible_child_name() or "musik"
            # Radio-Sender merken
            if hasattr(self, "_radio_panel"):
                self.config["last_radio_uuid"] = self._radio_panel._current_uuid or ""
                self.config["last_radio_name"] = self._radio_panel._current_name or ""
                self.config["last_radio_url"]  = self._radio_panel._current_url  or ""

            # ── Datenmüll bereinigen: nur Einträge für vorhandene Playlist-Dateien ──
            pl_set = set(self.player.playlist)
            clean_ratings       = {k: v for k, v in self._rating.items()       if k in pl_set}
            clean_play_count    = {k: v for k, v in self._play_count.items()    if k in pl_set}
            clean_last_position = {k: v for k, v in self._last_position.items() if k in pl_set}

            CONFIG_PATH.write_text(json.dumps({
                "playlist":      self.player.playlist,
                "current":       self.player.current,
                "ratings":       clean_ratings,
                "play_count":    clean_play_count,
                "last_position": clean_last_position,
                "shuffle":       self.player.shuffle,
                "repeat":        self.player.repeat,
                "config":        self.config,
            }, indent=2))
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def _on_close(self, *_):
        # Alle Player stoppen damit kein Audio im Hintergrund weiterläuft
        try:
            self.player.stop()
        except: pass
        try:
            self.radio_player.stop()
        except: pass
        try:
            if self.ab_player.is_playing():
                self.ab_player.play_pause()
        except: pass
        self._save_config()
        return False

    def _apply_css(self):
        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def _build_ui(self):
        hb = Gtk.HeaderBar()
        self.set_titlebar(hb)
        hb.set_show_title_buttons(True)

        for icon, tip, cb in [
            ("preferences-system-symbolic","Einstellungen", self._open_settings),
        ]:
            b = icon_btn(icon, tip); b.connect("clicked", cb); hb.pack_start(b)

        self._pl_toggle = icon_btn("view-list-symbolic","Playlist anzeigen/verstecken")
        self._pl_toggle.connect("clicked", self._toggle_playlist); hb.pack_end(self._pl_toggle)

        self._sleep_btn = icon_btn("weather-clear-night-symbolic","Sleep-Timer")
        self._sleep_btn.connect("clicked", self._open_sleep); hb.pack_end(self._sleep_btn)

        # ── Haupt-Container mit Tab-Leiste ────────────────────────
        main_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(main_vbox)

        # Tab-Leiste
        tab_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        tab_bar.set_margin_start(0); tab_bar.set_margin_end(0)
        tab_bar.set_margin_top(0);   tab_bar.set_margin_bottom(0)
        main_vbox.append(tab_bar)

        self._tab_musik = Gtk.ToggleButton(label="🎵  Musik")
        self._tab_musik.set_active(True)
        self._tab_musik.set_css_classes(["tab-btn", "tab-btn-active"])
        self._tab_musik.connect("toggled", lambda b: self._switch_tab("musik", b))
        tab_bar.append(self._tab_musik)

        self._tab_radio = Gtk.ToggleButton(label="📻  Radio")
        self._tab_radio.set_active(False)
        self._tab_radio.set_css_classes(["tab-btn", "flat"])
        self._tab_radio.connect("toggled", lambda b: self._switch_tab("radio", b))
        tab_bar.append(self._tab_radio)

        self._tab_ab = Gtk.ToggleButton(label="📖  Hörbuch / Hörspiel")
        self._tab_ab.set_active(False)
        self._tab_ab.set_css_classes(["tab-btn", "flat"])
        self._tab_ab.connect("toggled", lambda b: self._switch_tab("hoerbuch", b))
        tab_bar.append(self._tab_ab)

        # Stack
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._stack.set_transition_duration(200)
        self._stack.set_vexpand(True)
        main_vbox.append(self._stack)

        # ── Musik-Seite ───────────────────────────────────────────
        self._root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._root.set_margin_start(12); self._root.set_margin_end(12)
        self._root.set_margin_top(12);   self._root.set_margin_bottom(12)
        self._stack.add_named(self._root, "musik")

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        left.set_hexpand(True); self._root.append(left)
        self._left = left  # für dynamisches Anhängen des lower_stack

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        top.set_margin_start(4); left.append(top)

        cover_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._cover = CoverWidget()
        cover_col.append(self._cover)

        cover_btn_row_musik = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        pick_cover_btn = Gtk.Button(icon_name="image-x-generic-symbolic")
        pick_cover_btn.set_css_classes(["flat"])
        pick_cover_btn.set_tooltip_text("Eigenes Cover-Bild auswählen")
        pick_cover_btn.connect("clicked", self._pick_cover)
        cover_btn_row_musik.append(pick_cover_btn)

        search_cover_musik_btn = Gtk.Button(icon_name="system-search-symbolic")
        search_cover_musik_btn.set_css_classes(["flat"])
        search_cover_musik_btn.set_tooltip_text("Cover online suchen")
        search_cover_musik_btn.connect("clicked", self._search_cover_musik)
        cover_btn_row_musik.append(search_cover_musik_btn)
        cover_col.append(cover_btn_row_musik)

        top.append(cover_col)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        info.set_hexpand(True); info.set_valign(Gtk.Align.CENTER); top.append(info)

        # 1. Bandname (fett, größer)
        self._artist_lbl = Gtk.Label(label="Unbekannt", halign=Gtk.Align.START)
        self._artist_lbl.set_css_classes(["helga-artist"])
        self._artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        info.append(self._artist_lbl)

        # 2. Songname
        self._title_lbl = Gtk.Label(label="Kein Titel", halign=Gtk.Align.START)
        self._title_lbl.set_css_classes(["helga-title"])
        self._title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        self._title_lbl.set_max_width_chars(40); info.append(self._title_lbl)

        # 3. Albumname
        self._album_lbl = Gtk.Label(label="", halign=Gtk.Align.START)
        self._album_lbl.set_css_classes(["helga-album"])
        self._album_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        info.append(self._album_lbl)

        # 4. Tags (Jahr, Format) + Sterne
        self._tags_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._tags_box.set_margin_top(4); info.append(self._tags_box)

        self._stars_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        self._stars_box.set_margin_top(4)
        self._star_btns = []
        for i in range(5):
            sb = Gtk.Button(label="☆"); sb.set_css_classes(["flat"])
            sb.set_tooltip_text(f"{i+1} Stern")
            n = i+1; sb.connect("clicked", lambda b, n=n: self._set_rating(n))
            self._stars_box.append(sb); self._star_btns.append(sb)
        info.append(self._stars_box)

        self._format_lbl = Gtk.Label(label="", halign=Gtk.Align.START)
        self._format_lbl.set_css_classes(["helga-tag"]); info.append(self._format_lbl)

        self._vis = Visualiser()
        vis_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        vis_row.set_margin_start(4)
        vis_lbl = Gtk.Label(label="VIS")
        vis_lbl.set_css_classes(["section-label"])
        vis_row.append(vis_lbl)
        self._vis_btns = []
        for i, name in enumerate(VIS_MODES):
            b = Gtk.Button(label=name)
            b.set_css_classes(["vis-btn", "flat"])
            b.set_tooltip_text(f"Visualiser: {name}")
            b.connect("clicked", lambda btn, idx=i: self._set_vis_mode(idx))
            vis_row.append(b)
            self._vis_btns.append(b)
        left.append(vis_row)
        left.append(self._vis)
        saved_vis = self.config.get("vis_mode", 0)
        self._vis.set_mode(saved_vis)
        self._update_vis_btns(saved_vis)

        prog_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._prog = ProgressBar(self._seek)
        prog_box.append(self._prog)
        time_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._pos_lbl = Gtk.Label(label="0:00", halign=Gtk.Align.START, hexpand=True)
        self._dur_lbl = Gtk.Label(label="0:00", halign=Gtk.Align.END)
        for l in (self._pos_lbl, self._dur_lbl): l.set_css_classes(["helga-time"])
        time_row.append(self._pos_lbl); time_row.append(self._dur_lbl)
        prog_box.append(time_row); left.append(prog_box)

        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        ctrl.set_halign(Gtk.Align.CENTER); ctrl.set_margin_top(4); left.append(ctrl)

        self._shuf_btn = Gtk.ToggleButton()
        self._shuf_btn.set_icon_name("media-playlist-shuffle")
        self._shuf_btn.set_tooltip_text("Zufallswiedergabe")
        self._shuf_btn.set_css_classes(["flat"])
        self._shuf_btn.set_active(self.player.shuffle)
        self._shuf_btn.connect("toggled", self._toggle_shuffle); ctrl.append(self._shuf_btn)

        pb = icon_btn("media-skip-backward","Vorheriger Song")
        pb.connect("clicked", lambda *_: self.player.prev()); ctrl.append(pb)

        self._play_btn = Gtk.Button(icon_name="media-playback-start")
        self._play_btn.set_css_classes(["ctrl-btn-primary"])
        self._play_btn.set_tooltip_text("Abspielen / Pause")
        self._play_btn.connect("clicked", lambda *_: self._play_pause()); ctrl.append(self._play_btn)

        nb = icon_btn("media-skip-forward","Nächster Song")
        nb.connect("clicked", lambda *_: self.player.next()); ctrl.append(nb)

        self._rep_btn = Gtk.Button(icon_name="media-playlist-repeat")
        self._rep_btn.set_css_classes(["flat"])
        self._rep_btn.set_tooltip_text("Wiederholen: Aus")
        self._rep_btn.connect("clicked", self._cycle_repeat); ctrl.append(self._rep_btn)

        self._vol_btn = VolumeButton(self.player)
        self._vol_btn.set_volume(self.config.get("volume", 0.8))
        ctrl.append(self._vol_btn)

        eq_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        eq_row.set_margin_top(2); left.append(eq_row)
        eq_lbl = Gtk.Label(label="EQ"); eq_lbl.set_css_classes(["section-label"]); eq_row.append(eq_lbl)

        self._eq_toggle = Gtk.ToggleButton(label="EIN")
        self._eq_toggle.set_css_classes(["vis-btn"])
        self._eq_toggle.set_tooltip_text("Equalizer ein/ausschalten")
        eq_enabled = self.config.get("eq_enabled", True)
        self._eq_toggle.set_active(eq_enabled)
        self._eq_toggle.connect("toggled", self._on_eq_toggle)
        eq_row.append(self._eq_toggle)
        self._update_eq_toggle_label(eq_enabled)

        self._eq_combo = Gtk.DropDown.new_from_strings(list(EQ_PRESETS.keys()) + ["Manuell"])
        self._eq_combo.set_tooltip_text("EQ-Preset"); self._eq_combo.set_hexpand(True)
        saved_eq = self.config.get("eq_preset", 0)
        self._eq_combo.set_selected(saved_eq)
        self._eq_combo.connect("notify::selected", self._eq_changed); eq_row.append(self._eq_combo)

        # ── Manueller EQ: 10 vertikale Slider ────────────────────
        self._eq_manual_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._eq_manual_box.set_css_classes(["eq-manual-row"])
        self._eq_manual_box.set_margin_top(4)
        self._eq_manual_box.set_visible(False)
        self._eq_sliders = []
        eq_band_labels = ["32Hz","64Hz","125Hz","250Hz","500Hz","1kHz","2kHz","4kHz","8kHz","16kHz"]
        saved_manual = self.config.get("eq_manual", [0]*10)
        for i, freq in enumerate(eq_band_labels):
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            col.set_hexpand(True)
            val_lbl = Gtk.Label(label=f"{saved_manual[i]:+.0f}")
            val_lbl.set_css_classes(["eq-band-val"])
            val_lbl.set_halign(Gtk.Align.CENTER)
            col.append(val_lbl)
            sl = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, -12, 12, 0.5)
            sl.set_value(saved_manual[i])
            sl.set_inverted(True)
            sl.set_draw_value(False)
            sl.set_vexpand(True)
            sl.set_size_request(-1, 80)
            def _on_slide(s, lbl=val_lbl, idx=i):
                v = s.get_value()
                lbl.set_label(f"{v:+.0f}")
                gains = [self._eq_sliders[j].get_value() for j in range(10)]
                self.config["eq_manual"] = gains
                if self.config.get("eq_enabled", True):
                    self.player.set_eq_preset("Manuell", gains)
            sl.connect("value-changed", _on_slide)
            self._eq_sliders.append(sl)
            col.append(sl)
            freq_lbl = Gtk.Label(label=freq)
            freq_lbl.set_css_classes(["eq-band-lbl"])
            freq_lbl.set_halign(Gtk.Align.CENTER)
            col.append(freq_lbl)
            self._eq_manual_box.append(col)
        left.append(self._eq_manual_box)

        # ── Album-Cover-Grid (bleibt in left, immer sichtbar wenn maximiert) ──
        self._album_grid = AlbumGridWidget(self._on_album_tile_click)
        left.append(self._album_grid)
        self._album_grid.set_visible(False)  # erst bei Maximierung

        # ── Mittlere Spalte: Songtext (nur maximiert, zwischen left und playlist) ──
        self._mid_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._mid_col.set_hexpand(True)
        self._mid_col.set_margin_start(16); self._mid_col.set_margin_end(8)
        self._mid_col.set_visible(False)  # versteckt im normalen Fenster

        lyrics_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lyrics_hdr.set_margin_bottom(6)
        lyrics_lbl = Gtk.Label(label="SONGTEXT")
        lyrics_lbl.set_css_classes(["section-label"])
        lyrics_lbl.set_hexpand(True); lyrics_lbl.set_halign(Gtk.Align.START)
        lyrics_hdr.append(lyrics_lbl)
        lyrics_reload_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        lyrics_reload_btn.set_css_classes(["flat"])
        lyrics_reload_btn.set_tooltip_text("Songtext neu laden")
        lyrics_reload_btn.connect("clicked", lambda *_: self._load_lyrics(force=True))
        lyrics_hdr.append(lyrics_reload_btn)
        self._mid_col.append(lyrics_hdr)

        self._lyrics_scroll = Gtk.ScrolledWindow()
        self._lyrics_scroll.set_vexpand(True)
        self._lyrics_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._lyrics_listbox = Gtk.ListBox()
        self._lyrics_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._lyrics_listbox.set_css_classes(["lyrics-listbox"])
        self._lyrics_scroll.set_child(self._lyrics_listbox)
        self._mid_col.append(self._lyrics_scroll)

        self._lyrics_loaded_path = ""
        self._lyrics_lines = []        # [(time_ms_or_None, text), ...]
        self._lyrics_synced = False    # True wenn LRC mit Timestamps
        self._lyrics_active_row = -1   # aktuell hervorgehobene Zeile
        self._lyrics_timer_id = None   # GLib.timeout für Sync

        self._pl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self._pl_box.set_margin_start(12); self._pl_box.set_size_request(300, -1)
        self._root.append(self._mid_col)   # mittlere Spalte VOR playlist
        self._root.append(self._pl_box)

        pl_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pl_lbl = Gtk.Label(label="PLAYLIST"); pl_lbl.set_css_classes(["section-label"])
        pl_lbl.set_hexpand(True); pl_lbl.set_halign(Gtk.Align.START); pl_header.append(pl_lbl)
        add_file_btn = icon_btn("document-open-symbolic", "Dateien hinzufügen")
        add_file_btn.connect("clicked", self._open_files); pl_header.append(add_file_btn)
        add_folder_btn = icon_btn("folder-open-symbolic", "Ordner hinzufügen")
        add_folder_btn.connect("clicked", self._open_folder); pl_header.append(add_folder_btn)
        scan_btn = icon_btn("folder-visiting-symbolic", "Ordner jetzt scannen")
        scan_btn.connect("clicked", lambda *_: self._do_auto_scan()); pl_header.append(scan_btn)
        sep_pl = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        sep_pl.set_margin_start(2); sep_pl.set_margin_end(2)
        sep_pl.set_margin_top(4); sep_pl.set_margin_bottom(4)
        pl_header.append(sep_pl)
        smart_btn = icon_btn("edit-find-symbolic", "Intelligente Playlist erstellen")
        smart_btn.connect("clicked", self._open_smart_playlist); pl_header.append(smart_btn)
        clr_btn = icon_btn("edit-clear-all-symbolic","Playlist leeren"); clr_btn.connect("clicked", self._clear_playlist); pl_header.append(clr_btn)
        srt_btn = icon_btn("view-sort-ascending-symbolic","Nach Name sortieren"); srt_btn.connect("clicked", self._sort_playlist); pl_header.append(srt_btn)
        self._pl_box.append(pl_header)
        self._search = Gtk.SearchEntry(); self._search.set_placeholder_text("Suche …")
        self._search.connect("search-changed", self._filter_playlist); self._pl_box.append(self._search)
        self._pl_panel = PlaylistPanel(self._pl_select, self._pl_remove); self._pl_box.append(self._pl_panel)
        # Wenn Metadaten fertig geladen → Album-Grid aktualisieren
        self._pl_panel.on_meta_ready = self._refresh_album_grid
        self._pl_panel.on_sort_alpha_changed = lambda v: self._album_grid.set_sort_alpha(v)
        # Gespeicherten View-Modus wiederherstellen (Standard: album)
        saved_view = self.config.get("pl_view_mode", "album")
        GLib.idle_add(lambda: self._pl_panel._set_view(saved_view) or False)

        pl_footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1); pl_footer.set_margin_top(4)
        self._pl_count_lbl = Gtk.Label(label=""); self._pl_count_lbl.set_halign(Gtk.Align.START)
        self._pl_count_lbl.set_css_classes(["pl-row-title"]); pl_footer.append(self._pl_count_lbl)
        self._total_time_lbl = Gtk.Label(label=""); self._total_time_lbl.set_halign(Gtk.Align.START)
        self._total_time_lbl.set_css_classes(["pl-row-sub"])
        pl_footer.append(self._total_time_lbl); self._pl_box.append(pl_footer)

        dt = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY); dt.connect("drop", self._drop); self.add_controller(dt)
        kc = Gtk.EventControllerKey.new()
        kc.connect("key-pressed", self._key_pressed)
        self.add_controller(kc)

        self._restore_repeat_state()
        if self.player.shuffle:
            css = self._shuf_btn.get_css_classes()
            if "active-toggle" not in css: css.append("active-toggle")
            self._shuf_btn.set_css_classes(css)

        self._refresh_playlist()
        if 0 <= self.player.current < len(self.player.playlist):
            self._on_load(self.player.current)

        # ── Radio-Seite in Stack einhängen ────────────────────────
        self._radio_panel = RadioPanel(
            self.radio_player,
            vol_getter=lambda: self._vol_btn.get_volume(),
            notify_cb=self._radio_notify,
        )
        self._stack.add_named(self._radio_panel, "radio")

        # ── Hörbuch-Seite in Stack einhängen ─────────────────────
        self._ab_panel = AudiobookPanel(
            self.ab_player,
            self.ab_lib,
            vol_getter=lambda: self._vol_btn.get_volume(),
            config=self.config,
            save_config_cb=self._save_config,
        )
        self._stack.add_named(self._ab_panel, "hoerbuch")
        self._ab_panel._on_title_change = lambda t: self.set_title(t)

    def _update_window_title(self):
        """Setzt Fenstertitel passend zum aktiv spielenden Player."""
        # Priorität: was gerade tatsächlich spielt
        if self.player.is_playing() or (
                self.player.current >= 0 and
                self._stack.get_visible_child_name() == "musik"):
            # Musik läuft oder Musik-Tab aktiv → Titel aus _apply_meta (schon gesetzt)
            return
        tab = self._stack.get_visible_child_name() if hasattr(self, '_stack') else "musik"
        if tab == "radio":
            rp = self._radio_panel
            if rp._current_name:
                song = rp._now_song.get_label()
                self.set_title(f"{rp._current_name} — {song}" if song
                               else f"📻 {rp._current_name}")
            else:
                self.set_title("Helga — Radio")
        elif tab == "hoerbuch":
            ab = self._ab_panel
            if ab._current_book:
                b = ab._current_book
                author = b.get("author") or b.get("artist") or ""
                title  = b.get("title") or ""
                self.set_title(f"{author} — {title}" if (author and title)
                               else title or "Helga — Hörbuch")
            else:
                self.set_title("Helga — Hörbuch")
        elif tab == "musik":
            pass  # bleibt wie von _apply_meta gesetzt

    def _switch_tab(self, name, btn):
        if getattr(self, '_tab_switching', False):
            return
        self._tab_switching = True
        try:
            self._stack.set_visible_child_name(name)
            # Alle Tabs zurücksetzen
            tabs = [
                ("musik",    self._tab_musik,  ["tab-btn","tab-btn-active"], ["tab-btn","flat"]),
                ("radio",    self._tab_radio,  ["tab-btn","tab-btn-active"], ["tab-btn","flat"]),
                ("hoerbuch", self._tab_ab,     ["tab-btn","tab-btn-active"], ["tab-btn","flat"]),
            ]
            for tab_name, tab_btn, active_css, inactive_css in tabs:
                if tab_name == name:
                    tab_btn.set_css_classes(active_css); tab_btn.set_active(True)
                else:
                    tab_btn.set_css_classes(inactive_css); tab_btn.set_active(False)

            # Fenstertitel für neuen Tab setzen
            if name == "musik":
                # Musik-Tab: Titel direkt aus aktuellem Track
                if self.player.current >= 0 and self.player.current < len(self.player.playlist):
                    path = self.player.playlist[self.player.current]
                    with self._pl_panel._meta_lock:
                        m = dict(self._pl_panel._meta.get(path, {}))
                    if m:
                        GLib.idle_add(lambda: self.set_title(
                            f"{m.get('artist','?')} — {m.get('title','?')}"))
            else:
                GLib.idle_add(self._update_window_title)

            if name == "musik":
                # Radio pausieren (Sender merken für Rückkehr)
                if self.radio_player.is_playing():
                    self.radio_player.stop()
                    if hasattr(self, '_radio_panel'):
                        self._radio_panel._live_dot.set_label("")
                        self._radio_panel._fill_list()
                # Hörbuch pausieren
                if self.ab_player.is_playing():
                    self.ab_player.play_pause()
                    if hasattr(self, '_ab_panel'):
                        self._ab_panel._update_play_btn(False)
                # Volume wiederherstellen
                target = self._vol_btn.get_volume()
                self.player.set_vol(target)
                self._update_play_state(self.player.is_playing())

            elif name == "radio":
                # Musik ausblenden
                if self.player.is_playing():
                    self.fader.fade_out(callback=lambda: self._update_play_state(False))
                # Hörbuch pausieren
                if self.ab_player.is_playing():
                    self.ab_player.play_pause()
                    if hasattr(self, '_ab_panel'):
                        self._ab_panel._update_play_btn(False)
                # Radio-Sender fortsetzen falls einer gespeichert ist
                if hasattr(self, '_radio_panel'):
                    self._radio_panel.resume_if_needed(self._vol_btn.get_volume())

            elif name == "hoerbuch":
                # Musik ausblenden
                if self.player.is_playing():
                    self.fader.fade_out(callback=lambda: self._update_play_state(False))
                # Radio pausieren (Sender merken für Rückkehr)
                if self.radio_player.is_playing():
                    self.radio_player.stop()
                    if hasattr(self, '_radio_panel'):
                        self._radio_panel._live_dot.set_label("")
                        self._radio_panel._fill_list()
                # Volume für Hörbuch setzen
                self.ab_player.set_vol(self._vol_btn.get_volume())
        finally:
            self._tab_switching = False

    def _radio_notify(self, title, artist):
        """Song-Benachrichtigung vom Radio-Stream — OHNE Ton."""
        GLib.idle_add(self._update_window_title)
        try:
            subprocess.Popen([
                "notify-send",
                "-a", "Helga Radio",
                "-i", "audio-x-generic",
                "--hint=int:suppress-sound:1",   # kein Benachrichtigungs-Ton
                "-t", "4000",
                f"📻 {title}",
                artist or "",
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _show_notification(self, title, artist, album=""):
        try:
            body = " · ".join(filter(None, [artist, album]))
            subprocess.Popen([
                "notify-send",
                "-a", "Helga",
                "-i", "audio-x-generic",
                "-t", "4000",
                title,
                body,
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    def _set_vis_mode(self, idx):
        self._vis.set_mode(idx)
        self.config["vis_mode"] = idx
        self._update_vis_btns(idx)
        self._save_config()

    def _update_vis_btns(self, active_idx):
        for i, b in enumerate(self._vis_btns):
            if i == active_idx:
                b.set_css_classes(["vis-btn", "vis-btn-active"])
            else:
                b.set_css_classes(["vis-btn", "flat"])

    def _on_eq_toggle(self, btn):
        enabled = btn.get_active()
        self._update_eq_toggle_label(enabled)
        self.config["eq_enabled"] = enabled
        if enabled:
            idx = self._eq_combo.get_selected()
            is_manual = (idx == len(EQ_PRESETS))
            if is_manual:
                gains = self.config.get("eq_manual", [0]*10)
                self.player.set_eq_preset("Manuell", gains)
            else:
                keys = list(EQ_PRESETS.keys())
                if 0 <= idx < len(keys):
                    self.player.set_eq_preset(keys[idx], EQ_PRESETS[keys[idx]])
        else:
            self.player.set_eq_enabled(False)
        self._save_config()

    def _update_eq_toggle_label(self, enabled):
        if enabled:
            self._eq_toggle.set_label("EIN")
            self._eq_toggle.set_css_classes(["vis-btn", "vis-btn-active"])
        else:
            self._eq_toggle.set_label("AUS")
            self._eq_toggle.set_css_classes(["vis-btn", "flat", "eq-off"])

    def _restore_repeat_state(self):
        modes  = ["none","all","one"]
        icons  = ["media-playlist-repeat","media-playlist-repeat","media-playlist-repeat-song"]
        tips   = ["Wiederholen: Aus","Wiederholen: Alle","Wiederholen: Einen"]
        try:
            idx = modes.index(self.player.repeat)
        except:
            idx = 0; self.player.repeat = "none"
        self._rep_btn.set_icon_name(icons[idx])
        self._rep_btn.set_tooltip_text(tips[idx])
        if idx > 0:
            css = self._rep_btn.get_css_classes()
            if "active-toggle" not in css: css.append("active-toggle")
            self._rep_btn.set_css_classes(css)

    def _pick_cover(self, *_):
        if self.player.current < 0 or not self.player.playlist:
            return
        d = Gtk.FileDialog()
        f = Gtk.FileFilter(); f.set_name("Bilder")
        for ext in ("*.jpg","*.jpeg","*.png","*.webp","*.bmp","*.gif"):
            f.add_pattern(ext)
        ls = Gio.ListStore.new(Gtk.FileFilter); ls.append(f)
        d.set_filters(ls)
        d.open(self, None, self._cover_file_chosen)

    def _search_cover_musik(self, *_):
        """Dialog: Interpret/Titel eingeben, dann Cover online suchen."""
        if self.player.current < 0 or not self.player.playlist:
            return
        path = self.player.playlist[self.player.current]
        with self._pl_panel._meta_lock:
            meta = dict(self._pl_panel._meta.get(path, {}))

        dlg = Gtk.Dialog(title="Cover suchen", transient_for=self, modal=True)
        dlg.set_default_size(360, 180)
        box = dlg.get_content_area()
        box.set_spacing(10); box.set_margin_start(16); box.set_margin_end(16)
        box.set_margin_top(12); box.set_margin_bottom(12)

        grid = Gtk.Grid(row_spacing=8, column_spacing=10)
        box.append(grid)

        grid.attach(Gtk.Label(label="Interpret:", halign=Gtk.Align.START), 0, 0, 1, 1)
        artist_entry = Gtk.Entry()
        artist_entry.set_text(meta.get("artist",""))
        artist_entry.set_hexpand(True)
        grid.attach(artist_entry, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label="Album / Titel:", halign=Gtk.Align.START), 0, 1, 1, 1)
        album_entry = Gtk.Entry()
        album_entry.set_text(meta.get("album","") or meta.get("title",""))
        album_entry.set_hexpand(True)
        grid.attach(album_entry, 1, 1, 1, 1)

        status_lbl = Gtk.Label(label="")
        status_lbl.set_halign(Gtk.Align.START)
        status_lbl.set_css_classes(["dim-label"])
        box.append(status_lbl)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END); btn_box.set_margin_top(8)
        cancel_btn = Gtk.Button(label="Abbrechen")
        cancel_btn.connect("clicked", lambda *_: dlg.close())
        btn_box.append(cancel_btn)
        search_btn = Gtk.Button(label="Suchen")
        search_btn.add_css_class("suggested-action")
        btn_box.append(search_btn)
        box.append(btn_box)

        def _do_search(*_):
            artist = artist_entry.get_text().strip()
            album  = album_entry.get_text().strip()
            if not album: return
            search_btn.set_sensitive(False)
            status_lbl.set_label("Suche läuft …")
            def _fetch():
                pixbuf = None
                if artist:
                    pixbuf = self.cover_downloader.search_cover(artist, album, path)
                if not pixbuf:
                    pixbuf = self.cover_downloader.search_cover(album, album, path)
                def _done():
                    if pixbuf:
                        if path not in self._cache:
                            self._cache[path] = {}
                        self._cache[path]["cover"] = pixbuf
                        self._cover.set_pixbuf(pixbuf)
                        dlg.close()
                    else:
                        status_lbl.set_label("Kein Cover gefunden.")
                        search_btn.set_sensitive(True)
                GLib.idle_add(_done)
            threading.Thread(target=_fetch, daemon=True).start()

        search_btn.connect("clicked", _do_search)
        album_entry.connect("activate", _do_search)
        dlg.present()

    def _cover_file_chosen(self, dialog, result):
        try:
            file = dialog.open_finish(result)
            path = file.get_path()
            if not path: return
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            cur_path = self.player.playlist[self.player.current]
            if cur_path not in self._cache:
                self._cache[cur_path] = {}
            self._cache[cur_path]["cover"] = pixbuf
            self._cover.set_pixbuf(pixbuf)
        except Exception as e:
            print(f"Fehler beim Cover-Laden: {e}")

    def _open_smart_playlist(self, *_):
        dialog = SmartPlaylistDialog(self, self.smart_gen)
        dialog.connect("response", self._on_smart_playlist_response); dialog.present()

    def _on_smart_playlist_response(self, dialog, response):
        if response == Gtk.ResponseType.OK and dialog.result_playlist:
            self._add_files(dialog.result_playlist, ask=False, action="replace")

    def _open_settings(self, *_):
        dialog = SettingsDialog(self, self.config)
        dialog.connect("response", self._on_settings_response); dialog.present()

    def _apply_font_size(self, size):
        """Skaliert alle UI-Schriften dynamisch per CSS."""
        s = int(size)
        lines = [
            ".pl-row-title  { font-size: " + str(s) + "px; }",
            ".pl-row-artist { font-size: " + str(s) + "px; font-weight: bold; }",
            ".album-tile-title { font-size: " + str(s) + "px; font-weight: bold; }",
            ".album-tile-sub   { font-size: " + str(max(s-2,8)) + "px; color: @theme_unfocused_fg_color; }",
            ".pl-row-sub    { font-size: " + str(max(s-2,8)) + "px; color: @theme_unfocused_fg_color; }",
            ".pl-group-name { font-size: " + str(s+1) + "px; font-weight: bold; color: @accent_color; }",
            ".helga-artist  { font-size: " + str(s+10) + "px; font-weight: bold; color: @theme_fg_color; }",
            ".helga-title   { font-size: " + str(s+8) + "px; color: @theme_fg_color; }",
            ".helga-album   { font-size: " + str(s+6) + "px; color: @theme_unfocused_fg_color; }",
            ".radio-name    { font-size: " + str(s+1) + "px; }",
            ".radio-info    { font-size: " + str(max(s-1,8)) + "px; color: @theme_unfocused_fg_color; }",
            ".ab-title      { font-size: " + str(s+1) + "px; font-weight: bold; }",
            ".ab-author     { font-size: " + str(max(s-1,8)) + "px; color: @theme_unfocused_fg_color; }",
            ".lyrics-text   { font-size: " + str(s+1) + "px; line-height: 1.6; }",
        ]
        dynamic_css = chr(10).join(lines).encode()
        prov = Gtk.CssProvider()
        prov.load_from_data(dynamic_css)
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)

    def _on_settings_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            self.fader.set_fade_enabled(self.config["fade_enabled"])
            self.fader.set_fade_duration(self.config["fade_duration"])
            self.fader.set_fade_curve(self.config["fade_curve"])
            self._schedule_auto_scan()
            if hasattr(self, '_ab_panel'):
                self._ab_panel.update_scan_config(self.config)
            self._apply_font_size(self.config.get("font_size", 16))
            self._save_config()

    def _play_pause(self):
        if not self.player.playlist: 
            return
        if self.player.current < 0:
            self.player.load(0)
            GLib.timeout_add(300, self._start_fade_in)
            return

        playing = self.player.is_playing()

        if playing:
            if self.config.get("resume_enabled", True) and self.player.current >= 0:
                if self.player.current < len(self.player.playlist):
                    path = self.player.playlist[self.player.current]
                    pos = self.player.get_pos()
                    if pos > 0:
                        self._last_position[path] = pos
            self.fader.fade_out(callback=lambda: self._update_play_state(False))
        else:
            self.player.pl.set_state(Gst.State.PLAYING)
            GLib.timeout_add(80, self._start_fade_in)

    def _start_fade_in(self):
        self.fader.fade_in(callback=lambda: self._update_play_state(True))
        return False

    def _update_play_state(self, playing):
        self._cover.playing = playing
        self._vis.playing   = playing
        self._play_btn.set_icon_name("media-playback-pause" if playing else "media-playback-start")

    def _on_eos(self):
        if self.player.current >= 0 and self.player.current < len(self.player.playlist):
            path = self.player.playlist[self.player.current]
            self._play_count[path] = self._play_count.get(path, 0) + 1
            self._save_config()
        # Kein fade_out hier — fade_out ruft set_state(PAUSED) auf und erzeugt
        # eine Race-Condition mit dem load() im nächsten Song (NULL→PLAYING).
        # Stattdessen: direkt next() aufrufen, fade_in wird in _on_load getriggert.
        self._eos_triggered = True
        if self._queued_next >= 0:
            idx = self._queued_next
            self._queued_next = -1
            self.player.current = idx
            self.player.load(idx)
        else:
            self.player.next(auto=True)

    def _on_load(self, idx):
        self._lyrics_loaded_path = ""
        GLib.idle_add(self._load_lyrics)
        self._pl_panel.highlight(idx)
        self._update_meta(idx)
        # Aktives Album im Grid markieren
        if 0 <= idx < len(self.player.playlist):
            path = self.player.playlist[idx]
            meta  = self._pl_panel._get_meta(path)
            album = meta.get("album", "") or "Unbekanntes Album"
            self._album_grid.set_active_album(album)

        # Nach automatischem Song-Ende (EOS): fade_in starten.
        if self._eos_triggered:
            self._eos_triggered = False
            GLib.timeout_add(250, self._start_fade_in)

    def _seek(self, frac): 
        self.player.seek(frac)

    def _toggle_shuffle(self, btn):
        self.player.shuffle = btn.get_active()
        css = btn.get_css_classes()
        if btn.get_active():
            if "active-toggle" not in css: css.append("active-toggle")
        else:
            if "active-toggle" in css: css.remove("active-toggle")
        btn.set_css_classes(css); self._save_config()

    def _cycle_repeat(self, *_):
        modes  = ["none","all","one"]
        icons  = ["media-playlist-repeat","media-playlist-repeat","media-playlist-repeat-song"]
        tips   = ["Wiederholen: Aus","Wiederholen: Alle","Wiederholen: Einen"]
        cur    = modes.index(self.player.repeat)
        nxt    = (cur + 1) % 3
        self.player.repeat = modes[nxt]
        self._rep_btn.set_icon_name(icons[nxt]); self._rep_btn.set_tooltip_text(tips[nxt])
        css = self._rep_btn.get_css_classes()
        if nxt > 0:
            if "active-toggle" not in css: css.append("active-toggle")
        else:
            if "active-toggle" in css: css.remove("active-toggle")
        self._rep_btn.set_css_classes(css); self._save_config()

    def _eq_changed(self, combo, *_):
        all_keys = list(EQ_PRESETS.keys()) + ["Manuell"]
        idx  = combo.get_selected()
        is_manual = (idx == len(EQ_PRESETS))
        self._eq_manual_box.set_visible(is_manual)
        if is_manual:
            gains = self.config.get("eq_manual", [0]*10)
            if self.config.get("eq_enabled", True):
                self.player.set_eq_preset("Manuell", gains)
        elif 0 <= idx < len(EQ_PRESETS):
            keys = list(EQ_PRESETS.keys())
            if self.config.get("eq_enabled", True):
                self.player.set_eq_preset(keys[idx], EQ_PRESETS[keys[idx]])
        self.config["eq_preset"] = idx
        self._save_config()

    def _update_meta(self, idx):
        if not (0 <= idx < len(self.player.playlist)): return
        path = self.player.playlist[idx]
        if path not in self._cache:
            def _load():
                cover_dl = self.cover_downloader if self.config.get("auto_cover", True) else None
                m = get_meta(path, cover_dl)
                self._cache[path] = m
                GLib.idle_add(self._apply_meta, idx, path, m)
            threading.Thread(target=_load, daemon=True).start()
        else:
            self._apply_meta(idx, path, self._cache[path])

    def _apply_meta(self, idx, path, m):
        self._artist_lbl.set_label(m.get("artist","Unbekannt"))
        self._title_lbl.set_label(m.get("title","?"))
        self._album_lbl.set_label(m.get("album",""))
        self._cover.set_pixbuf(m.get("cover"))
        while child := self._tags_box.get_first_child(): self._tags_box.remove(child)
        year = (m.get("year","") or "")[:4]
        if year:
            lbl = Gtk.Label(label=year); lbl.set_css_classes(["helga-tag"]); self._tags_box.append(lbl)
        ext = Path(path).suffix.upper().lstrip("."); self._format_lbl.set_label(ext)
        self._refresh_stars(self._rating.get(path, 0))
        self.set_title(f"{m.get('artist','?')} — {m.get('title','?')}")

        # Benachrichtigung hier — Metadaten sind jetzt garantiert vollständig
        title  = m.get("title",  Path(path).stem)
        artist = m.get("artist", "")
        album  = m.get("album",  "")
        self._show_notification(title, artist, album)

    def _refresh_stars(self, n):
        for i, b in enumerate(self._star_btns): b.set_label("★" if i < n else "☆")

    def _set_rating(self, n):
        if 0 <= self.player.current < len(self.player.playlist):
            path = self.player.playlist[self.player.current]
            if self._rating.get(path, 0) == n: n = 0
            self._rating[path] = n; self._refresh_stars(n); self._save_config()

    def _add_files(self, paths, ask=True, action="add"):
        if not paths: return
        if ask:
            dialog = AddToPlaylistDialog(self, paths)
            dialog.connect("response", lambda d, r: self._on_add_response(d, r, paths))
            dialog.present()
        else:
            self._execute_add_action(paths, action)

    def _on_add_response(self, dialog, response, paths):
        if response == Gtk.ResponseType.OK and dialog.result:
            self._execute_add_action(paths, dialog.result)

    # ── Hörbuch-Erkennung ────────────────────────────────────────
    _AB_KEYWORDS = frozenset({"hörbuch", "hörspiel", "audiobook", "audio book",
                               "audiobooks", "hoerbuch", "hoerspiel"})

    @staticmethod
    def _read_genre_fast(path):
        """Liest Genre-Tag direkt aus ID3v2/MP4-Header — ohne Discoverer, sehr schnell."""
        try:
            ext = Path(path).suffix.lower()
            with open(path, "rb") as f:
                raw = f.read(10240)   # erste 10 KB reichen für ID3-Header

            # ── ID3v2 (mp3, aiff, …) ─────────────────────────────
            if raw[:3] == b"ID3":
                # Frame-Suche nach TCON (Genre)
                i = 10
                if raw[5] & 0x40:   # extended header vorhanden
                    ext_sz = int.from_bytes(raw[10:14], "big"); i += ext_sz + 4
                while i + 10 < len(raw):
                    fid = raw[i:i+4]
                    fsz = int.from_bytes(raw[i+4:i+8], "big")
                    if fsz <= 0 or fsz > 8192: break
                    if fid == b"TCON":
                        enc = raw[i+10]
                        txt = raw[i+11:i+10+fsz]
                        try:
                            genre = txt.decode("utf-16" if enc in (1,2) else "latin-1",
                                               errors="ignore").strip().lower()
                            genre = genre.strip("\x00")
                            return genre
                        except: pass
                    i += 10 + fsz

            # ── MP4/M4A/M4B ──────────────────────────────────────
            elif ext in (".m4a", ".m4b", ".mp4", ".aac"):
                # Suche nach ©gen atom (UTF-8-Text)
                idx = raw.find(b"\xa9gen")
                if idx >= 0 and idx + 20 < len(raw):
                    data_start = raw.find(b"data", idx, idx + 50)
                    if data_start >= 0:
                        txt = raw[data_start+8:data_start+80]
                        return txt.decode("utf-8", errors="ignore").strip().lower()

            # ── OGG/FLAC ─────────────────────────────────────────
            elif ext in (".ogg", ".flac", ".opus"):
                # Suche nach GENRE= in Vorbis Comment
                lower = raw.lower()
                idx = lower.find(b"genre=")
                if idx >= 0:
                    end = lower.find(b"\x00", idx)
                    txt = raw[idx+6:end if end > idx else idx+60]
                    return txt.decode("utf-8", errors="ignore").strip().lower()

        except: pass
        return ""

    def _is_audiobook_file(self, path):
        genre = self._read_genre_fast(path)
        return any(kw in genre for kw in self._AB_KEYWORDS)

    def _execute_add_action(self, paths, action):
        """Prüft Genre-Tags im Hintergrund (schnell), fügt danach nur Musik hinzu."""
        def _check_and_add():
            music_paths, ab_count = [], 0
            for path in paths:
                if self._is_audiobook_file(path):
                    ab_count += 1
                else:
                    music_paths.append(path)
            GLib.idle_add(self._execute_add_action_raw, music_paths, action, ab_count)
        threading.Thread(target=_check_and_add, daemon=True).start()

    def _execute_add_action_raw(self, paths, action, ab_count=0):
        """Fügt Pfade direkt zur Playlist hinzu (nach Filterung)."""
        if ab_count > 0:
            self._show_audiobook_hint(ab_count)
        if not paths and not self.player.playlist:
            self._refresh_playlist(); self._save_config(); return False
        if action == "replace":
            self.player.stop(); self.player.playlist = paths.copy()
            self.player.current = 0 if paths else -1
            if self.player.current >= 0:
                self.player.load(0)
                GLib.timeout_add(300, self._start_fade_in)
        elif action in ("add", "new"):
            new_paths = [p for p in paths if p not in self.player.playlist]
            self.player.playlist.extend(new_paths)
            if self.player.current < 0 and self.player.playlist:
                self.player.current = 0
                self.player.load(0)
                GLib.timeout_add(300, self._start_fade_in)
        self._refresh_playlist(); self._save_config()
        return False

    def _show_audiobook_hint(self, count):
        """Zeigt kurzen Hinweis-Banner wenn Hörbücher gefunden wurden."""
        if hasattr(self, "_ab_hint_bar") and self._ab_hint_bar.get_visible():
            return False
        bar = Gtk.InfoBar()
        bar.set_message_type(Gtk.MessageType.INFO)
        bar.set_show_close_button(True)
        lbl = Gtk.Label(
            label=f"\U0001f4d6  {count} Hörbuch/Hörspiel-Datei{'en' if count!=1 else ''} gefunden "
                  f"– {'sie sind' if count!=1 else 'sie ist'} nur im Tab "
                  f"'Hörbuch / Hörspiel' verfügbar.")
        lbl.set_wrap(True)
        bar.add_child(lbl)
        bar.connect("response", lambda b, _: (b.set_visible(False), False))
        self._ab_hint_bar = bar
        # In root-box ganz oben einfügen (vor Stack)
        self._root.prepend(bar)
        GLib.timeout_add(8000, lambda: bar.set_visible(False) or False)
        return False

    def _refresh_playlist(self):
        self._pl_panel.set_playlist(self.player.playlist, self.player.current)
        n = len(self.player.playlist)
        self._pl_count_lbl.set_label(f"{n} Song{'s' if n!=1 else ''}")
        total_seconds = 0
        for p in self.player.playlist:
            if p in self._cache and self._cache[p].get("duration", 0) > 0:
                total_seconds += self._cache[p]["duration"] / Gst.SECOND
            else:
                total_seconds += 180
        days    = int(total_seconds // 86400)
        hours   = int((total_seconds % 86400) // 3600)
        minutes = int((total_seconds % 3600) // 60)
        if days > 0:
            time_str = f"( {days}d {hours}h {minutes:02d}min )"
        elif hours > 0:
            time_str = f"( {hours}h {minutes:02d}min )"
        else:
            time_str = f"( {minutes}min )"
        self._total_time_lbl.set_label(time_str)
        # Album-Grid aktualisieren (nutzt Metadaten aus PlaylistPanel-Cache)
        GLib.idle_add(self._refresh_album_grid)

    def _on_maximized_changed(self, *_):
        maximized = self.is_maximized()
        self._album_grid.set_visible(maximized)
        self._mid_col.set_visible(maximized)
        if maximized:
            GLib.idle_add(self._refresh_album_grid)
            GLib.idle_add(self._load_lyrics)

    def _refresh_album_grid(self):
        """Album-Grid mit aktuellen Metadaten aus dem PlaylistPanel-Cache befüllen."""
        with self._pl_panel._meta_lock:
            meta_snapshot = dict(self._pl_panel._meta)
        self._album_grid.update_from_playlist(self.player.playlist, meta_snapshot)
        # Aktives Album direkt markieren
        if 0 <= self.player.current < len(self.player.playlist):
            path  = self.player.playlist[self.player.current]
            meta  = meta_snapshot.get(path, {})
            album = meta.get("album", "") or "Unbekanntes Album"
            self._album_grid.set_active_album(album)
        return False

    def _lyrics_parse_lrc(self, text):
        """Parsed LRC-Format zu [(ms, text), ...]. Gibt (lines, synced) zurueck."""
        import re
        lines = []
        synced = False
        lrc_pat = re.compile(r"^\[(\d+):(\d+)[.:](\d+)\](.*)")
        for raw in text.splitlines():
            m = lrc_pat.match(raw.strip())
            if m:
                ms = (int(m.group(1))*60 + int(m.group(2)))*1000 + int(m.group(3).ljust(3,"0")[:3])
                txt = m.group(4).strip()
                lines.append((ms, txt))
                synced = True
            elif raw.strip() and not synced:
                lines.append((None, raw.strip()))
        if not lines:
            lines.append((None, ""))
        return lines, synced

    def _lyrics_set_lines(self, lines):
        """Baut die ListBox mit allen Zeilen neu auf."""
        while row := self._lyrics_listbox.get_row_at_index(0):
            self._lyrics_listbox.remove(row)
        self._lyrics_lines = lines
        self._lyrics_active_row = -1
        for _, text in lines:
            lbl = Gtk.Label(label=text or "")
            lbl.set_halign(Gtk.Align.START)
            lbl.set_wrap(True)
            lbl.set_selectable(True)
            lbl.set_css_classes(["lyrics-text"])
            row = Gtk.ListBoxRow()
            row.set_child(lbl)
            row.set_selectable(False)
            self._lyrics_listbox.append(row)

    def _lyrics_highlight(self, idx):
        """Hebt Zeile idx hervor und scrollt sie ins Sichtfeld."""
        if idx == self._lyrics_active_row:
            return
        if self._lyrics_active_row >= 0:
            old_row = self._lyrics_listbox.get_row_at_index(self._lyrics_active_row)
            if old_row:
                lbl = old_row.get_child()
                if lbl:
                    lbl.set_css_classes(["lyrics-text"])
        new_row = self._lyrics_listbox.get_row_at_index(idx)
        if new_row:
            lbl = new_row.get_child()
            if lbl:
                lbl.set_css_classes(["lyrics-text", "lyrics-active"])
            def _scroll():
                adj = self._lyrics_scroll.get_vadjustment()
                alloc = new_row.get_allocation()
                scroll_h = self._lyrics_scroll.get_height()
                target = alloc.y - scroll_h // 2 + alloc.height // 2
                adj.set_value(max(0, min(target, adj.get_upper() - adj.get_page_size())))
            GLib.idle_add(_scroll)
        self._lyrics_active_row = idx

    def _lyrics_sync_tick(self):
        """Alle 200ms: aktuelle Zeile anhand Spielposition bestimmen."""
        if not self.is_maximized() or not self._lyrics_synced:
            self._lyrics_timer_id = None
            return False
        pos_ms = self.player.get_pos() // 1_000_000
        best = 0
        for i, (ms, _) in enumerate(self._lyrics_lines):
            if ms is not None and ms <= pos_ms:
                best = i
        self._lyrics_highlight(best)
        return True

    def _load_lyrics(self, force=False):
        """Laedt Songtext via lrclib/lyrics.ovh mit LRC-Sync-Unterstuetzung."""
        if not self.is_maximized():
            return
        if self.player.current < 0 or self.player.current >= len(self.player.playlist):
            self._lyrics_set_lines([(None, "Kein Song ausgewaehlt.")])
            return
        path = self.player.playlist[self.player.current]
        if not force and path == self._lyrics_loaded_path:
            return
        if self._lyrics_timer_id:
            GLib.source_remove(self._lyrics_timer_id)
            self._lyrics_timer_id = None
        self._lyrics_loaded_path = path
        with self._pl_panel._meta_lock:
            meta = dict(self._pl_panel._meta.get(path, {}))
        artist = meta.get("artist", "").strip()
        title  = meta.get("title",  "").strip()
        if not artist or not title:
            import os as _os2
            base = _os2.path.splitext(_os2.path.basename(path))[0]
            parts = base.split(" - ", 1)
            if len(parts) == 2:
                artist, title = parts[0].strip(), parts[1].strip()
        if not artist or not title:
            self._lyrics_set_lines([(None, "Keine Metadaten.")])
            return
        self._lyrics_set_lines([(None, "Lade Songtext ...")])
        def _fetch(a=artist, t=title, p=path):
            import urllib.request, json as _j, urllib.parse
            synced_text = ""
            plain_text  = ""
            try:
                url = "https://lrclib.net/api/search?track_name={}&artist_name={}".format(
                    urllib.parse.quote(t), urllib.parse.quote(a))
                req = urllib.request.Request(url, headers={"User-Agent": "Helga/1.0"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    data = _j.loads(r.read().decode())
                if isinstance(data, list) and data:
                    synced_text = (data[0].get("syncedLyrics") or "").strip()
                    plain_text  = (data[0].get("plainLyrics")  or "").strip()
            except: pass
            if not plain_text:
                try:
                    url2 = "https://api.lyrics.ovh/v1/{}/{}".format(
                        urllib.parse.quote(a), urllib.parse.quote(t))
                    req2 = urllib.request.Request(url2, headers={"User-Agent": "Helga/1.0"})
                    with urllib.request.urlopen(req2, timeout=8) as r2:
                        data2 = _j.loads(r2.read().decode())
                    plain_text = data2.get("lyrics", "").strip()
                except: pass
            use_text = synced_text or plain_text or "Kein Songtext gefunden."
            def _show():
                if self._lyrics_loaded_path != p:
                    return False
                lines, synced = self._lyrics_parse_lrc(use_text)
                self._lyrics_synced = synced
                self._lyrics_set_lines(lines)
                if synced:
                    self._lyrics_timer_id = GLib.timeout_add(200, self._lyrics_sync_tick)
                return False
            GLib.idle_add(_show)
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_album_tile_click(self, album_name, paths):
        """Klick auf Album-Kachel: ersten Track des Albums laden und abspielen."""
        if not paths: return
        first_path = paths[0]
        if first_path in self.player.playlist:
            idx = self.player.playlist.index(first_path)
            self._queued_next = -1
            self.player.load(idx)
            GLib.timeout_add(300, self._start_fade_in)
            self._pl_panel.highlight(idx)

    def _pl_select(self, idx):
        if self.config.get("queue_on_click", False) and self.player.is_playing():
            # Als nächstes merken — wird nach EOS gespielt
            self._queued_next = idx
            # Visuelles Feedback: Zeile kursiv/dim andeuten
            if 0 <= idx < len(self.player.playlist):
                name = Path(self.player.playlist[idx]).stem
                self._artist_lbl.set_label(f"⏭ Als nächstes: {name}")
        else:
            self._queued_next = -1
            self.player.load(idx)
            GLib.timeout_add(300, self._start_fade_in)

    def _pl_remove(self, idx):
        if 0 <= idx < len(self.player.playlist):
            del self.player.playlist[idx]
            if self.player.current == idx:
                self.player.stop(); self.player.current = -1; self._update_play_state(False)
            elif self.player.current > idx:
                self.player.current -= 1
            self._refresh_playlist(); self._save_config()

    def _clear_playlist(self, *_):
        self.player.stop(); self.player.playlist.clear(); self.player.current = -1
        self._update_play_state(False); self._refresh_playlist(); self._save_config()

    def _sort_playlist(self, *_):
        cur_path = self.player.playlist[self.player.current] if 0 <= self.player.current < len(self.player.playlist) else None
        self.player.playlist.sort(key=lambda p: Path(p).stem.lower())
        if cur_path and cur_path in self.player.playlist:
            self.player.current = self.player.playlist.index(cur_path)
        self._refresh_playlist()

    def _filter_playlist(self, entry):
        q = entry.get_text().lower()
        for pl_idx, row in self._pl_panel._rows:
            if not q:
                row.set_visible(True)
                continue
            path = self.player.playlist[pl_idx] if pl_idx < len(self.player.playlist) else ""
            meta = self._pl_panel._get_meta(path)
            haystack = (meta.get("title","") + meta.get("artist","") +
                        meta.get("album","") + Path(path).stem).lower()
            row.set_visible(q in haystack)

    def _toggle_playlist(self, *_):
        self._show_playlist = not self._show_playlist; self._pl_box.set_visible(self._show_playlist)

    def _open_files(self, *_):
        d = Gtk.FileDialog(); f = Gtk.FileFilter(); f.set_name("Audio")
        for e in SUPPORTED: f.add_pattern(f"*{e}")
        ls = Gio.ListStore.new(Gtk.FileFilter); ls.append(f); d.set_filters(ls)
        d.open_multiple(self, None, self._files_done)

    def _files_done(self, d, r):
        try: self._add_files([f.get_path() for f in d.open_multiple_finish(r) if f.get_path()])
        except: pass

    def _open_folder(self, *_):
        d = Gtk.FileDialog(); d.select_folder(self, None, self._folder_done)

    def _folder_done(self, d, r):
        try: folder = d.select_folder_finish(r)
        except: return
        if not folder: return
        folder_path = folder.get_path()
        files = []
        for root, dirs, names in os.walk(folder_path):
            dirs.sort()
            for n in sorted(names):
                if any(n.lower().endswith(e) for e in SUPPORTED): files.append(os.path.join(root, n))
        self._add_files(files)
        # Ordner merken für Auto-Scan
        dirs = self.config.get("music_dirs", [])
        if folder_path not in dirs:
            dirs.append(folder_path)
            self.config["music_dirs"] = dirs
            self._save_config()

    def _schedule_auto_scan(self):
        """Startet/neu-startet den Auto-Scan-Timer."""
        if self._scan_timer_id:
            GLib.source_remove(self._scan_timer_id)
            self._scan_timer_id = None
        if self.config.get("auto_scan", True):
            interval_ms = int(self.config.get("scan_interval_min", 10) * 60 * 1000)
            self._scan_timer_id = GLib.timeout_add(interval_ms, self._auto_scan_tick)
            # Einmalig beim Start nach kurzer Verzögerung scannen
            GLib.timeout_add(3000, self._auto_scan_once)

    def _auto_scan_once(self):
        self._do_auto_scan()
        return False  # nicht wiederholen

    def _auto_scan_tick(self):
        """Wird vom Timer periodisch aufgerufen."""
        self._do_auto_scan()
        return True   # weiter wiederholen

    def _do_auto_scan(self):
        """Scannt alle gespeicherten Musik-Ordner nach neuen Dateien
        und entfernt nicht mehr existierende Dateien aus der Playlist."""
        if not self.config.get("auto_scan", True): return
        dirs = self.config.get("music_dirs", [])
        def _scan():
            new_files = []
            existing = set(self.player.playlist)
            # Neue Dateien finden
            for folder_path in dirs:
                if not os.path.isdir(folder_path): continue
                for root, subdirs, names in os.walk(folder_path):
                    subdirs.sort()
                    for n in sorted(names):
                        if any(n.lower().endswith(e) for e in SUPPORTED):
                            p = os.path.join(root, n)
                            if p not in existing:
                                new_files.append(p)
            # Nicht mehr existierende Dateien finden
            missing = [p for p in self.player.playlist if not os.path.exists(p)]
            if new_files or missing:
                GLib.idle_add(self._scan_apply, new_files, missing)
        threading.Thread(target=_scan, daemon=True).start()

    def _scan_add_new(self, new_files):
        """Fügt neue Dateien zur Playlist hinzu — Hörbücher werden gefiltert."""
        self._execute_add_action(new_files, "add")
        return False

    def _scan_apply(self, new_files, missing):
        """Fügt neue Dateien hinzu und entfernt fehlende aus der Playlist."""
        changed = False
        # Fehlende Dateien entfernen
        if missing:
            missing_set = set(missing)
            cur_path = (self.player.playlist[self.player.current]
                        if 0 <= self.player.current < len(self.player.playlist) else None)
            self.player.playlist = [p for p in self.player.playlist if p not in missing_set]
            if cur_path and cur_path in missing_set:
                self.player.stop()
                self.player.current = -1
                self._update_play_state(False)
            elif cur_path and cur_path in self.player.playlist:
                self.player.current = self.player.playlist.index(cur_path)
            changed = True
            print(f"Auto-Scan: {len(missing)} fehlende Datei(en) aus Playlist entfernt")
        # Neue Dateien hinzufügen (Hörbücher werden gefiltert)
        if new_files:
            self._execute_add_action(new_files, "add")
            changed = True
        if changed and not new_files:
            self._refresh_playlist()
            self._save_config()
        return False

    def _drop(self, tgt, val, x, y):
        if not isinstance(val, Gio.File): return True
        p = val.get_path()
        if not p: return True
        if os.path.isdir(p):
            files = []
            for root, dirs, names in os.walk(p):
                for n in sorted(names):
                    if any(n.lower().endswith(e) for e in SUPPORTED): files.append(os.path.join(root, n))
            self._add_files(files)
        elif any(p.lower().endswith(e) for e in SUPPORTED): self._add_files([p])
        return True

    def _open_sleep(self, *_):
        if self._sleep_timer_id:
            GLib.source_remove(self._sleep_timer_id); self._sleep_timer_id = None
            css = self._sleep_btn.get_css_classes()
            if "sleep-active" in css: css.remove("sleep-active"); self._sleep_btn.set_css_classes(css)
            self._sleep_btn.set_tooltip_text("Sleep-Timer"); return
        SleepDialog(self, self._start_sleep)

    def _start_sleep(self, minutes):
        if self._sleep_timer_id: GLib.source_remove(self._sleep_timer_id)
        self._sleep_end = time.time() + minutes * 60
        self._sleep_timer_id = GLib.timeout_add_seconds(minutes*60, self._sleep_fire)
        css = self._sleep_btn.get_css_classes()
        if "sleep-active" not in css: css.append("sleep-active"); self._sleep_btn.set_css_classes(css)
        self._sleep_btn.set_tooltip_text(f"Sleep in {minutes} Min (klicken zum Abbrechen)")

    def _sleep_fire(self):
        self._sleep_timer_id = None
        css = self._sleep_btn.get_css_classes()
        if "sleep-active" in css: css.remove("sleep-active"); self._sleep_btn.set_css_classes(css)
        self._sleep_btn.set_tooltip_text("Sleep-Timer")
        # Immer 6 Sekunden ausfaden — unabhängig von fade_enabled
        SLEEP_FADE = 6.0
        def _fade_player(get_vol, set_vol, stop_cb):
            """Fadet einen Player in SLEEP_FADE Sekunden auf 0."""
            import time as _t
            start_vol = get_vol()
            if start_vol <= 0:
                GLib.idle_add(stop_cb); return
            start_t = _t.time()
            def step():
                elapsed = _t.time() - start_t
                if elapsed >= SLEEP_FADE:
                    set_vol(0.0)
                    stop_cb()
                    return False
                frac = elapsed / SLEEP_FADE
                set_vol(start_vol * (1.0 - frac))
                return True
            GLib.timeout_add(30, step)
        # Musik
        if self.player.is_playing():
            def stop_musik():
                self.player.stop()
                self.player.set_vol(self._vol_btn.get_volume())
                self._update_play_state(False)
            _fade_player(
                lambda: self.player.pl.get_property("volume"),
                lambda v: self.player.set_vol(v),
                stop_musik)
        # Radio
        if self.radio_player.is_playing():
            def stop_radio():
                self.radio_player.stop()
                self.radio_player.set_vol(self._vol_btn.get_volume())
                GLib.idle_add(self._radio_panel._fill_list)
            _fade_player(
                lambda: self._vol_btn.get_volume(),
                lambda v: self.radio_player.set_vol(v),
                stop_radio)
        # Hörbuch
        if self.ab_player.is_playing():
            def stop_ab():
                self.ab_player.play_pause()
                self.ab_player.set_vol(self._vol_btn.get_volume())
            _fade_player(
                lambda: self.ab_player.pl.get_property("volume"),
                lambda v: self.ab_player.set_vol(v),
                stop_ab)
        return False

    def _key_pressed(self, ctrl, keyval, keycode, state):
        from gi.repository import Gdk as G
        k = keyval
        if k == G.KEY_space:
            tab = self._stack.get_visible_child_name()
            if tab == "musik":
                self._play_pause()
            elif tab == "radio":
                rp = self._radio_panel
                if rp.radio_player.is_playing():
                    rp._stop()
                elif rp._current_url:
                    rp.radio_player.play(rp._current_url, rp.vol_getter())
                    rp._now_station.set_label(rp._current_name)
                    rp._live_dot.set_label("● LIVE")
                    rp._fill_list()
            elif tab == "hoerbuch":
                self._ab_panel._play_pause()
            return True
        if k == G.KEY_Right:
            pos = self.player.get_pos() + 10*Gst.SECOND; dur = self.player.get_dur()
            if dur > 0: self.player.seek(min(1, pos/dur))
            return True
        if k == G.KEY_Left:
            pos = self.player.get_pos() - 10*Gst.SECOND; dur = self.player.get_dur()
            if dur > 0: self.player.seek(max(0, pos/dur))
            return True
        if k == G.KEY_n: self.player.next(); return True
        if k == G.KEY_p: self.player.prev(); return True
        if k in (G.KEY_plus, G.KEY_KP_Add):
            self._vol_btn.set_volume(min(1.5, self._vol_btn.get_volume()+0.05)); return True
        if k in (G.KEY_minus, G.KEY_KP_Subtract):
            self._vol_btn.set_volume(max(0, self._vol_btn.get_volume()-0.05)); return True
        if k == G.KEY_m:
            self._vol_btn._mute_btn.set_active(not self._vol_btn._muted)
            return True
        return False

    def _tick(self):
        pos = self.player.get_pos(); dur = self.player.get_dur()
        if dur > 0:
            self._prog.set_fraction(pos/dur)
            def fmt(ns):
                s = int(ns/Gst.SECOND); return f"{s//60}:{s%60:02d}"
            self._pos_lbl.set_label(fmt(pos)); self._dur_lbl.set_label(fmt(dur))
        if self.player.playlist and self.player.current >= 0:
            playing = self.player.is_playing()
            if playing != self._cover.playing and not self.fader.is_fading():
                self._cover.playing = playing; self._vis.playing = playing
                self._play_btn.set_icon_name("media-playback-pause" if playing else "media-playback-start")
        if self._sleep_timer_id:
            remaining = int(self._sleep_end - time.time())
            if remaining > 0:
                m, s = divmod(remaining, 60)
                self._sleep_btn.set_tooltip_text(f"Sleep in {m}:{s:02d} (klicken zum Abbrechen)")
        # Radio-Lautstärke mit Hauptlautstärke synchron halten
        if self.radio_player.is_playing():
            self.radio_player.set_vol(self._vol_btn.get_volume())
        # Hörbuch-Lautstärke synchron halten
        if self.ab_player.is_playing():
            self.ab_player.set_vol(self._vol_btn.get_volume())
        return True


# ─── App ──────────────────────────────────────────────────────────────────────
class HelgaApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="de.helga.player")

    def do_activate(self):
        Helga(self).present()

    def do_startup(self):
        Gtk.Application.do_startup(self)

if __name__ == "__main__":
    sys.exit(HelgaApp().run(sys.argv))
