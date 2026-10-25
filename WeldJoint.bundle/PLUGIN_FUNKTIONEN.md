# Weld Joint – Funktionen, Klassen und Aufrufketten

Stand: 25.10.2026 · **Weld Joint 1.0.0** von Kabelfrikkler (https://github.com/workheart), basiert auf
„Box Joint“ v1.0.3 von Mark Suska (MIT; Sicherung des Originals in `_original_v1.0.3/`).
Zeilenangaben beziehen sich auf den aktuellen Code.
Dateiüberblick: [PLUGIN_DATEIBAUM.md](PLUGIN_DATEIBAUM.md) · API-Grundlagen:
[FUSION_API_SOURCE_OF_TRUTH.md](FUSION_API_SOURCE_OF_TRUTH.md)

---

## 0. Änderungen gegenüber dem Original (v1.0.3)

| Was | Wo |
|---|---|
| **Umbenannt in Weld Joint**, Autor Kabelfrikkler, Version 1.0.0: Hauptdatei `WeldJoint.py`/`.manifest`, Modul `fusion_weld_joint.py`, Klassen `WeldJoint…`, Icon-Ordner `Resources/WeldJoint`, neue IDs `Kabelfrikkler_WeldJoint…` (Features aus den Box-Joint-Testdateien werden damit nicht mehr neu berechnet), neue `UpgradeCode`/`AppNameSpace` (kein Überschreiben durch das App-Store-Original), README und Hilfe neu, LICENSE um eigenen Copyright-Vermerk ergänzt | alle |
| **Tool Diameter ausgebaut** (Eingabe, Parameter, Hohlkehlen/Dog-Bones – für Wasserstrahl/Laser unnötig) | `fusion_weld_joint.py` |
| **Mode** (Dropdown): *Fingers* (Original), *Tabs: Spacing* (feste `Tab Width`, Verteilung über `Tab Spacing`), *Tabs: Points* (ein Tab mittig auf jedem gewählten Skizzen-/Konstruktionspunkt). Es werden nur die Eingaben des gewählten Modus angezeigt | `computeWeldJoint`, `createInputs`, `updateInputVisibility`, `_modeInputIds` |
| **Tab Setback**: Tabs (Finger des anstoßenden Blechs B) enden um diesen Wert unter der Außenfläche von A | `computeWeldJoint` |
| **Slot Clearance**: Schlitz je Seite länger als der Tab (entlang der Kante) | `computeWeldJoint`, `createWidenedBody` |
| **Hole Clearance**: Schlitz je Seite breiter (quer zur Kante), nur wenn der Schlitz ein geschlossenes Loch in der Fläche ist | `computeWeldJoint`, `isClosedHole` |
| **Margin → Corner Margin** (nur das Label, ID bleibt `margin`) | `createInputs`, `_parameterDescriptions` |
| **Tooltips** für alle Eingaben (Kurztext + längere Beschreibung), optional mit Bild aus `Contents/Resources/ToolClips/<ID>.png`; Button-Bild `command.png` | `_tooltips`, `setTooltip`, `FusionCustomFeatureAddIn.__init__` |
| **Letzte Einstellungen merken**: Modus und alle Werte (ohne Flächen/Punkte) werden nach OK in `Contents/last_settings.json` gespeichert und beim nächsten Anlegen vorbelegt – dokumentübergreifend | `loadSettings`, `saveSettings`, `onDestroy`, `commandCompleted` |
| Fehler behoben: `margin` wurde bei mehreren Stößen überschrieben (jetzt `endMargin`) | `computeWeldJoint` |
| Fehler behoben: `computeDisabled` bleibt nach Exception nicht mehr hängen (`try/finally`) | `fusion_cf_addin.py` |
| Fehler behoben: `BooleanOperation.intersection` nutzte falschen Enum-Namen | `fusion_brep_util.py` |
| Live-Entwicklung: `run()` lädt alle Module neu; `stop()` räumt explizit über `destroy()` auf (statt `__del__`) und hängt den Compute-Handler ab. **Getestet: Neuladen ohne Fusion-Neustart funktioniert** | `WeldJoint.py`, `fusion_cf_addin.py` |
| Ältere Features bleiben editierbar: fehlende Parameter landen als Named Values; altes `tabMode = 'true'` wird als *Tabs: Spacing* gelesen | `_updateCustomFeature`, `featureParameter`, `customFeatureToParams` |
| Schräge (stumpfe) Stöße: der Schrägstreifen läuft pro Finger über die ganze Stoßlänge statt bis zum Nachbarfinger – gleiches Ergebnis, unabhängig von den Abständen (nötig für Punkte-Modus) | `computeWeldJoint` |

---

## 1. Architektur in einem Satz

`WeldJoint.py` lädt beim Start alle Module neu und erzeugt ein `WeldJointAddIn`. Dessen generische
Basisklasse `FusionCustomFeatureAddIn` kümmert sich um Buttons, Dialog-Events, Zeitleiste und
Neuberechnung und ruft dafür **Hook-Methoden** auf, die `WeldJointAddIn` überschreibt. Die Geometrie
berechnet `computeWeldJoint()` komplett mit **temporären B-Rep-Körpern**. `BaseCombines` bringt das
Ergebnis pro Zielkörper als *BaseFeature + Join-Combine + Intersect-Combine* ins Modell, und das
Ganze wird in der Zeitleiste zu **einem** Custom Feature „Weld Joint“ gruppiert.

```
            ┌───────────────────────── fusion_cf_addin.py ─────────────────────────┐
 Fusion ──► │ FusionCustomFeatureAddIn  (Events, Timeline, Create/Edit/Compute)    │
 Events     │        │ ruft Hooks auf                                              │
            └────────┼─────────────────────────────────────────────────────────────┘
                     ▼
            ┌───────────────────────── fusion_weld_joint.py ────────────────────────┐
            │ WeldJointAddIn (Dialog, Tooltips, Parameter ↔ Inputs ↔ Feature,       │
            │                letzte Einstellungen)                                 │
            │        │ createOrUpdateChildFeatures()                               │
            │        ▼                                                             │
            │ computeWeldJoint(params) ──► getAllButtingFaces() ──► getButtingFaces()│
            │        │                └─► isClosedHole(), pointGeometry()         │
            │        │ erzeugt BooleanOperation-Liste (temporäre Körper)          │
            └────────┼─────────────────────────────────────────────────────────────┘
                     ▼
            ┌──────────── fusion_base_combines.py ────────────┐
            │ BaseCombines.createOrUpdate()                   │──► BaseFeature, CombineFeature (Modell)
            └─────────────────────────────────────────────────┘
       Hilfen: fusion_brep_util.py (temporäre Geometrie) · fusion_util.py (Log, Parameter, EntityRef)
```

---

## 2. Abläufe (Aufrufketten)

### 2.1 Laden und Starten

```
Fusion lädt Contents/WeldJoint.py (Import)
├─ from . import fusion_util, fusion_brep_util, fusion_base_combines, fusion_cf_addin, fusion_weld_joint
│     (fusion_brep_util legt die globale Variable tempBrepMgr an)
└─ log('Loading …') / log('Finished loading …')

Fusion ruft run(context)                                         WeldJoint.py:16
├─ importlib.reload() für alle Module in Abhängigkeitsreihenfolge (Code-Änderungen greifen ohne Fusion-Neustart)
└─ fusion_weld_joint.WeldJointAddIn()                              fusion_weld_joint.py:133
   └─ FusionCustomFeatureAddIn.__init__(baseCommandId='Kabelfrikkler_WeldJoint', …)   fusion_cf_addin.py:16
      ├─ 11× newEventHandler(self.onXxx, <HandlerKlasse>)        → self._xxxHandler
      ├─ addButtonDefinition('Kabelfrikkler_WeldJointCreate', …, 'Resources/WeldJoint')  .commandCreated → onCreate
      │    .toolClipFilename = ToolClips/command.png (falls vorhanden)
      ├─ addButtonDefinition('Kabelfrikkler_WeldJointEdit', …)                          .commandCreated → onEdit
      ├─ CustomFeatureDefinition.create('Kabelfrikkler_WeldJointCreate', 'Weld Joint', 'Resources/WeldJoint')
      │    .editCommandId = 'Kabelfrikkler_WeldJointEdit'  ·  .customFeatureCompute → onCompute
      └─ Buttons: SolidScriptsAddinsPanel  +  SolidModifyPanel (nach FusionCombineCommand, promoted)
```

### 2.2 Neues Feature anlegen (Button „Weld Joint“)

```
commandCreated → onCreate(args)                                  fusion_cf_addin.py:110
├─ defaultParams() = loadSettings(WeldJointParameters())          letzte Einstellungen vorbelegen
├─ createInputs(command, params)                                 fusion_weld_joint.py:155
│   ├─ setTooltip(...) für jede Eingabe aus _tooltips            Text + optional Bild
│   └─ updateInputVisibility(inputs)                             nur Eingaben des gewählten Modus
└─ verbindet: preSelect→onPreSelect, inputChanged→onInputChanged, validateInputs→onValidateInputs,
              executePreview→onPreview, execute→onExecuteCreate, destroy→onDestroy

Maus über Fläche → preSelect → onPreSelect → canSelect(entity, input)        Faces: nur ebene Flächen auf Volumenkörpern
                                                                              Tab Points: Skizzen-/Konstruktionspunkte (Filter)
Mode wechseln    → inputChanged → onInputChanged → inputChanged(input, inputs) → updateInputVisibility
Jede Eingabe     → validateInputs → onValidateInputs → areInputsValid(inputs) sichtbare Ausdrücke gültig;
                                                                                Fingers: Anzahl ungerade
                                                                                Points: mind. 1 Punkt
Jede Eingabe     → executePreview → onPreview(args)                           fusion_cf_addin.py:201
                   ├─ inputsToParams(commandInputs) → WeldJointParameters
                   ├─ with computeDisabled():  _createCustomFeature(params)
                   ├─ _lastParams = params
                   └─ args.isValidResult = True   (Vorschau wird bei OK übernommen)
OK               → execute → onExecuteCreate(args) → _createCustomFeature(params)
                   (ob execute nach gültiger Vorschau noch kommt, ist nicht dokumentiert)
Ende             → destroy → onDestroy(args)                                  fusion_cf_addin.py:245
                   └─ nur bei terminationReason == Completed (OK):
                      commandCompleted(_lastParams) → saveSettings(params)    → Contents/last_settings.json

_createCustomFeature(params)                                      fusion_cf_addin.py:253
├─ customFeatures.createInput(self._customFeatureDef)
├─ für getCustomParameters(params):  input.addCustomParameter(id, Beschreibung, …)   11 Parameter
├─ für getDependencies(params):      input.addDependency('body0', body) …, ('point0', Punkt) …
├─ customFeatures.add(input)
├─ für getCustomNamedValues(params): addOrSetValue('faces' | 'mode' | 'tabPoints', …)
├─ createOrUpdateChildFeatures(params, [], allowFeatureCreationAndDeletion=True)
│   └─ computeWeldJoint(params).createOrUpdate(...)  (siehe 2.5 / 2.6)
└─ rollTo(before) · setStartAndEndFeatures(erstes, letztes) · rollTo(after)
```

### 2.3 Feature bearbeiten (Zeitleiste → „Feature bearbeiten“)

```
Fusion startet Command 'Kabelfrikkler_WeldJointEdit' → onEdit(args)        fusion_cf_addin.py:125
├─ customFeature = ui.activeSelections[0].entity
├─ customFeatureToParams(customFeature)                            Parameter (Fallback: Named Value, dann
│                                                                  eingebaute Defaults) + 'faces' + 'mode' + 'tabPoints'
├─ createInputs(command, params)
└─ verbindet zusätzlich activate→onActivate, execute→onExecuteEdit, destroy→onDestroy

activate → onActivate(args)                                       fusion_cf_addin.py:172
├─ _savedTimelineObject = currentTimelineObject()
├─ timelineObject.rollTo(rollBefore=True) · command.beginStep()
├─ with computeDisabled(): paramsToInputs(params, inputs)          Flächen, Modus, Werte, Sichtbarkeit, dann Punkte
└─ command.doExecutePreview()

executePreview → onPreview → _updateCustomFeature(params, customFeature)
OK             → onExecuteEdit → _updateCustomFeature(...) · Zeitleiste zurück auf gemerkte Position
Ende           → onDestroy → bei OK: Werte als letzte Einstellungen speichern

_updateCustomFeature(params, customFeature)                        fusion_cf_addin.py:286
├─ rollTo(before)
├─ Parameter setzen; fehlt ein Parameter (Feature von älterer Version) → als Named Value speichern
├─ dependencies.deleteAll() + add(...)
├─ customNamedValues.addOrSetValue(...)
├─ features = list(customFeature.features) · setStartAndEndFeatures(None, None) · rollTo(after)
├─ createOrUpdateChildFeatures(params, features, allowFeatureCreationAndDeletion=True)
└─ rollTo(before) · setStartAndEndFeatures(erstes, letztes) · rollTo(after)
```

### 2.4 Automatische Neuberechnung (Körper/Skizze davor geändert, Parameter im Parameter-Dialog geändert)

```
customFeatureCompute → onCompute(args)                             fusion_cf_addin.py:147
├─ wenn _computeDisabled → sofort zurück (eigene Vorschau/Ausführung läuft gerade)
├─ saved = currentTimelineObject()
├─ rollTo(before) · params = customFeatureToParams(f) · features = list(f.features)
├─ setStartAndEndFeatures(None, None) · rollTo(after)
├─ createOrUpdateChildFeatures(params, features, allowFeatureCreationAndDeletion=False)
│     → nur vorhandene BaseFeature-Körper aktualisieren, keine Features anlegen/löschen
├─ rollTo(before) · setStartAndEndFeatures(...) · rollTo(after)
└─ saved.rollTo(False)
```

Hinweise:
- Die letzten Einstellungen spielen hier **keine** Rolle – gespeicherte Features rechnen immer mit
  ihren eigenen Werten (fehlende → eingebaute Defaults).
- Werte, die bei älteren Features als Named Value gespeichert sind, lösen bei Änderung im
  Parameter-Dialog keine Neuberechnung aus (sie stehen dort nicht). Über „Feature bearbeiten“ geht es.

### 2.5 Geometrie berechnen – `computeWeldJoint(params)` (fusion_weld_joint.py:477)

Koordinatensystem pro Stoß („Nominal“), daraus ergeben sich alle Richtungen ohne Angabe der
Materialstärke:

| Achse | Richtung | Ausdehnung der Überlappung |
|---|---|---|
| **Z** | entlang der Stoßkante | Länge des Stoßes (`minZ … maxZ`) |
| **Y** | durch Blech A, ab dessen Außenfläche (Y = 0) | Dicke von A (`minY … maxY`) |
| **X** | quer durch Blech B | Dicke von B (`minX … maxX`) |

```
computeWeldJoint(params) → BaseCombines
├─ < 2 Flächen → leeres BaseCombines
├─ Parameter normalisieren, Punkte → Weltkoordinaten (pointGeometry)
├─ baseCombines.addTargetBody(face.body) für alle gewählten Körper
└─ für (faceA, faceB, buttingFace) in getAllButtingFaces(faces):
    ├─ Normalen nach innen ausrichten, Nominal-System aufbauen (jointToNominal / nominalToJoint)
    ├─ Überlappung: buttingFace bis zur Außenkante extrudieren ∩ bodyA → BoundingBox
    ├─ tabOffsets = Startpositionen der Tabs/B-Finger ab minZ (siehe Abschnitt 4)
    │     Points:  Punkte, die auf diesem Stoß liegen     → keine → Paar übersprungen
    │     Tabs:    Stoß kürzer als ein Tab                → Paar übersprungen
    │     Fingers: zu wenige Finger                       → Paar übersprungen
    ├─ Vorlage-Finger = createSimpleBox(…, Breite fingerBWidth)
    ├─ stumpfer Winkel (> 90°): Finger anschrägen
    ├─ Cutter für A (Schlitz):
    │     createWidenedBody(Vorlage, Z, slotClearance)                        Slot Clearance
    │     wenn holeClearance > 0 und isClosedHole(...):                       Hole Clearance
    │         Cutter und Schnittbereich (overlap) zusätzlich in X verbreitern
    ├─ Joiner für B (Tab) = Vorlage, Y < minY + tabSetback abgeschnitten       Tab Setback
    │     tabSetback ≥ Dicke von A → keine Tabs, nur Schlitze
    └─ für jeden tabOffset:
          Cutter hochschieben → ∩ Schnittbereich → zurücktransformieren → difference(bodyA)
          Joiner hochschieben → ∩ overlap        → zurücktransformieren → union(bodyB)
```

### 2.6 Ergebnis ins Modell bringen – `BaseCombines.createOrUpdate()` (fusion_base_combines.py:26)

Pro Zielkörper entsteht ein **Feature-Tripel** in der Zeitleiste:

```
[BaseFeature "Körper *"]  →  [Combine JOIN (Werkzeug behalten)]  →  [Combine INTERSECT]
      enthält M                   Ziel T := T ∪ M                        T := (T ∪ M) ∩ M = M
```

M = Kopie des Originalkörpers mit allen Bool-Ops angewendet. Der Trick mit Join + Intersect macht
den Originalkörper T **identisch zu M**, ohne dass T ersetzt wird – nachfolgende Features, die sich auf
T beziehen, bleiben gültig.

```
createOrUpdate(existingFeatures, allowFeatureCreationAndDeletion)
├─ vorhandene Features in Dreiergruppen durchgehen (zip(*[iter(list)]*3))
│   ├─ Zielkörper hat keine Ops mehr und Löschen erlaubt → Tripel löschen
│   └─ sonst merken
├─ (wenn erlaubt) Zielkörper ohne vorhandene Features hinzufügen
└─ für jeden Zielkörper:
    ├─ M = tempBrepMgr.copy(T); alle BooleanOperations anwenden
    ├─ BaseFeature vorhanden → startEdit · updateBody(bodies[0], M) · finishEdit
    │  sonst                 → baseFeatures.add · startEdit · bRepBodies.add(aContainingBody(M)) ·
    │                          updateBody(…, M) · finishEdit
    ├─ sourceBodies[0].name = T.name + ' *'
    └─ Join- und Intersect-Combine anlegen bzw. targetBody nachziehen
```

### 2.7 Stoppen

```
stop(context)                                                     WeldJoint.py:31
└─ thisAddIn.destroy()                                            fusion_cf_addin.py:86
   ├─ customFeatureCompute.remove(computeHandler)   (Definition überlebt den Neustart)
   └─ alle Controls + CommandDefinitions 'Kabelfrikkler_WeldJointCreate'/'…Edit' löschen
```

---

## 3. Referenz aller Funktionen und Klassen

Legende: **genutzt von** = wer ruft auf · ∅ = im Plugin nicht verwendet

### 3.1 `WeldJoint.py` – Einstieg

| Name | Zeile | Zweck | genutzt von |
|---|---|---|---|
| `_modules` | [11](Contents/WeldJoint.py:11) | eigene Module in Abhängigkeitsreihenfolge | `run` |
| `thisAddIn` | [13](Contents/WeldJoint.py:13) | globale Instanz von `WeldJointAddIn` (hält Handler am Leben) | `run`, `stop` |
| `run(context)` | [16](Contents/WeldJoint.py:16) | Module neu laden, `WeldJointAddIn()` erzeugen | Fusion |
| `stop(context)` | [31](Contents/WeldJoint.py:31) | `thisAddIn.destroy()` | Fusion |

### 3.2 `fusion_weld_joint.py` – Fachlogik

| Name | Zeile | Zweck | genutzt von |
|---|---|---|---|
| `WeldJointParameters` (dataclass) | [17](Contents/fusion_weld_joint.py:17) | alle Parameter, siehe Tabelle unten | überall in `WeldJointAddIn` |
| `_parameterDescriptions` | [53](Contents/fusion_weld_joint.py:53) | ID → Anzeigename aller 11 Feature-Parameter (IDs = Input-IDs = Feldnamen) | Parameter-Hooks, Einstellungen |
| `_modeNames` | [68](Contents/fusion_weld_joint.py:68) | Modus-ID → Text im Dropdown | `createInputs`, `selectedMode`, `paramsToInputs`, `loadSettings` |
| `_modeInputIds` | [75](Contents/fusion_weld_joint.py:75) | Modus-ID → Eingaben, die nur in diesem Modus sichtbar sind | `updateInputVisibility` |
| `_tooltips` | [83](Contents/fusion_weld_joint.py:83) | Input-ID → (Kurz-Tooltip, längere Beschreibung mit HTML) | `createInputs` |
| `_toolClipFolder` | [123](Contents/fusion_weld_joint.py:123) | `Contents/Resources/ToolClips` – Tooltip-Bilder `<ID>.png`, `command.png` | `setTooltip`, `__init__` |
| `_settingsPath` | [126](Contents/fusion_weld_joint.py:126) | `Contents/last_settings.json` | `loadSettings`, `saveSettings` |
| `WeldJointAddIn` | [129](Contents/fusion_weld_joint.py:129) | Unterklasse von `FusionCustomFeatureAddIn` | `WeldJoint.run` |
| `.__init__()` | [133](Contents/fusion_weld_joint.py:133) | ID `Kabelfrikkler_WeldJoint`, Name, Tooltips, Icon-Ordner, Button-Bild, Toolbar-Positionen | `run` |
| `.createInputs(command, params)` | [155](Contents/fusion_weld_joint.py:155) | Dialog aufbauen, Tooltips setzen (Reihenfolge siehe unten) | `onCreate`, `onEdit` |
| `.canSelect(entity, input)` | [217](Contents/fusion_weld_joint.py:217) | Faces: nur ebene Flächen auf Volumenkörpern | `onPreSelect` |
| `.inputChanged(input, inputs)` | [226](Contents/fusion_weld_joint.py:226) | `mode` geändert → Sichtbarkeit umschalten | `onInputChanged` |
| `.areInputsValid(inputs)` | [230](Contents/fusion_weld_joint.py:230) | sichtbare Ausdrücke gültig; Fingers: Anzahl ganzzahlig + ungerade; Points: mind. 1 Punkt | `onValidateInputs` |
| `.defaultParams()` | [265](Contents/fusion_weld_joint.py:265) | eingebaute Defaults + letzte Einstellungen (`loadSettings`) | `onCreate` |
| `.commandCompleted(params)` | [268](Contents/fusion_weld_joint.py:268) | `saveSettings(params)` | `onDestroy` |
| `.paramsToInputs(params, inputs)` | [271](Contents/fusion_weld_joint.py:271) | Parameter → Dialog. Reihenfolge wichtig: erst Sichtbarkeit, dann Punkte wählen (Ausblenden löscht die Auswahl) | `onActivate` |
| `.inputsToParams(inputs)` | [290](Contents/fusion_weld_joint.py:290) | Dialog → `WeldJointParameters` | `onPreview`, `onExecuteCreate`, `onExecuteEdit` |
| `.customFeatureToParams(feature)` | [308](Contents/fusion_weld_joint.py:308) | gespeichertes Feature → Parameter; Fallback auf **eingebaute** Defaults (nicht die letzten Einstellungen); `mode` mit Fallback auf altes `tabMode` | `onEdit`, `onActivate`, `onCompute` |
| `.getCustomParameters(params)` | [338](Contents/fusion_weld_joint.py:338) | alle 11 Parameter als Dict | `_create…`, `_update…`, `paramsToInputs` |
| `.getCustomParameterDescriptions()` | [341](Contents/fusion_weld_joint.py:341) | `_parameterDescriptions` | `getCustomParameterDescription` |
| `.getCustomNamedValues(params)` | [344](Contents/fusion_weld_joint.py:344) | `faces`, `mode`, `tabPoints` (Tokens) | `_create…`, `_update…` |
| `.getDependencies(params)` | [351](Contents/fusion_weld_joint.py:351) | Körper `body0…` und Tab-Punkte `point0…` als Abhängigkeiten (Skizze ändern → Neuberechnung) | `_create…`, `_update…` |
| `.createOrUpdateChildFeatures(params, existing, allow)` | [363](Contents/fusion_weld_joint.py:363) | `computeWeldJoint(params).createOrUpdate(...)` | `onCompute`, `_create…`, `_update…` |
| `addLengthInput(inputs, id, name, param, isZeroAllowed)` | [375](Contents/fusion_weld_joint.py:375) | Längen-Eingabe mit Untergrenze 0 (exklusiv oder inklusiv) | `createInputs` |
| `setTooltip(input, tooltip, description)` | [395](Contents/fusion_weld_joint.py:395) | `tooltip`, `tooltipDescription`, `toolClipFilename` (wenn `<ID>.png` existiert) | `createInputs` |
| `loadSettings(params)` | [407](Contents/fusion_weld_joint.py:407) | letzte Einstellungen anwenden; im aktuellen Dokument ungültige Ausdrücke (z. B. fremde Benutzerparameter) werden übersprungen | `defaultParams` |
| `saveSettings(params)` | [428](Contents/fusion_weld_joint.py:428) | Modus + Ausdrücke/Einheiten aller 11 Parameter als JSON speichern | `commandCompleted` |
| `selectedMode(inputs)` | [444](Contents/fusion_weld_joint.py:444) | ID des im Dropdown gewählten Modus | `areInputsValid`, `inputsToParams`, `updateInputVisibility` |
| `updateInputVisibility(inputs)` | [452](Contents/fusion_weld_joint.py:452) | nur Eingaben des gewählten Modus anzeigen | `createInputs`, `inputChanged`, `paramsToInputs` |
| `featureParameter(feature, id, default)` | [461](Contents/fusion_weld_joint.py:461) | Parameter lesen → sonst Named Value → sonst Default | `customFeatureToParams` |
| `computeWeldJoint(params)` | [477](Contents/fusion_weld_joint.py:477) | **gesamte Geometrie**, liefert `BaseCombines` | `createOrUpdateChildFeatures` |
| `pointGeometry(point)` | [721](Contents/fusion_weld_joint.py:721) | Position eines Skizzenpunkts (`worldGeometry`) oder Konstruktionspunkts | `computeWeldJoint` |
| `isClosedHole(overlap, body, nominalToJoint, distance)` | [730](Contents/fusion_weld_joint.py:730) | prüft per Volumen, ob Blech A auf **beiden** Seiten quer zur Kante weitergeht (Loch in der Fläche statt Kerbe an der Kante) | `computeWeldJoint` |
| `getAllButtingFaces(outsideFaces)` | [755](Contents/fusion_weld_joint.py:755) | alle geordneten Paare (A, B) → `(faceA, faceB, buttingFace)` | `computeWeldJoint` |
| `getButtingFaces(faceA, faceB)` | [765](Contents/fusion_weld_joint.py:765) | Stirnflächen von B, die an A anliegen (eben, parallel zu A, koplanar und überlappend mit einer Fläche von A) | `getAllButtingFaces` |
| `clamp(value, min, max)` | [812](Contents/fusion_weld_joint.py:812) | Wert begrenzen | `createInputs`, `computeWeldJoint` |
| `withoutHtml(string)` | [820](Contents/fusion_weld_joint.py:820) | HTML-Tags entfernen | `areInputsValid` |

**Parameter und Dialog** (Reihenfolge wie im Dialog; Speicherung: P = Feature-Parameter, N = Named Value;
Modi: F = Fingers, T = Tabs: Spacing, P = Tabs: Points; „gemerkt“ = in `last_settings.json`)

| ID | Label | Default | sichtbar | Speicherung | gemerkt | Bedeutung |
|---|---|---|---|---|---|---|
| `faces` | Faces | – | immer | N | nein | gewählte Außenflächen (Tokens) |
| `mode` | Mode | Fingers | immer | N | ja | `fingers` / `tabs` / `points` |
| `tabPoints` | Tab Points | – | P | N + Abhängigkeit | nein | Skizzen-/Konstruktionspunkte, je ein Tab mittig darauf |
| `minFingers` | Min Fingers | 3 | F | P | ja | min. Gesamtzahl Finger (ungerade) |
| `maxFingers` | Max Fingers | 33 | F | P | ja | max. Gesamtzahl Finger (ungerade) |
| `minFingerWidth` | Min Finger Width | 25 mm / 1" | F | P | ja | |
| `maxFingerWidth` | Max Finger Width | 150 mm / 6" | F | P | ja | |
| `fingerRatio` | Finger Ratio | 0,5 | F | P | ja | Anteil der B-Finger an einer Periode |
| `tabWidth` | Tab Width | 20 mm / ¾" | T, P | P | ja | Breite jedes Tabs entlang der Kante |
| `tabSpacing` | Tab Spacing | 100 mm / 4" | T | P | ja | max. Lücke zwischen Tabs und zu den Enden (Kante zu Kante) |
| `margin` | Corner Margin | 0 | F, T | P | ja | Finger/Tabs rücken um diesen Wert zusätzlich von beiden Enden (Ecken) nach innen |
| `tabSetback` | Tab Setback | 0 | immer | P | ja | Tabs enden so weit unter der Außenfläche von A |
| `slotClearance` | Slot Clearance | 0 | immer | P | ja | Schlitz je Seite länger (entlang der Kante) |
| `holeClearance` | Hole Clearance | 0 | immer | P | ja | Schlitz je Seite breiter (quer), nur bei geschlossenen Löchern |

Alte Features (vor dieser Version) haben zusätzlich noch den ungenutzten Parameter `bitDiameter`.

### 3.3 `fusion_cf_addin.py` – generische Custom-Feature-Basisklasse

**Event-Handler** (von Fusion aufgerufen, über `newEventHandler` verpackt):

| Methode | Zeile | Event | Zweck |
|---|---|---|---|
| `__init__(…, toolClipFilename=None)` | [16](Contents/fusion_cf_addin.py:16) | – | Handler, Button-/Edit-Definition (inkl. Button-Bild), CustomFeatureDefinition, Toolbar |
| `destroy()` | [86](Contents/fusion_cf_addin.py:86) | – | Compute-Handler abhängen, Controls + CommandDefinitions entfernen |
| `onCreate(args)` | [110](Contents/fusion_cf_addin.py:110) | `commandCreated` (Create) | Dialog mit `defaultParams()` |
| `onEdit(args)` | [125](Contents/fusion_cf_addin.py:125) | `commandCreated` (Edit) | Dialog mit Werten des Features |
| `onCompute(args)` | [147](Contents/fusion_cf_addin.py:147) | `customFeatureCompute` | Neuberechnung ohne Feature-Anlage |
| `onActivate(args)` | [172](Contents/fusion_cf_addin.py:172) | `activate` (nur Edit) | Zeitleiste zurückrollen, Selektion füllen, Vorschau |
| `onPreSelect(args)` | [190](Contents/fusion_cf_addin.py:190) | `preSelect` | → `canSelect` |
| `onInputChanged(args)` | [194](Contents/fusion_cf_addin.py:194) | `inputChanged` | → `inputChanged` |
| `onValidateInputs(args)` | [197](Contents/fusion_cf_addin.py:197) | `validateInputs` | → `areInputsValid` |
| `onPreview(args)` | [201](Contents/fusion_cf_addin.py:201) | `executePreview` | Feature anlegen bzw. aktualisieren, `_lastParams` merken, `isValidResult = True` |
| `onExecuteCreate(args)` | [220](Contents/fusion_cf_addin.py:220) | `execute` (Create) | Feature anlegen |
| `onExecuteEdit(args)` | [229](Contents/fusion_cf_addin.py:229) | `execute` (Edit) | Feature aktualisieren, Zeitleiste zurücksetzen |
| `onDestroy(args)` | [245](Contents/fusion_cf_addin.py:245) | `destroy` | bei `CompletedTerminationReason` (OK) → `commandCompleted(_lastParams)` |

**Interne Methoden:**

| Methode | Zeile | Zweck |
|---|---|---|
| `_createCustomFeature(params)` | [253](Contents/fusion_cf_addin.py:253) | CustomFeatureInput aufbauen, Feature anlegen, Kind-Features erzeugen, gruppieren |
| `_updateCustomFeature(params, feature)` | [286](Contents/fusion_cf_addin.py:286) | Parameter (fehlende → Named Value), Abhängigkeiten, Named Values setzen, Kind-Features aktualisieren |
| `computeDisabled()` (contextmanager) | [371](Contents/fusion_cf_addin.py:371) | unterdrückt `onCompute`/`onPreview`, solange das Plugin selbst das Modell ändert (`try/finally`) |

**Hooks** (Standard-Implementierung leer; `WeldJointAddIn` überschreibt alle außer
`getCustomParameterDescription`):

`createInputs` [321](Contents/fusion_cf_addin.py:321) · `canSelect` [324](Contents/fusion_cf_addin.py:324) ·
`inputChanged` [327](Contents/fusion_cf_addin.py:327) · `areInputsValid` [330](Contents/fusion_cf_addin.py:330) ·
`defaultParams` [333](Contents/fusion_cf_addin.py:333) · `commandCompleted` [336](Contents/fusion_cf_addin.py:336) ·
`paramsToInputs` [339](Contents/fusion_cf_addin.py:339) · `inputsToParams` [342](Contents/fusion_cf_addin.py:342) ·
`customFeatureToParams` [345](Contents/fusion_cf_addin.py:345) · `getCustomParameters` [348](Contents/fusion_cf_addin.py:348) ·
`getCustomParameterDescriptions` [351](Contents/fusion_cf_addin.py:351) ·
`getCustomParameterDescription(id)` [354](Contents/fusion_cf_addin.py:354) (Beschreibung oder ID) ·
`getCustomNamedValues` [357](Contents/fusion_cf_addin.py:357) · `getDependencies` [360](Contents/fusion_cf_addin.py:360) ·
`createOrUpdateChildFeatures` [363](Contents/fusion_cf_addin.py:363)

### 3.4 `fusion_base_combines.py` – Ergebnis ins Modell (unverändert)

| Name | Zeile | Zweck | genutzt von |
|---|---|---|---|
| `_BooleanOperations` (dataclass) | [10](Contents/fusion_base_combines.py:10) | Zielkörper + Liste seiner `BooleanOperation`s | `BaseCombines` |
| `BaseCombines` | [15](Contents/fusion_base_combines.py:15) | sammelt Ops pro Zielkörper (Schlüssel `revisionId`) | `computeWeldJoint` |
| `.add(booleanOperation)` | [19](Contents/fusion_base_combines.py:19) | Op zum Zielkörper hinzufügen | `computeWeldJoint` |
| `.addTargetBody(body)` | [22](Contents/fusion_base_combines.py:22) | Zielkörper registrieren (auch ohne Ops) | `computeWeldJoint`, `add` |
| `.createOrUpdate(existing, allow)` | [26](Contents/fusion_base_combines.py:26) | Tripel BaseFeature/Join/Intersect anlegen oder aktualisieren (siehe 2.6) | `createOrUpdateChildFeatures` |

### 3.5 `fusion_brep_util.py` – temporäre Geometrie

| Name | Zeile | Zweck | genutzt von |
|---|---|---|---|
| `tempBrepMgr` | [8](Contents/fusion_brep_util.py:8) | globaler `TemporaryBRepManager` | überall |
| `dumpBody(body, indent)` | [11](Contents/fusion_brep_util.py:11) | Debug-Text über einen Körper | ∅ (Debug) |
| `definitionOfBody(body)` | [52](Contents/fusion_brep_util.py:52) | Körper → `BRepBodyDefinition` (Neuaufbau als Volumenkörper) | `createObliquePrism` |
| `createSimpleBox(x, y, z, dx, dy, dz)` | [88](Contents/fusion_brep_util.py:88) | achsparalleler Quader ab Min-Punkt | `computeWeldJoint` |
| `createFaceFromCurves(curves)` | [104](Contents/fusion_brep_util.py:104) | geschlossene ebene Kurven → Fläche | `computeWeldJoint` |
| `createPrism(base, height)` | [112](Contents/fusion_brep_util.py:112) | gerades Prisma entlang Flächennormale | `computeWeldJoint` |
| `createObliquePrism(base, direction)` | [124](Contents/fusion_brep_util.py:124) | schräges Prisma | `computeWeldJoint`, `createPrism` |
| `createWidenedBody(body, direction, distance, maxStep)` | [156](Contents/fusion_brep_util.py:156) | Körper in ±`direction` um `distance` verbreitern (Vereinigung verschobener Kopien, Schrittweite ≤ `maxStep`) | `computeWeldJoint` |
| `boundingBoxBody(body, margin)` | [183](Contents/fusion_brep_util.py:183) | Quader um Körper | ∅ |
| `aContainingBody(body)` | [202](Contents/fusion_brep_util.py:202) | Kugel, die den Körper sicher enthält | `BaseCombines.createOrUpdate` |
| `anExternalBody(body)` | [219](Contents/fusion_brep_util.py:219) | Kugel außerhalb des Körpers | ∅ |
| `anInternalBody(body)` | [240](Contents/fusion_brep_util.py:240) | winzige Kugel im Körper | ∅ |
| `BooleanOperation` (dataclass) | [250](Contents/fusion_brep_util.py:250) | `targetBody`, `toolBody`, `operation`; `.difference` / `.intersection` / `.union` | `computeWeldJoint`, `BaseCombines` |

### 3.6 `fusion_util.py` – allgemeine Hilfen (unverändert)

| Name | Zeile | Zweck | genutzt von |
|---|---|---|---|
| `with_logging(f)` | [10](Contents/fusion_util.py:10) | Decorator: Ein-/Austritt loggen | ∅ (Debug) |
| `log(message)` | [20](Contents/fusion_util.py:20) | Text ins Fenster TEXT COMMANDS | überall |
| `messageBox(message)` | [25](Contents/fusion_util.py:25) | Meldungsfenster | ∅ |
| `handleException()` | [29](Contents/fusion_util.py:29) | Traceback mit `Klasse.Funktion`-Präfix loggen | `newEventHandler`, `run`, `stop`, `loadSettings`, `saveSettings` |
| `newObjectCollection(objects)` | [37](Contents/fusion_util.py:37) | Liste → `ObjectCollection` | `BaseCombines.createOrUpdate` |
| `newEventHandler(handler, superclass)` | [44](Contents/fusion_util.py:44) | Handler-Klasse, deren `notify` die Methode aufruft und Exceptions loggt | `FusionCustomFeatureAddIn.__init__` |
| `currentTimelineObject()` | [54](Contents/fusion_util.py:54) | Objekt vor dem Zeitleisten-Marker | `onCompute`, `onActivate` |
| `newValueInput(value)` | [60](Contents/fusion_util.py:60) | Python-Wert → `ValueInput` | ∅ |
| `cmOrIn(cm, inches)` | [72](Contents/fusion_util.py:72) | Default je nach Benutzer-Einheit | `WeldJointParameters` |
| `UserInputError(input, message)` | [81](Contents/fusion_util.py:81) | Fehler mit Bezug auf ein Input | `areInputsValid` |
| `Parameter` | [88](Contents/fusion_util.py:88) | Ausdruck + Einheit; aus String, Fusion-Parameter oder CommandInputs; `UNITLESS = 'rad/rad'` | überall |
| `Parameter.length(cm)` / `.value` / `.expression` / `.units` / `.valueInput` | [136](Contents/fusion_util.py:136)–[166](Contents/fusion_util.py:166) | | |
| `EntityRef(entityOrToken)` | [172](Contents/fusion_util.py:172) | dauerhafte Referenz über `entityToken` | `WeldJointParameters.faces`, `.tabPoints` |
| `dumpMenus()` | [195](Contents/fusion_util.py:195) | alle Toolbar-/Panel-/Control-IDs auflisten | ∅ (Hilfe) |

---

## 4. Rechenregeln (computeWeldJoint)

Begriffe: **A** = Blech, in das geschlitzt wird (seine Außenfläche liegt außen an der Ecke).
**B** = Blech, dessen Stirnfläche an A stößt (`buttingFace`) und das die Finger/Tabs bekommt.
Welches Blech A bzw. B ist, ergibt sich aus der Geometrie, nicht aus der Größe der Finger.

```
Z-Richtung = entlang der Stoßkante (lengthWithMargins = maxZ − minZ der Überlappung)

 minZ                                                                    maxZ
 |endMargin| A | B | A | B | A | … | B | A |endMargin|
             └─ fingerAWidth   └─ fingerBWidth (= Tab bzw. B-Finger)
```

- `fingers` ist immer **ungerade**; A behält `ceil(n/2)` Abschnitte, B bekommt `floor(n/2)` Finger/Tabs.
- **Tabs: Points:** Ein Punkt gehört zu einem Stoß, wenn er (im Nominal-System) innerhalb der Stoßlänge
  liegt und quer dazu höchstens **eine Materialstärke** (die größere von A und B) neben dem
  Überlappungsbereich. Typisch: Skizze auf der Außenfläche von A oder B, Punkt auf der Stoßkante bzw.
  im Streifen, mit Bemaßung zur Ecke. Wo der Punkt quer zur Kante liegt (Mitte oder Rand des Tabs),
  ist egal – entlang der Kante sitzt der Tab mittig auf dem Punkt. Ragt er über das Stoßende hinaus,
  wird er abgeschnitten. Punkte, die auf keinem Stoß liegen, werden still ignoriert.
  Corner Margin und Tab Spacing gelten hier nicht.
- **Tabs: Spacing:** `length = Stoßlänge − 2·Corner Margin`;
  `tabs = max(ceil((length − Spacing) / (TabWidth + Spacing)), 1)`;
  Lücke `fingerAWidth = (length − tabs·TabWidth) / (tabs + 1)` ≤ Spacing. Alle Lücken (auch an den
  Enden) sind gleich groß. Beispiel: 1000 mm, Tab 20, Spacing 150 → 5 Tabs, Lücken 150 mm.
- **Fingers:** wie im Original – Anzahl über `Min Finger Width`, begrenzt durch
  `Max Fingers`, dann exakt einpassen; `fingerRatio = B/(A+B)`.
- **Slot Clearance c:** Cutter = Vorlage ⊕ [−c, +c] in Z → Schlitz = Tab + 2c.
- **Hole Clearance h:** nur wenn `isClosedHole` (Material von A auf beiden Seiten in X):
  Cutter **und** Schnittbereich ⊕ [−h, +h] in X → Lochbreite = Dicke B + 2h. An einer Ecke
  (Kerbe) passiert nichts.
- **Tab Setback s:** Tab endet bei Y = minY + s, also s unter der Außenfläche von A.
  s ≥ Dicke von A → keine Tabs, nur Schlitze.
- Alle Clearances sind **je Seite**.

---

## 5. Offene Punkte / Auffälligkeiten

1. **Compute kann keine neuen Stöße anlegen** – `allowFeatureCreationAndDeletion=False` (von der
   API vorgegeben). Kommt durch eine Änderung weiter vorne ein *neuer* Zielkörper dazu, erscheint er
   erst nach „Feature bearbeiten“ → OK.
2. `BRepBody.volume` auf temporären Körpern (in `isClosedHole`) – laut Doku ohne Einschränkung.
   Die Unterscheidung Loch/Ecke wurde nicht gezielt getestet, bisher aber keine Auffälligkeit gemeldet.
3. Stumpfe Winkel + Hole Clearance: Die Verbreiterung erfolgt in X (Nominal), bei schrägen
   Schlitzwänden ist das senkrechte Spiel dann kleiner als h.
4. `getButtingFaces` kann dieselbe Stirnfläche mehrfach liefern → doppelte (gleiche) Bool-Ops,
   nur langsamer.
5. `addTextBoxCommandInput` ist laut API „retired“ (funktioniert weiter).
6. `newValueInput`: `bool`-Zweig unerreichbar (ungenutzt).
7. Punkte-Modus: Die Skizze muss in der Zeitleiste **vor** dem Weld-Joint-Feature liegen. Bei Körpern
   in verschobenen Unterkomponenten ist ungetestet, ob Punkt- (Welt-) und Flächenkoordinaten
   zusammenpassen.
8. Punkte-Modus: Wechselt man den Modus weg von *Tabs: Points*, wird die Punktauswahl geleert (Fusion
   löscht die Auswahl ausgeblendeter Auswahlfelder).
9. Letzte Einstellungen liegen im Add-in-Ordner (`Contents/last_settings.json`) – gehen bei einer
   Neuinstallation verloren und gelten pro Windows-Benutzer.
10. Presets (benannte Wertesätze, z. B. pro Zulieferer) sind noch nicht umgesetzt.
