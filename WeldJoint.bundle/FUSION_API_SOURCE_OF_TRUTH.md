# Fusion API – Source of Truth für dieses Plugin

Stand: 25.10.2026 · Gilt für Fusion (ehem. Fusion 360) mit **Python 3.14** (auf diesem Rechner belegt durch
`Contents/__pycache__/*.cpython-314.pyc`).

Dieses Dokument fasst zusammen, wie Fusion-Add-ins aufgebaut sind und welche API-Teile das
Weld Joint-Plugin nutzt bzw. für die Schweiß-Anpassungen voraussichtlich braucht. Alles, was hier
steht, ist aus der offiziellen Autodesk-Doku (Links unten) oder direkt aus dem Plugin-Code belegt.
Punkte, die **nicht** offiziell belegt sind, sind mit ⚠️ *unverifiziert* markiert.

---

## 0. Quellen

| Thema | Link |
|---|---|
| API-Referenz (Einstieg) | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ |
| Scripts & Add-ins schreiben/debuggen | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/WritingDebugging_UM.htm |
| Python-Spezifisches | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/PythonSpecific_UM.htm |
| Commands (Lebenszyklus, Events) | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Commands_UM.htm |
| Command Inputs | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CommandInputs_UM.htm |
| CommandInputs-Objekt (alle `add*`) | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/core_CommandInputs.htm |
| Selection-Filter | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/SelectionFilters_UM.htm |
| Custom Features (Konzept) | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/CustomFeatures_UM.htm |
| CustomFeature-Objekt | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_CustomFeature.htm |
| CustomFeatureDefinition | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_CustomFeatureDefinition.htm |
| CustomNamedValues | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_CustomNamedValues.htm |
| BaseFeature | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_BaseFeature.htm |
| CombineFeatures.createInput | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_CombineFeatures_createInput.htm |
| TemporaryBRepManager | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_TemporaryBRepManager.htm |
| B-Rep-Geometrie | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BRepGeometry_UM.htm |
| Python 3.12 → 3.14 Upgrade (Blog, 08.01.2026) | https://blog.autodesk.io/fusion-python-upgrade-and-more/ |
| Publishing Guidelines (Bundle-Struktur) | https://aps.autodesk.com/node/3050 |
| Forum: Modul-Cache beim Neuladen | https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/when-is-add-in-code-reloaded-what-is-the-best-development/td-p/9744789 |

Hinweis: Die Autodesk-Hilfe hat Seiten mit Präfix (`core_…`, `fusion_…`) und ohne. Wenn eine URL
404 liefert, die Variante mit Präfix probieren, z. B. `core_CommandInputs_addValueInput.htm`.

---

## 1. Script vs. Add-in

| | Script | Add-in |
|---|---|---|
| Lebensdauer | `run()` läuft einmal, danach entladen | bleibt geladen, reagiert auf Events |
| Einstieg | `run(context)` | `run(context)` + `stop(context)` |
| Buttons in der Toolbar | nein | ja |
| Manifest `type` | `"script"` | `"addin"` |

- `run(context)`: `context` ist ein Python-`dict`, enthält `IsApplicationStartup` (bool).
- `stop(context)`: nur Add-ins; `context['IsApplicationClosing']` (bool). Hier **alle UI-Elemente
  wieder entfernen**, die in `run` erzeugt wurden.

---

## 2. Speicherorte und Paketstruktur

### Wo Fusion sucht (Windows)

| Ort | Pfad |
|---|---|
| Standard-Add-ins | `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns` |
| Standard-Scripts | `%APPDATA%\Autodesk\Autodesk Fusion 360\API\Scripts` |
| **App-Store-Bundles (dieses Plugin)** | `%APPDATA%\Autodesk\ApplicationPlugins\<Name>.bundle` |
| Add-ins ohne Bundle | `%APPDATA%\Autodesk\FusionAddins` |
| Beliebiger Ort | über „Scripts and Add-Ins“ → **+** → „Script or add-in from device“ verlinken |

### Bundle-Aufbau (App-Store-Format, so ist Weld Joint installiert)

