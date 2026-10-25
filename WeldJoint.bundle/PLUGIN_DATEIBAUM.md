# Weld Joint – Dateibaum

Stand: 25.10.2026 · **Weld Joint 1.0.0** von Kabelfrikkler (https://github.com/workheart).
Basiert auf „Box Joint“ v1.0.3 von Mark Suska (MIT-Lizenz, https://github.com/EvilHacker/BoxJoint).
Installiert als Bundle unter `%APPDATA%\Autodesk\ApplicationPlugins\` – der Ordner heißt noch
`BoxJoint.bundle` und soll in `WeldJoint.bundle` umbenannt werden (bei geschlossenem Fusion).

Funktionen und Aufrufketten stehen in [PLUGIN_FUNKTIONEN.md](PLUGIN_FUNKTIONEN.md), die
Fusion-API-Grundlagen in [FUSION_API_SOURCE_OF_TRUTH.md](FUSION_API_SOURCE_OF_TRUTH.md).

## Baum

```
WeldJoint.bundle\  (noch BoxJoint.bundle)
├── PackageContents.xml ............ Paketbeschreibung: Name, Autor, Version, UpgradeCode; verweist auf
│                                    Contents\WeldJoint.manifest
├── FUSION_API_SOURCE_OF_TRUTH.md .. Fusion-API-Referenz für die Entwicklung
├── PLUGIN_DATEIBAUM.md ............ diese Datei
├── PLUGIN_FUNKTIONEN.md ........... Funktionen, Klassen, Aufrufketten, Änderungsliste
├── request 1 … 5 *.png ............ Screenshots der Schweiß-Anforderungen (Radius, Seitenverhältnis,
│                                    Tab kürzen, Slot-Spiel, Loch-Spiel)
├── _original_v1.0.3\ .............. Sicherung des Box-Joint-Originals – wird nicht geladen
│   ├── *.py, BoxJoint.manifest, PackageContents.xml
│   └── docs\ ...................... alte App-Store-Hilfe (Help.html + Screenshots/CSS)
│
└── Contents\  (= Inhalt eines GitHub-Repos)
    ├── WeldJoint.manifest ......... JSON-Manifest: type=addin, runOnStartup=true, Autor, Version 1.0.0
    ├── WeldJoint.py ............... Einstieg: run() lädt Module neu + erzeugt WeldJointAddIn,
    │                                stop() ruft destroy()                                         (42 Zeilen)
    │
    ├── fusion_weld_joint.py ....... ★ Fachlogik: Parameter, Dialog, Tooltips, Modi (Fingers /
    │                                Tabs: Spacing / Tabs: Points), Geometrie, Clearances,
    │                                letzte Einstellungen                                          (824 Zeilen)
    ├── fusion_cf_addin.py ......... Generische Basisklasse „Custom Feature Add-in“:
    │                                Buttons, Events, Create/Edit/Compute, Timeline-Handling      (377 Zeilen)
    ├── fusion_base_combines.py .... Bringt temporäre Bool-Ops als BaseFeature + 2 Combine
    │                                Features pro Zielkörper ins Modell                            (118 Zeilen)
    ├── fusion_brep_util.py ........ Hilfen für temporäre B-Rep-Körper (Prisma, Box, Fläche,
    │                                Verbreitern …) und Datenklasse BooleanOperation               (280 Zeilen)
    ├── fusion_util.py ............. Allgemeine Hilfen: Logging, Event-Handler-Fabrik,
    │                                Parameter-/EntityRef-Klassen, Einheiten                       (211 Zeilen)
    │
    ├── last_settings.json ......... (entsteht beim ersten OK) zuletzt benutzte Einstellungen, dokumentübergreifend
    │
    ├── Resources\
    │   ├── ToolClips\ ............. Tooltip-Bilder: <Input-ID>.png und command.png (Button); Liste in LIESMICH.txt
    │   └── WeldJoint\ ............. Icons für Button + Zeitleiste (vom Code als resourceFolder genutzt;
    │       │                        noch die Box-Joint-Icons)
    │       ├── 16x16.png, 16x16@2x.png
    │       ├── 32x32.png, 32x32@2x.png
    │       ├── 64x64.png, 64x64@2x.png
    │       └── 128x128.png, 128x128@2x.png
    │
    ├── icons\
    │   └── Weld Joint.ico ......... Windows-Icon (Installer), vom Code nicht genutzt; noch das Box-Joint-Icon
    │
    ├── docs\
    │   └── Help.html .............. Hilfeseite (in PackageContents.xml als HelpFile verlinkt), eigenständig
    │
    ├── __pycache__\ ............... Von Fusion erzeugter Bytecode (cpython-314 = Python 3.14), kann gelöscht werden
    │
    ├── README.md .................. README (Englisch, für GitHub): Funktionen, Installation, Bedienung
    ├── LICENSE .................... MIT-Lizenz, © 2023 Mark Suska + © 2026 Kabelfrikkler
    ├── privacy_policy.txt ......... „sammelt keine Daten“
    └── .gitignore ................. ignoriert .env/.vscode (Fusion-Debugging), __pycache__, last_settings.json
```

## Abhängigkeiten zwischen den Python-Modulen

```
WeldJoint.py
 ├─► alle fusion_*-Module (importlib.reload in run())
 ├─► fusion_weld_joint  (WeldJointAddIn)
 └─► fusion_util        (log, handleException)

fusion_weld_joint
 ├─► fusion_cf_addin        (FusionCustomFeatureAddIn  ← Basisklasse)
 ├─► fusion_base_combines   (BaseCombines)
 ├─► fusion_brep_util       (* : tempBrepMgr, createSimpleBox, createPrism, createWidenedBody, …, BooleanOperation)
 └─► fusion_util            (* : Parameter, EntityRef, UserInputError, log, handleException, cmOrIn)

fusion_cf_addin
 └─► fusion_util            (newEventHandler, currentTimelineObject, Parameter)

fusion_base_combines
 ├─► fusion_util            (newObjectCollection)
 └─► fusion_brep_util       (tempBrepMgr, aContainingBody, BooleanOperation)

fusion_brep_util / fusion_util
 └─► nur adsk.core, adsk.fusion, Standardbibliothek
```

Alle Imports sind relativ (`from .modul import …`), weil Fusion den `Contents`-Ordner als Paket lädt.

## Welche Datei ändere ich wofür?

| Vorhaben | Datei |
|---|---|
| Neuer Zahlen-Parameter im Dialog | `fusion_weld_joint.py`: Feld in `WeldJointParameters`, Eintrag in `_parameterDescriptions` und `_tooltips`, Input in `createInputs` (gleiche ID). Speichern/Laden/Dialog-Abgleich/Merken laufen dann automatisch |
| Neue Auswahl/Schalter (kein Zahlenwert) | wie `mode` / `tabPoints`: Feld, `createInputs`, `paramsToInputs`, `inputsToParams`, `customFeatureToParams`, `getCustomNamedValues` (ggf. `loadSettings`/`saveSettings`) |
| Neuer Modus | `_modeNames`, `_modeInputIds`, Zweig in `computeWeldJoint` (muss `tabOffsets` liefern) |
| Form/Anzahl/Breite der Finger/Tabs, Clearances | `fusion_weld_joint.py`: `computeWeldJoint` |
| Welche Eingaben in welchem Modus sichtbar sind | `fusion_weld_joint.py`: `_modeInputIds` |
| Welche Flächenpaare als Stoß erkannt werden | `fusion_weld_joint.py`: `getAllButtingFaces`, `getButtingFaces` |
| Eingabeprüfung / Fehlermeldung im Dialog | `fusion_weld_joint.py`: `areInputsValid`, `canSelect` |
| Name, Tooltip des Buttons, Button-Position, Command-ID | `fusion_weld_joint.py`: `WeldJointAddIn.__init__` |
| Icons | `Contents\Resources\WeldJoint\` |
| Tooltip-Texte | `fusion_weld_joint.py`: `_tooltips` |
| Tooltip-Bilder | PNG nach `Contents\Resources\ToolClips\<Input-ID>.png` legen (≤ 300 px breit) |
| Gemerkte Einstellungen zurücksetzen | `Contents\last_settings.json` löschen |
| Wie Ergebnisse in die Zeitleiste kommen | `fusion_base_combines.py` |
| Create/Edit/Recompute-Ablauf | `fusion_cf_addin.py` (generisch, selten nötig) |
| Neue Geometrie-Bausteine (z. B. Fase-Prisma) | `fusion_brep_util.py` |
| Plugin-Name/Version/Autor im Add-in-Dialog | `Contents\WeldJoint.manifest`, `PackageContents.xml` |
| Zurück zum Box-Joint-Original | Dateien aus `_original_v1.0.3\` nach `Contents\` kopieren (Weld-Joint-Dateien vorher entfernen) |

## Hinweise zum Bestand

- **IDs:** `baseCommandId='Kabelfrikkler_WeldJoint'` ist zugleich die ID der CustomFeatureDefinition
  (`Kabelfrikkler_WeldJointCreate`). Fusion-Dateien mit Weld-Joint-Features hängen an dieser ID –
  **nicht mehr ändern**. Features aus der Box-Joint-Zeit (`Suska_BoxJointCreate`) werden von diesem
  Add-in nicht mehr berechnet.
- `UpgradeCode` und `AppNameSpace` in `PackageContents.xml` sind neu, damit ein Update des
  App-Store-Originals „Box Joint“ dieses Add-in nicht überschreibt.
- Manifest nutzt `"autodeskProduct": "Fusion360"` (aktuell `"Fusion"`, alter Wert funktioniert).
- `runOnStartup` ist `true`. Für Debugging mit VS Code empfiehlt Autodesk `false`.
