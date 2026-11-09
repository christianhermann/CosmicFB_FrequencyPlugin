# CosmicFB Frequency Plugin (`cosmic-frequent-folders`)

> [!NOTE]
> **Disclaimer:** This project is **100% vibecoded** — built with AI assistance for personal workflow optimization on Pop!_OS / COSMIC Desktop. Use at your own risk!
>
> **Hinweis:** Dieses Projekt ist **vibecoded** — KI-gestützt entwickelt für den eigenen Workflow unter Pop!_OS / COSMIC Desktop. Nutzung auf eigene Gefahr!

[🇬🇧 English](#english) | [🇩🇪 Deutsch](#deutsch)

---

<a id="english"></a>

## 🇬🇧 English

A lightweight sidecar tool for **Pop!_OS / COSMIC Desktop** that dynamically populates the **COSMIC Files** (`cosmic-files`) sidebar with your most frequently and recently used folders — similar to *Quick Access* in Windows Explorer.

### How It Works

Since `cosmic-files` does not have a native plugin API, it watches its configuration file (`~/.config/cosmic/com.system76.CosmicFiles/v1/favorites`) in real time via inotify. This tool uses a **sidecar approach**:

1. **Data Sources (Frecency Score):**
   - **FreeDesktop Recent Files (`~/.local/share/recently-used.xbel`):** Evaluates opened files, their parent directories, visit counts (`count`), and timestamps (`visited`). Accesses directly through `cosmic-files` receive a `1.5x` weight bonus.
   - **Terminal Navigation (`zoxide`):** If `zoxide` is installed, frequently visited terminal directories are logarithmically blended into the ranking.
   - **Time Decay (Half-Life):** Older visits automatically lose weight based on a configurable half-life (default: `7 days`):
     $$\text{Score} = \sum \text{Count} \cdot w_{\text{App}} \cdot 0.5^{\Delta t / T_{1/2}}$$
2. **Pinned Favorites Protection & Two-Way GUI Sync:**
   - Standard folders (`Home`, `Documents`, `Downloads`, `Pictures`, etc.) and custom pinned paths always stay at the top.
   - **Two-Way GUI Sync:** If you manually drag a folder into the `cosmic-files` sidebar or remove an existing pinned folder in the GUI, the script detects the difference against the last dynamic set and automatically updates your pinned list.
3. **Atomic Writes:**
   - The RON file is only touched when the list actually changes and is updated atomically (`tempfile` + `os.replace`) so `cosmic-files` never reads a partial file.

### Project Structure

- `cosmic_frequent_folders.py` — Main script (pure Python 3 standard library, zero external dependencies).
- `systemd/cosmic-frequent-folders.service` — Systemd user service.
- `systemd/cosmic-frequent-folders.timer` — Systemd user timer (runs 1 minute after login and every 15 minutes thereafter).
- `install.sh` — Sets up the symlink in `~/.local/bin/cosmic-frequent-folders` and enables the systemd timer.

### Installation

```bash
chmod +x install.sh
./install.sh
```

### CLI Usage

| Command | Description |
| :--- | :--- |
| `cosmic-frequent-folders` | Immediately syncs the sidebar favorites |
| `cosmic-frequent-folders --dry-run` | Prints calculated scores and generated RON without saving |
| `cosmic-frequent-folders --pin /path/to/dir` | Permanently pins a folder |
| `cosmic-frequent-folders --unpin /path/to/dir` | Unpins a folder from permanent favorites |
| `cosmic-frequent-folders --test` | Runs the built-in self-test |

### Configuration

On first run, `~/.config/cosmic-frequent-folders/config.json` is generated automatically:

- **`max_dynamic`**: Number of dynamic folders shown below pinned items (default: `4`).
- **`half_life_days`**: Half-life in days for time decay (default: `7.0`).
- **`use_zoxide`**: Include `zoxide query -l -s` scores (`true` / `false`).
- **`sync_gui_favorites`**: Sync manual pin/unpin changes made inside the COSMIC Files GUI (`true` / `false`).

---

<a id="deutsch"></a>

## 🇩🇪 Deutsch

Ein leichtgewichtiges Sidecar-Tool für **Pop!_OS / COSMIC Desktop**, das die am häufigsten und kürzlich genutzten Ordner dynamisch in die Seitenleiste von **COSMIC Files** (`cosmic-files`) einträgt – analog zum *Schnellzugriff (Quick Access)* unter Windows.

### Funktionsweise

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

### Projektstruktur

- `cosmic_frequent_folders.py` — Hauptskript (reines Python 3 Standard-Library, keine externen Abhängigkeiten).
- `systemd/cosmic-frequent-folders.service` — Systemd-User-Service für die Aktualisierung.
- `systemd/cosmic-frequent-folders.timer` — Systemd-User-Timer (läuft 1 Minute nach Login und danach alle 15 Minuten).
- `install.sh` — Richtet den Symlink unter `~/.local/bin/cosmic-frequent-folders` sowie den Systemd-Timer ein.

### Installation

```bash
chmod +x install.sh
./install.sh
```

Das Installationsskript:
1. Verlinkt `cosmic_frequent_folders.py` nach `~/.local/bin/cosmic-frequent-folders`.
2. Kopiert die Systemd-Units nach `~/.config/systemd/user/`.
3. Aktiviert und startet `cosmic-frequent-folders.timer`.
4. Führt einen initialen Sync durch.

### Verwendung (CLI)

| Befehl | Beschreibung |
| :--- | :--- |
| `cosmic-frequent-folders` | Führt sofort ein Update der Seitenleiste durch |
| `cosmic-frequent-folders --dry-run` | Zeigt die berechneten Scores und das generierte RON-Format ohne zu speichern |
| `cosmic-frequent-folders --pin /pfad/zum/ordner` | Heftet einen Ordner dauerhaft an |
| `cosmic-frequent-folders --unpin /pfad/zum/ordner` | Entfernt einen Ordner aus den dauerhaft angehefteten Favoriten |
| `cosmic-frequent-folders --test` | Führt den integrierten Selbsttest aus |

### Konfiguration

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

#### Wichtige Parameter
- **`max_dynamic`**: Anzahl der dynamischen Ordner, die unterhalb der festen Favoriten angezeigt werden (Standard: `4`).
- **`half_life_days`**: Halbwertszeit in Tagen für den Aktualitäts-Faktor (Standard: `7.0`).
- **`use_zoxide`**: Bezieht `zoxide query -l -s` mit ein (`true` / `false`).
- **`sync_gui_favorites`**: Übernimmt manuelle Favoriten-Änderungen aus der COSMIC Files GUI (`true` / `false`).