```
<Name>.bundle\
├── PackageContents.xml      ← Paketbeschreibung; ComponentEntry.ModuleName zeigt auf das Manifest
└── Contents\
    ├── <Name>.manifest      ← JSON, beschreibt das Add-in
    ├── <Name>.py            ← Haupt-Python-Datei (gleicher Name wie Manifest)
    └── …                    ← weitere Module, Icons, Doku
```

### Manifest-Felder (`.manifest`, JSON)

| Feld | Bedeutung |
|---|---|
| `autodeskProduct` | aktuell `"Fusion"`; ältere Add-ins (auch Weld Joint) nutzen `"Fusion360"` – funktioniert weiter |
| `type` | `"addin"` oder `"script"` |
| `id` | wird laut Doku nicht verwendet |
| `author`, `version` | Anzeige im Dialog |
| `description` | Objekt nach Sprach-LCID, `""` = Standard, `1031` = Deutsch |
| `runOnStartup` | `true` = beim Fusion-Start laden. **Doku empfiehlt `false` während der Entwicklung/Debugging** |
| `supportedOS` | `"windows"`, `"mac"`, `"windows\|mac"` |
| `editEnabled` | erlaubt „Edit“ im Dialog |
| `iconFilename` | optionales Icon für den Dialog |

---

## 3. Entwicklungs-Workflow (Live-Testen)

- **Starten/Stoppen:** Fusion → Registerkarte UTILITIES → **Scripts and Add-Ins** → Add-in
  auswählen → Start/Stop. Stop ruft `stop(context)` mit `IsApplicationClosing = False`.
- **Editieren/Debuggen:** „Edit in code editor“ öffnet VS Code (Python-Extension wird von Fusion
  installiert). Breakpoints setzen, F5. Für Add-ins vorher „Run on Startup“ aus und laufende Instanz
  stoppen.
- **Log-Ausgaben:** Fenster **TEXT COMMANDS** (Ansicht → Text Commands einblenden). Das Plugin
  schreibt dort via `palettes.itemById('TextCommands').writeText(...)`; die offizielle Alternative
  ist `adsk.core.Application.get().log(...)`.
- **⚠️ Modul-Cache beim Neuladen:** Fusion nutzt **eine einzige Python-Laufzeit**. Laut Forum werden
  bereits importierte Untermodule beim Stop/Start eines Add-ins nicht zwingend neu geladen. Für
  Weld Joint heißt das: Änderungen an `fusion_weld_joint.py`, `fusion_util.py` usw. könnten erst nach
  einem Fusion-Neustart wirken. Bekannte Abhilfen: `importlib.reload(...)` für jedes eigene Modul
  oder die Einträge des Pakets in `stop()` aus `sys.modules` löschen. **Weld Joint macht das seit
  der Schweiß-Version selbst:** `run()` ruft `importlib.reload` für alle eigenen Module auf.
  Änderungen an `WeldJoint.py` selbst brauchen im Zweifel einen Fusion-Neustart.
- **Python 3.14** seit dem Fusion-Release Januar 2026 (vorher 3.12). Nur `.py`-Quellen ausliefern;
  `.pyc` aus anderen Python-Versionen laden nicht.
- Fusions Python enthält **nur die Standardbibliothek**. Fremdpakete als lokale Kopie in den
  Add-in-Ordner legen und relativ importieren (`from .lib import x`), nicht `sys.path` verbiegen.

---

## 4. Python-Eigenheiten der API

- Namensräume: `adsk.core` (Application, UI, Geometrie, Events), `adsk.fusion` (Design, Bodies,
  Features), `adsk.cam` (Fertigung).
- **Event-Handler-Objekte müssen referenziert bleiben** (z. B. globale Liste oder Attribut), sonst
  räumt der Garbage Collector sie weg und das Event feuert nicht mehr. Weld Joint speichert sie als
  `self._…Handler`.
- Typ-Hints (`design: adsk.fusion.Design = app.activeProduct`) sind nur IDE-Hilfe, keine Prüfung.
  Echte Prüfung: `adsk.fusion.BRepFace.cast(obj)` → `None` bei falschem Typ, oder `isinstance`.
