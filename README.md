README – Helga Music Player (GTK4)

Überblick
Helga ist ein funktionsreicher, vollständig in GTK4 entwickelter Musikplayer für Linux.
Er integriert sich automatisch in das System‑Theme, nutzt GStreamer für Audio‑Wiedergabe und bietet intelligente Playlists, Cover‑Download, Equalizer, Fade‑Effekte und eine moderne Oberfläche.

Entwickler: evilware666 & Helga
Version: 2.0
MIT License  


Helga-Player Module
- Musik‑Player  
- Radio‑Player  
- Hörbuch‑Player  
- Hörspiel‑Player  
- Smart‑Playlist‑Generator  
- Cover‑Downloader  
- Equalizer  
- Fade‑In/Fade‑Out  
- System‑Theme‑Integration  
- Abhängigkeits‑Installer  
- uvm.

# 📀 **Helga – System‑Theme aware GTK4 Music, Radio & Audiobook Player**  
Ein moderner, funktionsreicher Audio‑Player für Linux  
*(GTK4 • GStreamer • System‑Theme‑Integration • Smart Playlists)*

Helga ist ein vollständig in Python entwickelter, system‑theme‑sensitiver Audio‑Player, der Musik, Radio‑Streams, Hörbücher und Hörspiele in einer einzigen, eleganten GTK4‑Oberfläche vereint.  
Er ist optimiert für Linux‑Desktop‑Umgebungen wie GNOME, Cinnamon, KDE Plasma und XFCE.

---

## ✨ **Hauptfunktionen**

### 🎵 **Musik‑Player**
- Unterstützt alle gängigen Audioformate:  
  **MP3, OGG, FLAC, WAV, AAC, M4A, OPUS, WMA, APE, ALAC, MP4, WEBM, MKA**
- Automatische Metadaten‑Erkennung (Titel, Album, Künstler, Jahr, Genre)
- Cover‑Erkennung aus Dateien oder Online‑Download (MusicBrainz / iTunes)
- Gapless Playback (GStreamer)
- Lautstärke‑Regler, Mute, Equalizer, Spectrum‑Visualizer
- Fade‑In / Fade‑Out beim Starten/Stoppen

---

### 📻 **Radio‑Player**
- Unterstützt HTTP/HTTPS‑Radio‑Streams
- Automatische Metadaten‑Erkennung (falls vom Sender unterstützt)
- Speichern von Lieblings‑Sendern
- Sofort‑Start ohne Verzögerung
- Fehler‑Erkennung bei Offline‑Streams

---

### 🎧 **Hörbuch‑Player**
- Merkt sich **Fortschritt pro Datei**
- Kapitel‑Erkennung (falls im Container vorhanden)
- Lesezeichen‑System
- Automatische Fortsetzung beim nächsten Start
- Langsame/Normale/Schnelle Wiedergabegeschwindigkeit

---

### 🎙️ **Hörspiel‑Player**
- Spezieller Modus für Hörspiele:
  - Automatische Gruppierung nach Serien
  - Sortierung nach Episoden‑Nummer
  - Cover‑Erkennung pro Episode
  - „Nächste Episode automatisch abspielen“

---

### 🧠 **Smart‑Playlist‑Generator**
Helga analysiert deine Bibliothek und erstellt intelligente Playlists:

- **Nie gespielt**
- **Meist gespielt**
- **Am wenigsten gespielt**
- **Neueste Dateien**
- **Älteste Dateien**
- **Kürzlich hinzugefügt**
- **Nach Bewertung**
- **Nach Künstler**
- **Nach Genre**
- **Nach Jahr / Jahrzehnt**
- **Favoriten‑Algorithmus**
- **Zufällige Auswahl**

Alle Playlists werden dynamisch erzeugt und aktualisiert.

---

### 🎨 **System‑Theme Integration**
Helga passt sich automatisch an:

- Hell/Dunkel‑Modus
- System‑Farben
- GTK4‑Accent‑Color
- Transparenz & Schatten

Alle UI‑Elemente (Buttons, Listen, Cover‑Frames, Equalizer‑Regler) nutzen das aktive Theme.

---

### 🎚️ **Equalizer & Audio‑Pipeline**
- 10‑Band‑Equalizer (GStreamer `equalizer-10bands`)
- Spectrum‑Visualizer (48 Bänder)
- Pulsesink/Autoaudiosink/Alsa‑Fallback
- Lautstärke‑Element mit Mute‑Support
- Saubere, stabile Audio‑Pipeline:
  ```
  volume → equalizer → audioconvert → spectrum → sink
  ```

---

### 🌅 **Fade‑In / Fade‑Out**
- Sanftes Einblenden beim Start
- Sanftes Ausblenden beim Stoppen
- Verschiedene Fade‑Kurven:
  - Linear
  - Smoothstep
  - Exponential

---

### 🖼️ **Cover‑Downloader**
Automatische Cover‑Suche über:

- MusicBrainz
- CoverArtArchive
- iTunes API

Cover werden gecached unter:

```
~/.cache/helga/covers/
```

---

### 🧩 **Metadaten‑Fixer**
Helga repariert automatisch falsch kodierte Umlaute (Mojibake):

- Latin‑1 → UTF‑8
- CP1252 → UTF‑8
- UTF‑8 → Latin‑1 fallback

---

### 🛠️ **Abhängigkeits‑Installer (GUI)**
Beim ersten Start prüft Helga alle benötigten Pakete:

- python3‑gi  
- python3‑gst‑1.0  
- gstreamer‑plugins‑base  
- gstreamer‑plugins‑good  
- gstreamer‑plugins‑ugly  
- gstreamer‑libav  

Falls etwas fehlt:

- GTK4‑Fenster zeigt fehlende Pakete
- Passwort‑Dialog
- Automatische Installation mit Fortschrittsanzeige
- Neustart‑Button

---

## 📂 **Konfigurations‑Ordner**
Helga speichert Einstellungen unter:

```
~/.config/helga/config.json
```

Dort werden gespeichert:

- Lautstärke
- Equalizer‑Preset
- Letzter Track
- Play‑Counts
- Bewertungen
- Hörbuch‑Fortschritt
- Radio‑Sender
- Theme‑Einstellungen

---

## 🧠 **Play‑History & Ratings**
Helga merkt sich:

- Wie oft ein Track gespielt wurde
- Deine Bewertungen (1–5 Sterne)
- Letzte Position bei Hörbüchern
- Zuletzt gespielte Dateien

Diese Daten werden für Smart‑Playlists genutzt.

---

## 🚀 **Starten**
```
python3 helga.py
```

---

## 🧩 **Abhängigkeiten (Debian/Ubuntu)**
```
sudo apt install python3-gi python3-gst-1.0 \
    gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-ugly gstreamer1.0-libav \
    gir1.2-gtk-4.0 gir1.2-gstreamer-1.0
```

---

