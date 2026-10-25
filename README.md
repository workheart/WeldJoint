# Weld Joint

An [Autodesk Fusion](https://www.autodesk.com/products/fusion-360/overview) Add-In for creating
**weld tabs** and **finger joints** between plates that are cut by laser or waterjet and then welded.
The joint is a single, editable feature in the timeline.

By [Kabelfrikkler](https://github.com/workheart).

## Thanks

This Add-In is based on [Box Joint](https://github.com/EvilHacker/BoxJoint) by **Mark Suska**.
Many thanks to him for sharing it under the MIT License: the joint detection, the timeline handling and
the whole custom feature framework come from his work. Weld Joint adds the welding features on top.

The welding features were coded with [Claude Code](https://claude.com/claude-code).

## Installation

1. Download this repository (**Code** → **Download ZIP**) and extract it.
2. Rename the extracted folder to `WeldJoint`. It must directly contain `WeldJoint.manifest` and `WeldJoint.py`.
3. In Fusion open **UTILITIES** → **ADD-INS** → **Scripts and Add-Ins**, click **+** →
   **Script or add-in from device** and select the `WeldJoint` folder (the folder with the manifest,
   not a folder above it).

   Or copy the folder to the Fusion Add-Ins folder, where Fusion finds it by itself:
   * Windows: `%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns`
   * macOS: `~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns`
4. Start **WeldJoint** in the list. Turn on **Run on Startup** to load it with Fusion.

To uninstall, stop the Add-In in **Scripts and Add-Ins**, then unlink it or delete the folder.

## Usage

1. Model the plates with simple butt joints: plates touch each other with a planar face.
2. Open **Weld Joint** (**DESIGN** workspace, **SOLID** tab, **MODIFY** panel).
3. Select the **outside face** of each plate to join.
4. Choose the **Mode** and set the values, then click **OK**.

A joint is created wherever a selected plate butts against another selected plate, at any angle.
The butting plate gets the tabs, the other plate gets the slots. Material thickness is measured from
the plates, it does not need to be entered.

To change a joint, select it in the timeline and choose **Edit Feature**.
The joint is recomputed when the plates (or the tab sketch) earlier in the timeline change.

The dialog remembers the last used settings, also across documents.
To reset them, delete `last_settings.json` in the Add-In folder.

## Modes

| Mode | What it does |
|---|---|
| **Fingers** | Alternating fingers along the whole edge (the original Box Joint behavior). |
| **Tabs: Spacing** | Tabs of a fixed width, spread evenly. All gaps, also those to the ends of the edge, are equal and never larger than *Tab Spacing*. |
| **Tabs: Points** | One tab at each selected sketch point, centered along the edge. Draw the points in a sketch on an outside face, on the edge or within the plate thickness. Dimension them in the sketch: the tabs follow when the sketch changes. |

## Inputs

| Input | Meaning |
|---|---|
| **Faces** | Outside faces of the plates to join. |
| **Mode** | See above. |
| **Tab Points** | Sketch or construction points that place the tabs (mode *Tabs: Points*). |
| **Min / Max Fingers** | Number of fingers of both plates together (odd). |
| **Min / Max Finger Width** | Allowed finger width. |
| **Finger Ratio** | Width share of the fingers on the butting plate. 0.5 makes all fingers equally wide. |
| **Tab Width** | Width of each tab along the edge. |
| **Tab Spacing** | Largest gap between two tabs. |
| **Corner Margin** | Moves all fingers or tabs inward by this distance, from both ends of the edge. |
| **Tab Setback** | The tabs end this far below the outside face of the other plate, which leaves room for the weld. |
| **Slot Clearance** | Play along the edge, per side: each slot is longer than its tab by this value on both sides. |
| **Hole Clearance** | Play across the edge, per side: each slot is wider than the plate thickness by this value on both sides. Only for closed holes inside a face, not for notches at a corner. |

Every input has a tooltip. Tooltip images are loaded from `Resources/ToolClips/<input id>.png`
(at most 300 px wide). The file names are listed in `Resources/ToolClips/LIESMICH.txt`.

## Support

[https://github.com/workheart](https://github.com/workheart)

## License

MIT, see [LICENSE](LICENSE).
