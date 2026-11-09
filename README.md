# CosmicFB Frequency Plugin (`cosmic-frequent-folders`)

Ein leichtgewichtiges Sidecar-Tool für **Pop!_OS / COSMIC Desktop**, das die am häufigsten und kürzlich genutzten Ordner dynamisch in die Seitenleiste von **COSMIC Files** (`cosmic-files`) einträgt – analog zum *Schnellzugriff (Quick Access)* unter Windows.

---

## Funktionsweise

Da `cosmic-files` keine interne Plugin-Schnittstelle besitzt, aber Änderungen an seiner Konfigurationsdatei (`~/.config/cosmic/com.system76.CosmicFiles/v1/favorites`) in Echtzeit per Inotify überwacht, nutzt dieses Projekt einen **Sidecar-Ansatz**:

1. **Datenquellen (Frecency-Score):**
   - **FreeDesktop Recent Files (`~/.local/share/recently-used.xbel`):** Analysiert geöffnete Dateien, deren Elternverzeichnisse, Besuchszähler (`count`) und Zeitstempel (`visited`). Zugriffe direkt über `cosmic-files` erhalten eine höhere Gewichtung (`1.5x`).
   - **Terminal-Navigation (`zoxide`):** Falls `zoxide` installiert ist, fließen auch häufig im Terminal besuchte Ordner logarithmisch gewichtet in das Ranking ein.
   - **Zeitlicher Verfall (Half-Life Decay):** Ältere Zugriffe verlieren über eine konfigurierbare Halbwertszeit (Standard: `7 Tage`) automatisch an Gewicht:
     $$\text{Score} = \sum \text{Count} \cdot w_{\text{App}} \cdot 0.5^{\Delta t / T_{1/2}}$$
2. **Schutz & Synchronisation gepinnter Favoriten:**
   - Standard-Ordner (`Home`, `Documents`, `Downloads`, `Pictures` etc.) sowie eigene dauerhaft angeheftete Ordner bleiben immer oben in der Liste erhalten.
   - **Zwei-Wege-GUI-Sync:** Wenn du in `cosmic-files` manuell einen neuen Ordner in die Seitenleiste ziehst oder einen bestehenden entfernst, erkennt das Skript die Differenz zur letzten dynamischen Liste und übernimmt deine Änderung automatisch in die geschützten Favoriten.
3. **Atomares Schreiben:**
   - Die RON-Datei wird nur aktualisiert, wenn sich die Liste tatsächlich geändert hat, und wird atomar (`tempfile` + `os.replace`) geschrieben, sodass `cosmic-files` niemals eine unfertige Datei liest.

---

## Projektstruktur

- `cosmic_frequent_folders.py` — Hauptskript (reines Python 3 Standard-Library, keine externen Abhängigkeiten).
- `systemd/cosmic-frequent-folders.service` — Systemd-User-Service für die Aktualisierung.
- `systemd/cosmic-frequent-folders.timer` — Systemd-User-Timer (läuft 1 Minute nach Login und danach alle 15 Minuten).
- `install.sh` — Richtet den Symlink unter `~/.local/bin/cosmic-frequent-folders` sowie den Systemd-Timer ein.

---

## Installation

```bash
chmod +x install.sh
./install.sh
```

Das Installationsskript:
1. Verlinkt `cosmic_frequent_folders.py` nach `~/.local/bin/cosmic-frequent-folders`.
2. Kopiert die Systemd-Units nach `~/.config/systemd/user/`.
3. Aktiviert und startet `cosmic-frequent-folders.timer`.
4. Führt einen initialen Sync durch.

---

## Verwendung (CLI)

| Befehl | Beschreibung |
| :--- | :--- |
| `cosmic-frequent-folders` | Führt sofort ein Update der Seitenleiste durch |
| `cosmic-frequent-folders --dry-run` | Zeigt die berechneten Scores und das generierte RON-Format ohne zu speichern |
| `cosmic-frequent-folders --pin /pfad/zum/ordner` | Heftet einen Ordner dauerhaft an |
| `cosmic-frequent-folders --unpin /pfad/zum/ordner` | Entfernt einen Ordner aus den dauerhaft angehefteten Favoriten |
| `cosmic-frequent-folders --test` | Führt den integrierten Selbsttest aus |

---

## Konfiguration

Beim ersten Start wird automatisch `~/.config/cosmic-frequent-folders/config.json` angelegt:

```json
{
  "pinned": [
    "Home",
    "Documents",
    "Downloads",
    "Pictures",
    "/run/media/christian/NextcloudData/Nextcloud/Dokumente/Programmieren"
  ],
  "last_dynamic": [],
  "max_dynamic": 4,
  "half_life_days": 7.0,
  "use_zoxide": true,
  "sync_gui_favorites": true,
  "exclude_prefixes": [
    "/tmp",
    "/var",
    "/proc",
    "/sys",
    "/dev",
    "/run/user"
  ],
  "exclude_names": [
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "target",
    "build",
    "dist",
    ".cache",
    ".local",
    ".config",
    ".gemini"
  ]
}
```

### Wichtige Parameter
- **`max_dynamic`**: Anzahl der dynamischen Ordner, die unterhalb der festen Favoriten angezeigt werden (Standard: `4`).
- **`half_life_days`**: Halbwertszeit in Tagen für den Aktualitäts-Faktor (Standard: `7.0`).
- **`use_zoxide`**: Bezieht `zoxide query -l -s` mit ein (`true` / `false`).
- **`sync_gui_favorites`**: Übernimmt manuelle Favoriten-Änderungen aus der COSMIC Files GUI (`true` / `false`).