- Fusion-Objekte mit `==` vergleichen, **nicht** mit `is`.
- Collections: `for x in coll`, `len(coll)`, `coll[0]`, `coll[-1]`, Slicing; `.count`/`.item(i)`
  gehen auch.
- Rückgabe-„Arrays“ sind `vector`-Objekte → bei Bedarf `list(...)`.
- Out-Parameter kommen als Tuple zurück: `(ok, x, y, z) = point.getData()`.
- **Interne Einheiten: Länge in cm, Winkel in rad.** `ValueInput.createByReal(1.0)` = 1 cm.
  Benutzerangaben als String (`'5 mm'`) über `ValueInput.createByString`.

---

## 5. Objektmodell (die Teile, die Weld Joint nutzt)

```
adsk.core.Application.get()
├── .userInterface                      → UserInterface
│   ├── .commandDefinitions             → addButtonDefinition(...), itemById(...)
│   ├── .workspaces.itemById('FusionSolidEnvironment')
│   │   └── .toolbarPanels.itemById('SolidModifyPanel' | 'SolidScriptsAddinsPanel')
│   │       └── .controls.addCommand(cmdDef, positionId, isBefore) → CommandControl
│   ├── .allToolbarPanels / .toolbars   → zum Aufräumen in stop()
│   ├── .activeSelections               → aktuelle Auswahl (z. B. das zu editierende Feature)
│   ├── .palettes.itemById('TextCommands').writeText(msg)
│   └── .messageBox(msg)
├── .activeProduct                      → adsk.fusion.Design (im DESIGN-Workspace)
│   ├── .activeComponent                → Component
│   │   ├── .features.customFeatures    → CustomFeatures
│   │   ├── .features.baseFeatures      → BaseFeatures
│   │   ├── .features.combineFeatures   → CombineFeatures
│   │   └── .bRepBodies.add(body, baseFeature)
│   ├── .timeline                       → Timeline (.markerPosition, [index])
│   ├── .unitsManager                   → UnitsManager
│   └── .findEntityByToken(token)       → Liste von Entities
└── .pointTolerance                     → geometrische Toleranz (cm)
```

### UnitsManager (vom Plugin genutzt)

| Aufruf | Zweck |
|---|---|
| `defaultLengthUnits` | Benutzer-Längeneinheit (`'mm'`, `'cm'`, `'in'` …) |
| `evaluateExpression(expr, units)` | Ausdruck → Wert in internen Einheiten |
| `formatInternalValue(value, units, showUnits)` | interner Wert → String |
| `formatUnits(units)` | Einheiten-String normalisieren |

### Entity Tokens

- Jede persistente Entity hat `entityToken` (String). `design.findEntityByToken(token)` liefert sie
  wieder – auch nach Neuberechnung. So speichert Weld Joint die gewählten Flächen im Feature.

---

## 6. Commands (Befehle) und UI

### Ablauf

1. In `run()`: `ui.commandDefinitions.addButtonDefinition(id, name, tooltip, resourceFolder)`
   → `CommandDefinition`. `resourceFolder` enthält die Icons (16x16, 32x32, 64x64, 128x128,
   jeweils optional `@2x`).
2. Button in ein Panel: `panel.controls.addCommand(cmdDef, positionId, isBefore)`;
   `control.isPromotedByDefault = True` zeigt den Button direkt in der Leiste.
3. Klick → Fusion erzeugt `Command` und feuert `cmdDef.commandCreated`.
4. Im `commandCreated`-Handler: Inputs anlegen (→ Dialog erscheint) und Handler an die Events des
   `Command` hängen.
5. In `stop()`: Controls und CommandDefinitions per `itemById(id).deleteMe()` entfernen.

### Command-Events

