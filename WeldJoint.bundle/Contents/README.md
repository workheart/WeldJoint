# Weld Joint

An [Autodesk Fusion](https://www.autodesk.com/products/fusion-360/overview) Add-In for creating
**weld tabs** and **finger joints** between plates that are cut by laser or waterjet and then welded.

By [Kabelfrikkler](https://github.com/workheart). Based on
[Box Joint](https://github.com/EvilHacker/BoxJoint) by Mark Suska (MIT License).

## Features

* **Three modes**
	* **Fingers**: alternating fingers along the whole edge (the original Box Joint behavior).
	* **Tabs: Spacing**: tabs of a fixed width, spread evenly with a maximum gap.
	* **Tabs: Points**: one tab at each selected sketch point. Dimension the points in the sketch and
	  the tabs follow when the sketch changes.
* **Clearances for welding**, all per side:
	* **Tab Setback**: tabs end below the outside face of the other plate, which leaves room for the weld.
	* **Slot Clearance**: slots are longer than the tabs, along the edge.
	* **Hole Clearance**: slots are wider than the plate thickness, only for closed holes inside a face
	  (not for notches at a corner).
* **Corner Margin**: moves all fingers or tabs away from the corners.
* Works for any number of plates at once, for plates meeting at any angle, and for tabs into the
  middle of a face (T-joints).
* **Editable feature**: the joint is a single feature in the timeline. Edit it like any built-in
  feature. It is recomputed when the plates (or the tab sketch) earlier in the timeline change.
* The dialog **remembers the last used settings**, also across documents.
* Tooltips for every input.

Material thickness does not need to be entered: it is measured from the plates.

## Installation

Copy the folder `WeldJoint.bundle` (containing `PackageContents.xml` and `Contents`) to:

* `%appdata%\Autodesk\ApplicationPlugins` (Windows)
* `~/Library/Application Support/Autodesk/ApplicationPlugins` (macOS)

Then start Fusion. The Add-In loads automatically.

## Usage

The Add-In is in the `DESIGN` workspace, `SOLID` tab, `MODIFY` panel: **Weld Joint**.

1. Model the plates with simple butt joints: plates touch each other with a planar face.
2. Open **Weld Joint** and select the **outside face** of each plate to join.
3. Choose the **Mode** and set the values.
	* For **Tabs: Points**, first draw a sketch on an outside face with points on the edge (or within
	  the plate thickness) where the tabs should be. Then click into **Tab Points** and select them.
4. Click **OK**.

A joint is created wherever a selected plate butts against another selected plate. The butting plate
gets the tabs, the other plate gets the slots.

To change a joint, select it in the timeline and choose **Edit Feature**.

To reset the remembered settings, delete `Contents/last_settings.json`.

### Tooltip images

Tooltip images are loaded from `Contents/Resources/ToolClips/<input id>.png` (at most 300 px wide).
The list of file names is in `Contents/Resources/ToolClips/LIESMICH.txt`.

## License

MIT, see [LICENSE](LICENSE).