| Event | EventArgs | Wofür |
|---|---|---|
| `commandCreated` (auf CommandDefinition) | `CommandCreatedEventArgs` (`.command`) | Dialog bauen, Handler verbinden |
| `activate` / `deactivate` | `CommandEventArgs` | `activate` kann mehrfach kommen (z. B. nach Orbit). **Selektionen vorbefüllen geht erst hier**, nicht in `commandCreated` |
| `inputChanged` | `InputChangedEventArgs` | Inputs ein-/ausblenden. **Keine Modelländerungen hier** |
| `validateInputs` | `ValidateInputsEventArgs` (`.areInputsValid`, `.inputs`) | OK-Button freigeben/sperren |
| `preSelect` / `select` / `unselect` | `SelectionEventArgs` (`.selection`, `.activeInput`, `.isSelectable`, `.additionalEntities`) | Auswahl filtern |
| `executePreview` | `CommandEventArgs` (`.isValidResult`) | Vorschau. Vorherige Vorschau wird vor jedem Aufruf zurückgenommen. `isValidResult = True` → Vorschau wird bei OK übernommen, `execute` entfällt |
| `execute` | `CommandEventArgs` (`.executeFailed`) | OK gedrückt → Modell ändern |
| `destroy` | `CommandEventArgs` | Letztes Event, immer – Aufräumen |
| Maus/Tastatur | `mouseClick`, `mouseMove`, … `keyDown`, `keyUp` | Interaktion im Viewport |

Weitere `Command`-Methoden, die Weld Joint nutzt: `command.beginStep()` (Zwischenschritt, damit ein
Timeline-Rollback bei Vorschau-Abbruch nicht zurückgenommen wird) und `command.doExecutePreview()`
(Vorschau manuell auslösen).

Alles, was in `execute`/`executePreview` passiert, ist **eine Transaktion** = ein Undo-Schritt.

### Wichtige UI-IDs

| ID | Was |
|---|---|
| `FusionSolidEnvironment` | DESIGN-Workspace |
| `SolidModifyPanel` | Panel ÄNDERN |
| `SolidCreatePanel` | Panel ERSTELLEN |
| `SolidScriptsAddinsPanel` | Panel ADD-INS |
| `FusionCombineCommand` | Befehl „Kombinieren“ (Weld Joint hängt sich dahinter) |

`fusion_util.dumpMenus()` im Plugin listet alle IDs der aktuellen Fusion-Version auf.

---

## 7. Command Inputs (Dialog-Elemente)

Alle Methoden hängen an `command.commandInputs` (`CommandInputs`). Signaturen aus der offiziellen
Referenz:

| Methode | Signatur | Ergebnis |
|---|---|---|
| `addSelectionInput` | `(id, name, commandPrompt)` | `SelectionCommandInput` |
| `addValueInput` | `(id, name, unitType, initialValue: ValueInput)` | `ValueCommandInput` |
| `addDistanceValueCommandInput` | `(id, name, initialValue: ValueInput)` | `DistanceValueCommandInput` (mit Manipulator im Viewport, `setManipulator(...)`) |
| `addAngleValueCommandInput` | `(id, name, initialValue)` | `AngleValueCommandInput` |
| `addIntegerSpinnerCommandInput` | `(id, name, min, max, spinStep, initialValue)` | `IntegerSpinnerCommandInput` |
| `addFloatSpinnerCommandInput` | `(id, name, unitType, min, max, spinStep, initialValue)` – min/max/initial in internen Einheiten | `FloatSpinnerCommandInput` |
| `addBoolValueInput` | `(id, name, isCheckBox, resourceFolder='', initialValue=False)` | `BoolValueCommandInput` |
| `addDropDownCommandInput` | `(id, name, dropDownStyle)`; Einträge über `.listItems.add(name, isSelected)` | `DropDownCommandInput` |
| `addStringValueInput` | `(id, name, initialValue)` | `StringValueCommandInput` |
| `addTextBoxCommandInput` | `(id, name, formattedText, numRows, isReadOnly)` – **retired**, funktioniert aber weiter | `TextBoxCommandInput` |
| `addSimpleTextBoxCommandInput` / `addFormattedTextBoxCommandInput` | Nachfolger (einfach editierbar / HTML, nicht editierbar) | |
| `addGroupCommandInput`, `addTabCommandInput`, `addTableCommandInput`, `addButtonRowCommandInput`, `addRadioButtonGroupCommandInput`, `addSeparatorCommandInput`, `addImageCommandInput`, `addFloat/IntegerSlider(List)CommandInput`, `addDirectionCommandInput`, `addTriadCommandInput`, `addBrowserCommandInput` | Gruppierung, Tabs, Tabellen, Slider, Richtung … | |
| `itemById(id)` / `item(i)` | Input wiederfinden | |

Gemeinsame Properties: `.id`, `.name`, `.tooltip`, `.isVisible`, `.isEnabled`, `.isFullWidth`.
Werte-Inputs: `.value` (intern), `.expression` (String inkl. Einheit), `.isValidExpression`,
`.minimumValue`, `.isMinimumLimited`, `.isMinimumInclusive` (analog Maximum).

### SelectionCommandInput

- `addSelectionFilter(name)` – fügt Filter hinzu (mehrere = ODER).
- `setSelectionLimits(min, max=0)` – Weld Joint: mindestens 2 Flächen.
- `addSelection(entity)`, `clearSelection()`, `selectionCount`, `selection(i).entity`.

### Selection-Filter-Strings (vollständig laut Doku)

`Bodies`, `SolidBodies`, `SurfaceBodies`, `MeshBodies`, `Faces`, `SolidFaces`, `SurfaceFaces`,
`PlanarFaces`, `CylindricalFaces`, `ConicalFaces`, `SphericalFaces`, `ToroidalFaces`,
`SplineFaces`, `Edges`, `LinearEdges`, `CircularEdges`, `EllipticalEdges`, `TangentEdges`,
`NonTangentEdges`, `Vertices`, `RootComponents`, `Occurrences`, `Sketches`, `SketchConstraints`,
`Profiles`, `Texts`, `SketchCurves`, `SketchLines`, `SketchCircles`, `SketchPoints`,
`ConstructionPoints`, `ConstructionLines`, `ConstructionPlanes`, `Features`, `Canvases`, `Decals`,
`JointOrigins`, `Joints`.

---

## 8. Custom Features (Kern des Plugins)

Ein Custom Feature erscheint als **ein Eintrag in der Zeitleiste** und gruppiert darunterliegende
Standard-Features. Weld Joint nutzt die Variante *mit eigenem Compute* (Neuberechnung durch Python).

> ⚠️ Die Autodesk-Doku führt Custom Features weiterhin als **Preview**-API (kann sich ändern).

### Bausteine

| API | Zweck |
|---|---|
| `adsk.fusion.CustomFeatureDefinition.create(id, name, iconFolder)` | Feature-Typ registrieren (in `run`). `id` global eindeutig (Firmenpräfix). Existiert die ID schon, wird die **vorhandene** Definition zurückgegeben |
| `definition.editCommandId` | Command, der bei „Feature bearbeiten“ startet |
| `definition.customFeatureCompute.add(handler)` | Neuberechnung, wenn sich Abhängigkeiten/Parameter ändern |
| `definition.defaultName`, `.iconFolder`, `.id` | |
| `customFeatures.createInput(definition)` | → `CustomFeatureInput` |
| `input.addCustomParameter(id, name, valueInput, units, isVisible)` | Parameter (erscheint im Parameter-Dialog, änderbar → löst Compute aus) |
| `input.addDependency(id, entity)` | Abhängigkeit (ändert sich die Entity → Compute) |
| `input.setStartAndEndFeatures(start, end)` | gruppierte Features |
| `customFeatures.add(input)` | → `CustomFeature` |

### CustomFeature-Objekt

`parameters` (`.itemById(id).expression/.value`), `dependencies` (`.add(id, entity)`,
`.itemById(id).entity`, `.deleteAll()`), `customNamedValues`, `features` (gruppierte Features),
`setStartAndEndFeatures(start, end)`, `timelineObject` (`.rollTo(rollBefore)`), `bodies`, `faces`,
`healthState`, `errorOrWarningMessage`, `entityToken`, `isSuppressed`, `deleteMe()`.

### CustomNamedValues (freie String-Speicher im Feature)

`addOrSetValue(id, value)`, `value(id)`, `isExistingValue(id)`, `remove(id)`, `idByIndex(i)`,
`count`. Weld Joint speichert hier die Face-Tokens (`'faces'`).

### customFeatureCompute-Event

- Args: `CustomFeatureEventArgs` mit `.customFeature` und `.computeStatus`
  (Fehler melden: `computeStatus.statusMessages.addError(...)`, nur vordefinierte Meldungen).
- Das Modell ist auf den Zustand **vor** dem Feature zurückgerollt.
- **Erlaubt im Compute sind nur:** Bodies in Base Features ändern (`updateBody`), Sketch-Inhalte,
  eigene Parameter. Andere Änderungen (neue Features anlegen/löschen usw.) schlagen
  wahrscheinlich fehl. → Darum ruft Weld Joint im Compute `allowFeatureCreationAndDeletion=False`.
- Body **aktualisieren statt löschen+neu**, damit nachfolgende Referenzen (Fasen, Bohrungen …)
  stabil bleiben.

### Edit-Ablauf (Empfehlung der Doku, so auch in Weld Joint umgesetzt)

1. `commandCreated`: Feature aus `ui.activeSelections[0].entity`, Inputs mit gespeicherten Werten
   anlegen.
2. `activate`: Timeline-Position merken, `timelineObject.rollTo(True)`, `command.beginStep()`,
   Selektionen jetzt befüllen.
3. `execute`: Parameter/Abhängigkeiten aktualisieren, neu berechnen, Timeline zurück
   (`rollTo(False)`).

### Einschränkungen

- Man kann die Timeline nicht **in** ein Custom Feature rollen.
- Custom Compute funktioniert nur mit Gruppen aus Base Features, Sketches und Combine Features.
- Fehlt das Add-in beim Öffnen einer Datei: generisches Icon + Warnung, **keine** Neuberechnung.
- Für stabile IDs bei temporären Bodies: Bodies konsistent aufbauen
  (`BRepBodyDefinition` → `associativeID` setzen).

---

## 9. Base Features und Combine Features

### BaseFeature (nicht-parametrischer Container für fertige Bodies)

| Aufruf | Zweck |
|---|---|
| `baseFeatures.add()` | neues Base Feature |
| `startEdit()` / `finishEdit()` | Edit-Modus; nur dann sind `bodies` die Quell-Bodies |
| `component.bRepBodies.add(tempBody, baseFeature)` | Body hineinlegen (im Edit-Modus) |
| `updateBody(sourceBody, newTempBody)` → bool | Geometrie eines vorhandenen Quell-Bodys ersetzen (Referenzen bleiben) |
| `sourceBodies`, `bodies`, `timelineObject`, `deleteMe()` | |

### CombineFeatures

- `combineFeatures.createInput(targetBody, toolBodies: ObjectCollection)` → `CombineFeatureInput`
- `input.operation = adsk.fusion.FeatureOperations.<…>` –
  `JoinFeatureOperation`, `CutFeatureOperation`, `IntersectFeatureOperation`
- `input.isKeepToolBodies = True/False`
- `combineFeatures.add(input)` → `CombineFeature` (`.targetBody` änderbar)

---

## 10. Temporäre B-Rep-Geometrie (TemporaryBRepManager)

`tempBrepMgr = adsk.fusion.TemporaryBRepManager.get()` – rechnet mit Bodies **außerhalb** des
Dokuments (schnell, keine Zeitleiste). Ergebnis wird später per BaseFeature ins Modell gebracht.

| Methode | Zweck |
|---|---|
| `booleanOperation(target, tool, BooleanTypes)` | Bool-Op, **ändert `target` in-place** |
| `copy(body/face/edge)` | temporäre Kopie |
| `transform(body, Matrix3D)` | in-place transformieren |
| `createBox(OrientedBoundingBox3D)` | Quader |
| `createCylinderOrCone(...)`, `createEllipticalCylinderOrCone(...)`, `createSphere(center, r)`, `createTorus(...)` | Grundkörper |
| `createWireFromCurves(curves, allowSelfIntersections)` → `(wireBody, edgeMap)` | Draht aus Kurven |
| `createFaceFromPlanarWires([wireBodies])` | ebene Fläche (weitere Drähte = Löcher) |
| `createRuledSurface(wireA, wireB)` | Regelfläche zwischen zwei Drähten |
| `imprintOverlapBodies(b1, b2, imprintCoincidentEdges)` | Überlappungen aufprägen; Weld Joint nutzt Index `[3]` = überlappende Flächen |
| `planeIntersection(body, plane)` | Schnitt mit Ebene → Draht |
| `deleteFaces(...)`, `createHelixWire(...)`, `createSilhouetteCurves(...)`, `createProjectedBodyOutline(...)` | |
| `createFromFile(...)` / `exportToFile(bodies, path)` | Import/Export (gut zum Debuggen) |

`adsk.fusion.BooleanTypes`: `DifferenceBooleanType`, `IntersectionBooleanType`, `UnionBooleanType`.

`BRepBodyDefinition` (in `fusion_brep_util.definitionOfBody`): Bodies aus Topologie neu aufbauen
(`lumpDefinitions → shellDefinitions → faceDefinitions → loopDefinitions → bRepCoEdgeDefinitions`),
`.createBody()`; `doFullHealing` steuert Reparatur.

### B-Rep-Topologie

`BRepBody → lumps → shells → faces → loops → coEdges → edge → vertices`

- `face.geometry` liefert eine **Kopie** (z. B. `Plane` mit `.normal`, `.origin`) – nach Änderungen
  neu abrufen.
- `face.isParamReversed`: Flächen-Normale der Geometrie ist gegenüber der Body-Normale umgedreht.
  Weld Joint nutzt das, um die nach innen zeigende Normale zu bestimmen.
- `face.evaluator.getNormalAtPoint(...)` liefert immer die **nach außen** zeigende Normale (B-Rep-
  Evaluator ist zuverlässiger als der Geometrie-Evaluator).
- `face.body`, `face.edges`, `edge.faces`, `body.isSolid`, `body.revisionId`, `body.boundingBox`,
  `face.pointOnFace`.

### Geometrie-Klassen in `adsk.core` (vom Plugin genutzt)

`Point3D.create(x,y,z)`, `Vector3D.create(...)` (`crossProduct`, `scaleBy`, `add`, `length`),
`Matrix3D.create()` (`setToAlignCoordinateSystems`, `setCell`, `translation`, `invert`, `copy`),
`Plane` (`normal`, `intersectWithPlane`, `intersectWithLine`, `isParallelToPlane`, `isCoPlanarTo`),
`InfiniteLine3D.create(origin, direction)` (`intersectWithCurve`), `Line3D.create(p1, p2)`,
`Arc3D.createByCenter(center, normal, referenceVector, radius, startAngle, endAngle)`,
`Circle3D.createByCenter(center, normal, radius)`,
`OrientedBoundingBox3D.create(center, lengthDir, widthDir, length, width, height)`,
`ObjectCollection.create()`, `SurfaceTypes.PlaneSurfaceType`.

---

## 11. Stolperfallen und Regeln (Kurzliste)

1. Handler-Objekte referenziert halten.
2. Interne Einheit cm; Benutzerwerte als Ausdruck-String speichern (`expression`), nicht als Zahl.
3. Selektionen erst im `activate` vorbefüllen.
4. Im `inputChanged` nichts am Modell ändern.
5. Im Compute nur Base-Feature-Bodies aktualisieren, keine Features anlegen/löschen.
6. Bodies aktualisieren (`updateBody`) statt löschen, damit Folgefeatures nicht brechen.
7. Bei Timeline-Manipulation (`rollTo`) die ursprüngliche Markerposition immer wiederherstellen.
8. In `stop()` alle Buttons/Definitions entfernen, sonst gibt es beim Neustart doppelte IDs.
9. Fehler in Handlern abfangen und loggen (Weld Joint: `newEventHandler` + `handleException`).
10. Lange Rechnungen in `executePreview` vermeiden – läuft bei jeder Eingabeänderung.
11. Ab Januar 2026: **Intent-Driven Design** (Design-Typen *hybrid*, *part*, *assembly*). In
    *hybrid* (bisheriges Verhalten) laufen Apps unverändert; in *part*/*assembly* kann sich
    UI/Verhalten ändern. ⚠️ Für Weld Joint in diesen Typen noch nicht getestet.
