"""
Camera Inferno Tweaker
=======================
- Camera list: only cameras with Camera Inferno
- Character dropdown: "All Characters" or individual rig
- All Characters = shared position/size/colour for all rigs
- Individual = per-rig overrides, stacked automatically
- Name + timecode on one line per rig
- Collapsible position/size/colour section

Run from Maya Script Editor (Python tab).
"""

import maya.cmds as cmds
import re

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

C_BG     = (0.18, 0.18, 0.18)
C_HEADER = (0.13, 0.13, 0.13)
C_ROW    = (0.22, 0.22, 0.22)
C_BTN    = (0.30, 0.30, 0.30)
C_STATUS = (0.15, 0.15, 0.15)
C_OK     = (0.13, 0.28, 0.13)
C_ERR    = (0.28, 0.10, 0.10)
C_WARN   = (0.25, 0.18, 0.05)

W      = 480
LBL_W  = 110
MARGIN = 8
ROW_H  = 26

WINDOW_ID = "camInfernoTweakerWin"

DEFAULT_X    = -0.952
DEFAULT_Y    = -0.720
DEFAULT_SIZE =  2.0
DEFAULT_GAP  =  0.029
DEFAULT_COL  = (1.0, 0.8, 0.0)

DEFAULT_SHAPES = {"frontShape", "sideShape", "topShape", "perspShape"}

ALL_CHARS = "All Characters"


# ---------------------------------------------------------------------------
# Scene queries
# ---------------------------------------------------------------------------

def _all_scene_cameras():
    result = []
    for shape in cmds.ls(type="camera") or []:
        if shape in DEFAULT_SHAPES:
            continue
        xf = cmds.listRelatives(shape, parent=True, fullPath=False)[0]
        result.append((xf, shape))
    return sorted(result, key=lambda p: p[0].lower())


def _inferno_cameras():
    return [(xf, sh) for xf, sh in _all_scene_cameras()
            if _find_inferno(xf)[0]]


def _find_inferno(cam_xf):
    try:
        desc = cmds.listRelatives(cam_xf, allDescendents=True, fullPath=True) or []
        for fp in desc:
            short = fp.split("|")[-1]
            try:
                if cmds.nodeType(short) == "dcCameraInferno":
                    parent_fp = cmds.listRelatives(fp, parent=True, fullPath=True)
                    parent    = parent_fp[0].split("|")[-1] if parent_fp else None
                    return short, parent
            except Exception:
                pass
    except Exception:
        pass
    return None, None


def _get_rigs():
    """Return [(namespace, tc_jnt), ...] sorted by namespace."""
    joints = sorted([j for j in (cmds.ls(type="joint") or [])
                     if j.endswith(":timecode_jnt") or j == "timecode_jnt"])
    return [(j.rsplit(":", 1)[0] if ":" in j else "", j) for j in joints]


# ---------------------------------------------------------------------------
# Settings cache: { jnt -> {x, y, size, col} }  for per-rig overrides
# Also a separate cache for per-camera global settings
# ---------------------------------------------------------------------------

# Per-rig settings cache (used in individual mode)
RIG_SETTINGS = {}

# Per-camera global settings cache
CAM_SETTINGS = {}


def _default_settings():
    return dict(x=DEFAULT_X, y=DEFAULT_Y, size=DEFAULT_SIZE,
                gap=DEFAULT_GAP, col=DEFAULT_COL)


def _read_settings_from_node(node):
    s = _default_settings()
    try:
        count = cmds.getAttr(f"{node}.field", size=True) or 0
        if count >= 1:
            pos0 = cmds.getAttr(f"{node}.field[0].fieldPositionA")[0]
            sz   = cmds.getAttr(f"{node}.field[0].fieldTextSize")
            col  = cmds.getAttr(f"{node}.field[0].fieldTextColor")[0]
            s["x"]    = pos0[0]
            s["y"]    = pos0[1]
            s["size"] = sz
            s["col"]  = (col[0], col[1], col[2])
        if count >= 2:
            pos1     = cmds.getAttr(f"{node}.field[1].fieldPositionA")[0]
            s["gap"] = round(pos0[1] - pos1[1], 4)
    except Exception:
        pass
    return s


# ---------------------------------------------------------------------------
# Read / write slider values
# ---------------------------------------------------------------------------

def _read_sliders():
    return dict(
        x    = cmds.floatSliderGrp("ci_posX",  q=True, value=True),
        y    = cmds.floatSliderGrp("ci_posY",  q=True, value=True),
        size = cmds.floatSliderGrp("ci_size",  q=True, value=True),
        gap  = cmds.floatSliderGrp("ci_gap",   q=True, value=True),
        col  = cmds.colorSliderGrp("ci_color", q=True, rgbValue=True),
    )


def _write_sliders(s):
    if not cmds.floatSliderGrp("ci_posX", exists=True):
        return
    cmds.floatSliderGrp("ci_posX",  e=True, value=s["x"])
    cmds.floatSliderGrp("ci_posY",  e=True, value=s["y"])
    cmds.floatSliderGrp("ci_size",  e=True, value=s["size"])
    cmds.floatSliderGrp("ci_gap",   e=True, value=s["gap"])
    cmds.colorSliderGrp("ci_color", e=True, rgbValue=s["col"])


def _label_for_rig(jnt):
    """Label override text field value, or full namespace as fallback."""
    safe = re.sub(r"[^A-Za-z0-9]", "_", jnt)
    ctrl = f"ci_lbl_{safe}"
    if cmds.textField(ctrl, exists=True):
        val = cmds.textField(ctrl, q=True, text=True).strip()
        if val:
            return val
    return jnt.rsplit(":", 1)[0] if ":" in jnt else jnt


# ---------------------------------------------------------------------------
# Field setup
# ---------------------------------------------------------------------------

def _setup_fields(node, rigs, glob):
    """
    Each rig = one field: "Label   HH:MM:SS:FF"
    In All Characters mode all use glob settings, stacked by gap.
    In individual mode each rig uses its cached RIG_SETTINGS.
    """
    selected = UI_STATE.get("char_sel", ALL_CHARS)

    for i, (ns, tc_jnt) in enumerate(rigs):
        label = _label_for_rig(tc_jnt)
        sep  = cmds.textField("ci_separator", q=True, text=True)                if cmds.textField("ci_separator", exists=True) else " "
        text = f"{label}{sep}{{a:02.0f}}:{{b:02.0f}}:{{c:02.0f}}:{{d:02.0f}}"

        if selected == ALL_CHARS:
            x    = glob["x"]
            y    = glob["y"] - i * glob["gap"] * 3
            size = glob["size"]
            col  = glob["col"]
        else:
            # Per-rig settings — use cached or defaults stacked by index
            rs   = RIG_SETTINGS.get(tc_jnt, _default_settings())
            x    = rs["x"]
            y    = rs["y"]
            size = rs["size"]
            col  = rs["col"]

        r, g, b = col
        fi = i

        cmds.setAttr(f"{node}.field[{fi}].fieldEnable",    1)
        cmds.setAttr(f"{node}.field[{fi}].fieldType",      1)
        cmds.setAttr(f"{node}.field[{fi}].fieldTextValue", text, type="string")
        cmds.setAttr(f"{node}.field[{fi}].fieldTextSize",  size)
        cmds.setAttr(f"{node}.field[{fi}].fieldTextAlign", 0)
        cmds.setAttr(f"{node}.field[{fi}].fieldTextColor", r, g, b)
        cmds.setAttr(f"{node}.field[{fi}].fieldTextAlpha", 1.0)
        cmds.setAttr(f"{node}.field[{fi}].fieldPositionA", x, y, 0.0)

        for src_a, dst_s in [
            ("TCHour",   "fieldValueA"),
            ("TCMinute", "fieldValueB"),
            ("TCSecond", "fieldValueC"),
            ("TCFrame",  "fieldValueD"),
        ]:
            src = f"{tc_jnt}.{src_a}"
            dst = f"{node}.field[{fi}].{dst_s}"
            if not cmds.isConnected(src, dst):
                cmds.connectAttr(src, dst, force=True)

    # Disable leftover fields
    existing = cmds.getAttr(f"{node}.field", size=True) or 0
    for fi in range(len(rigs), existing):
        try:
            cmds.setAttr(f"{node}.field[{fi}].fieldEnable", 0)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Add Camera Inferno
# ---------------------------------------------------------------------------

def _add_inferno(cam_xf):
    node, _ = _find_inferno(cam_xf)
    if node:
        return node
    if not cmds.pluginInfo("dcCameraInferno", q=True, loaded=True):
        try:
            cmds.loadPlugin("dcCameraInferno")
        except Exception as e:
            cmds.warning(f"[Cam Inferno] Plugin load failed: {e}")
            return None
    try:
        short = cam_xf.split("|")[-1]
        safe  = re.sub(r"[^A-Za-z0-9]", "_", short)
        tfm   = cmds.createNode("transform", name=f"cameraInferno_{safe}",
                                parent=cam_xf)
        node  = cmds.createNode("dcCameraInferno", parent=tfm)
        cmds.setAttr(f"{tfm}.template", 1)
        cmds.setAttr(f"{node}.maskAspectRatio", 1.7777)
        return node
    except Exception as e:
        cmds.warning(f"[Cam Inferno] Could not create: {e}")
        return None


# ---------------------------------------------------------------------------
# UI state
# ---------------------------------------------------------------------------

UI_STATE = {
    "cameras":  [],
    "rigs":     [],
    "char_sel": ALL_CHARS,   # ALL_CHARS or a specific tc_jnt
}


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _selected_cam():
    cams = UI_STATE.get("cameras", [])
    if not cams:
        return None
    try:
        idx = cmds.optionMenu("ci_camMenu", q=True, select=True) - 1
        return cams[idx][0]
    except Exception:
        return None


def _pilot_viewport(cam_xf):
    try:
        cmds.lookThru(cam_xf)
    except Exception:
        pass


def _apply(*_):
    # Guard against being called before UI is fully built
    if not cmds.floatSliderGrp("ci_posX", exists=True):
        return
    cam_xf = _selected_cam()
    if not cam_xf:
        return _set_status("No camera selected.", "err")
    node, _ = _find_inferno(cam_xf)
    if not node:
        return _set_status("No burn-in on this camera.", "err")
    rigs = UI_STATE.get("rigs", [])
    if not rigs:
        return _set_status("No timecode joints found.", "err")

    glob = _read_sliders()

    # Cache current slider values
    selected = UI_STATE.get("char_sel", ALL_CHARS)
    if selected == ALL_CHARS:
        CAM_SETTINGS[cam_xf] = glob
    else:
        RIG_SETTINGS[selected] = glob

    _setup_fields(node, rigs, glob)
    _update_cam_status(cam_xf)
    _set_status(f"Applied  |  {cam_xf}  |  {len(rigs)} rig(s).", "ok")


def _on_char_change(*_):
    """Character dropdown changed — load that rig's cached settings into sliders."""
    sel_label = cmds.optionMenu("ci_charMenu", q=True, value=True)

    if sel_label == ALL_CHARS:
        UI_STATE["char_sel"] = ALL_CHARS
        cam_xf = _selected_cam()
        s = CAM_SETTINGS.get(cam_xf, _default_settings()) if cam_xf else _default_settings()
    else:
        # Find the tc_jnt and its index for stacking
        rigs = UI_STATE.get("rigs", [])
        jnt  = next((j for ns, j in rigs if ns == sel_label), None)
        if not jnt:
            return
        idx = next((i for i,(ns,j) in enumerate(rigs) if j == jnt), 0)
        UI_STATE["char_sel"] = jnt

        if jnt in RIG_SETTINGS:
            # Already has cached individual settings — use them
            s = RIG_SETTINGS[jnt]
        else:
            # Seed from current global settings, stacking Y by index
            glob = _read_sliders()
            s = dict(
                x    = glob["x"],
                y    = glob["y"] - idx * glob["gap"] * 3,
                size = glob["size"],
                gap  = glob["gap"],
                col  = glob["col"],
            )
            RIG_SETTINGS[jnt] = s

    _write_sliders(s)


def _on_cam_change(*_):
    cam_xf = _selected_cam()
    if not cam_xf:
        return
    _pilot_viewport(cam_xf)
    node, _ = _find_inferno(cam_xf)
    s = _read_settings_from_node(node) if node else _default_settings()
    CAM_SETTINGS.setdefault(cam_xf, s)
    # Load appropriate settings for current char selection
    selected = UI_STATE.get("char_sel", ALL_CHARS)
    if selected == ALL_CHARS:
        _write_sliders(CAM_SETTINGS.get(cam_xf, s))
    else:
        _write_sliders(RIG_SETTINGS.get(selected, _default_settings()))
    _update_cam_status(cam_xf)


def _update_cam_status(cam_xf):
    if not cmds.text("ci_camStatus", exists=True):
        return
    node, _ = _find_inferno(cam_xf)
    if node:
        vis   = cmds.getAttr(f"{node}.visibility")
        label = f"  {cam_xf}  |  {'visible' if vis else 'hidden'}"
        cmds.text("ci_camStatus", e=True, label=label, backgroundColor=C_OK)
    else:
        cmds.text("ci_camStatus", e=True,
                  label=f"  {cam_xf}  |  no burn-in",
                  backgroundColor=C_WARN)


def _rebuild_cam_menu():
    cams = _inferno_cameras()
    UI_STATE["cameras"] = cams
    for item in (cmds.optionMenu("ci_camMenu", q=True, itemListLong=True) or []):
        cmds.deleteUI(item)
    if cams:
        for xf, _ in cams:
            cmds.menuItem(label=xf, parent="ci_camMenu")
        _on_cam_change()
    else:
        cmds.menuItem(label="-- none --", parent="ci_camMenu")
        if cmds.text("ci_camStatus", exists=True):
            cmds.text("ci_camStatus", e=True,
                      label="  No cameras with Camera Inferno.",
                      backgroundColor=C_WARN)
    # Restore label override rows — they get wiped when UI rebuilds
    _rebuild_label_col()


def _rebuild_char_menu():
    """Repopulate the character dropdown with All + each rig namespace."""
    if not cmds.optionMenu("ci_charMenu", exists=True):
        return
    rigs = UI_STATE.get("rigs", [])
    for item in (cmds.optionMenu("ci_charMenu", q=True, itemListLong=True) or []):
        cmds.deleteUI(item)
    cmds.menuItem(label=ALL_CHARS, parent="ci_charMenu")
    for ns, jnt in rigs:
        cmds.menuItem(label=ns or jnt, parent="ci_charMenu")
    UI_STATE["char_sel"] = ALL_CHARS
    cmds.optionMenu("ci_charMenu", e=True, value=ALL_CHARS)

    # Update the label override column
    _rebuild_label_col()


def _rebuild_label_col():
    """One label-override row per rig in ci_labelCol.
    Preserves any existing label values the user has typed."""
    if not cmds.columnLayout("ci_labelCol", exists=True):
        return

    # Snapshot existing label values before wiping
    rigs = UI_STATE.get("rigs", [])
    saved = {}
    for ns, jnt in rigs:
        safe = re.sub(r"[^A-Za-z0-9]", "_", jnt)
        ctrl = f"ci_lbl_{safe}"
        if cmds.textField(ctrl, exists=True):
            saved[jnt] = cmds.textField(ctrl, q=True, text=True)

    for c in (cmds.columnLayout("ci_labelCol", q=True, childArray=True) or []):
        try:
            cmds.deleteUI(c)
        except Exception:
            pass

    if not rigs:
        cmds.text(label="  No rigs found.", align="left",
                  backgroundColor=C_BG, parent="ci_labelCol")
        return

    for ns, jnt in rigs:
        safe    = re.sub(r"[^A-Za-z0-9]", "_", jnt)
        ctrl    = f"ci_lbl_{safe}"
        default = ns or jnt
        # Restore previously typed value if it exists
        val     = saved.get(jnt, default)
        cmds.rowLayout(
            numberOfColumns=2,
            columnWidth2=(LBL_W + 20, W - LBL_W - 20 - MARGIN * 2),
            columnAttach=[(1,"left",MARGIN),(2,"both",4)],
            height=ROW_H, backgroundColor=C_ROW,
            parent="ci_labelCol",
        )
        cmds.text(label=default, align="left",
                  font="smallBoldLabelFont", backgroundColor=C_ROW)
        cmds.textField(ctrl,
                       text=val,
                       backgroundColor=(0.20, 0.20, 0.20),
                       changeCommand=_apply)
        cmds.setParent("..")
        cmds.separator(height=2, style="none", parent="ci_labelCol")

    # Always return to root so nothing accidentally parents inside ci_labelCol
    if cmds.columnLayout("ci_rootCol", exists=True):
        cmds.setParent("ci_rootCol")


def _refresh_rigs(*_):
    rigs = _get_rigs()
    UI_STATE["rigs"] = rigs
    _rebuild_char_menu()
    _rebuild_label_col()   # always explicitly rebuild, preserving typed values
    rig_label = f"  {', '.join(ns or jnt for ns,jnt in rigs)}" if rigs \
                else "  ⚠  No timecode joints found"
    rig_bg = C_OK if rigs else C_ERR
    if cmds.text("ci_rigLabel", exists=True):
        cmds.text("ci_rigLabel", e=True, label=rig_label, backgroundColor=rig_bg)
    _set_status(f"{len(rigs)} rig(s) found.", "ok" if rigs else "err")
    _apply()


def _add(*_):
    all_cams = [xf for xf, _ in _all_scene_cameras()]
    if not all_cams:
        return _set_status("No cameras in scene.", "err")
    result = cmds.confirmDialog(
        title="Add Camera Inferno",
        message="Select a camera:",
        button=all_cams + ["Cancel"],
        defaultButton=all_cams[0],
        cancelButton="Cancel",
    )
    if result == "Cancel":
        return
    if _find_inferno(result)[0]:
        return _set_status(f"{result} already has a burn-in.", "ok")
    node = _add_inferno(result)
    if node:
        rigs = UI_STATE.get("rigs", [])
        if rigs:
            _setup_fields(node, rigs, _default_settings())
        _rebuild_cam_menu()
        cams = UI_STATE.get("cameras", [])
        for i, (xf, _) in enumerate(cams):
            if xf == result:
                cmds.optionMenu("ci_camMenu", e=True, select=i + 1)
                break
        _pilot_viewport(result)
        _on_cam_change()
        _set_status(f"Added to {result}.", "ok")
    else:
        _set_status("Failed — see Script Editor.", "err")


def _toggle(*_):
    cam_xf = _selected_cam()
    if not cam_xf:
        return
    node, _ = _find_inferno(cam_xf)
    if not node:
        return _set_status("No burn-in on this camera.", "err")
    vis = cmds.getAttr(f"{node}.visibility")
    cmds.setAttr(f"{node}.visibility", not vis)
    _update_cam_status(cam_xf)
    _set_status(f"{'Shown' if not vis else 'Hidden'} on {cam_xf}.", "ok")


def _remove(*_):
    cam_xf = _selected_cam()
    if not cam_xf:
        return
    node, parent_tfm = _find_inferno(cam_xf)
    if not node:
        return _set_status("No burn-in on this camera.", "err")
    if cmds.confirmDialog(
            title="Remove Burn-in",
            message=f"Delete burn-in from {cam_xf}?",
            button=["Delete", "Cancel"],
            defaultButton="Cancel") == "Delete":
        to_del = parent_tfm if parent_tfm and cmds.objExists(parent_tfm) else node
        if cmds.objExists(to_del):
            cmds.delete(to_del)
        for child in (cmds.listRelatives(cam_xf, children=True, fullPath=False) or []):
            if child.startswith("dummy_") or child.startswith("cameraInferno_"):
                try:
                    cmds.delete(child)
                except Exception:
                    pass
        _rebuild_cam_menu()
        _set_status(f"Removed from {cam_xf}.", "ok")


def _set_status(msg, state="neutral"):
    bg = {"ok": C_OK, "err": C_ERR}.get(state, C_STATUS)
    if cmds.text("ci_status", exists=True):
        cmds.text("ci_status", e=True, label=f"  {msg}", backgroundColor=bg)
    print(f"[Cam Inferno] {msg}")


# ---------------------------------------------------------------------------
# UI build
# ---------------------------------------------------------------------------

def build_ui():
    if cmds.window(WINDOW_ID, exists=True):
        cmds.deleteUI(WINDOW_ID)

    cameras = _inferno_cameras()
    rigs    = _get_rigs()
    UI_STATE["cameras"]  = cameras
    UI_STATE["rigs"]     = rigs
    UI_STATE["char_sel"] = ALL_CHARS

    first_cam  = cameras[0][0] if cameras else None
    first_node, _ = _find_inferno(first_cam) if first_cam else (None, None)
    s = _read_settings_from_node(first_node) if first_node else _default_settings()
    if first_cam:
        CAM_SETTINGS[first_cam] = s

    cmds.window(WINDOW_ID, title="TAOS Character Timecode",
                width=W, sizeable=True, minimizeButton=True,
                backgroundColor=C_BG)

    cmds.columnLayout("ci_rootCol", adjustableColumn=True, rowSpacing=0,
                      backgroundColor=C_BG, columnAttach=("both", 0))

    def hdr(title):
        cmds.separator(height=8, style="none")
        cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=22,
                       backgroundColor=C_HEADER, columnAttach=[(1,"both",0)])
        cmds.text(label=f"  {title}", align="left", font="boldLabelFont",
                  height=22, backgroundColor=C_HEADER)
        cmds.setParent("..")
        cmds.separator(height=1, style="in")
        cmds.separator(height=4, style="none")

    def slider(ctrl, label, mn, mx, val, prec=3):
        cmds.floatSliderGrp(ctrl, label=label, field=True,
                            minValue=mn, maxValue=mx, value=val, precision=prec,
                            columnWidth3=(LBL_W, 58, 250),
                            columnAttach3=("left","both","both"),
                            columnOffset3=(MARGIN, 4, 4),
                            backgroundColor=C_ROW,
                            changeCommand=_apply, dragCommand=_apply)
        cmds.separator(height=2, style="none")

    def lrow(label, widget_fn):
        cmds.rowLayout(numberOfColumns=2,
                       columnWidth2=(LBL_W, W - LBL_W - MARGIN * 2),
                       columnAttach=[(1,"left",MARGIN),(2,"both",4)],
                       height=ROW_H, backgroundColor=C_ROW)
        cmds.text(label=label, align="left", font="boldLabelFont",
                  backgroundColor=C_ROW)
        widget_fn()
        cmds.setParent("..")
        cmds.separator(height=2, style="none")

    # ── Plugin check ──────────────────────────────────────────────────────────
    plugin_loaded = cmds.pluginInfo("dcCameraInferno", q=True, loaded=True)
    if not plugin_loaded:
        try:
            cmds.loadPlugin("dcCameraInferno")
            plugin_loaded = cmds.pluginInfo("dcCameraInferno", q=True, loaded=True)
        except Exception:
            pass
    if not plugin_loaded:
        cmds.separator(height=6, style="none")
        cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=28,
                       columnAttach=[(1,"both",MARGIN)], backgroundColor=C_ERR)
        cmds.text(label="  ⚠  dcCameraInferno plugin not loaded.",
                  align="left", font="boldLabelFont", backgroundColor=C_ERR)
        cmds.setParent("..")

    # ── Add inferno ───────────────────────────────────────────────────────────
    cmds.separator(height=6, style="none")
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1,"both",MARGIN)], backgroundColor=C_BG)
    cmds.button(label="Add Camera Inferno to Camera", height=30,
                backgroundColor=C_BTN, command=lambda *_: _add())
    cmds.setParent("..")

    # ── Camera ────────────────────────────────────────────────────────────────
    hdr("CAMERA")

    def _cam_widget():
        cmds.optionMenu("ci_camMenu", label="", backgroundColor=C_BTN,
                        changeCommand=_on_cam_change, height=ROW_H - 2)
        if cameras:
            for xf, _ in cameras:
                cmds.menuItem(label=xf)
        else:
            cmds.menuItem(label="-- no cameras with burn-in --")

    lrow("Camera", _cam_widget)

    cam_label = f"  {first_cam}  |  visible" if first_node else \
                f"  {first_cam}  |  no burn-in" if first_cam else \
                "  No cameras with burn-in found"
    cam_bg = C_OK if first_node else C_WARN
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=22,
                   columnAttach=[(1,"both",MARGIN)], backgroundColor=cam_bg)
    cmds.text("ci_camStatus", label=cam_label, align="left",
              font="boldLabelFont", backgroundColor=cam_bg)
    cmds.setParent("..")
    cmds.separator(height=4, style="none")

    cmds.rowLayout(numberOfColumns=3,
                   columnWidth3=(W//3-MARGIN, W//3-MARGIN, W//3-MARGIN),
                   columnAttach=[(i,"both",MARGIN) for i in range(1,4)],
                   backgroundColor=C_BG)
    cmds.button(label="Toggle Visible", height=28, backgroundColor=C_BTN,
                command=lambda *_: _toggle())
    cmds.button(label="Remove", height=28, backgroundColor=(0.32,0.14,0.14),
                command=lambda *_: _remove())
    cmds.button(label="Refresh Cams", height=28, backgroundColor=C_BTN,
                command=lambda *_: _rebuild_cam_menu())
    cmds.setParent("..")

    # ── Rigs ──────────────────────────────────────────────────────────────────
    hdr("RIGS")

    rig_label = f"  {', '.join(ns or jnt for ns,jnt in rigs)}" if rigs \
                else "  ⚠  No timecode joints found"
    rig_bg = C_OK if rigs else C_ERR
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=22,
                   columnAttach=[(1,"both",MARGIN)], backgroundColor=rig_bg)
    cmds.text("ci_rigLabel", label=rig_label, align="left",
              font="boldLabelFont", backgroundColor=rig_bg)
    cmds.setParent("..")
    cmds.separator(height=4, style="none")
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1,"both",MARGIN)], backgroundColor=C_BG)
    cmds.button(label="Refresh Rigs", height=26, backgroundColor=C_BTN,
                command=lambda *_: _refresh_rigs())
    cmds.setParent("..")

    # ── Label overrides (collapsible) ─────────────────────────────────────────
    cmds.separator(height=8, style="none")
    cmds.frameLayout("ci_labelFrame", label="  LABEL OVERRIDES",
                     collapsable=True, collapse=True,
                     backgroundColor=C_HEADER, marginWidth=0, marginHeight=0)
    cmds.columnLayout("ci_labelCol", adjustableColumn=True, rowSpacing=0,
                      backgroundColor=C_BG, columnAttach=("both", 0))
    cmds.separator(height=4, style="none", parent="ci_labelCol")
    cmds.setParent("..")
    cmds.setParent("..")
    _rebuild_label_col()

    # Explicitly return to root after frameLayout so sliders always land at top level
    cmds.setParent("ci_rootCol")

    # ── Character selector ────────────────────────────────────────────────────
    hdr("CHARACTER & TRANSFORMS")

    cmds.rowLayout(numberOfColumns=2,
                   columnWidth2=(LBL_W, W - LBL_W - MARGIN * 2),
                   columnAttach=[(1,"left",MARGIN),(2,"both",4)],
                   height=ROW_H, backgroundColor=C_ROW)
    cmds.text(label="Character", align="left", font="boldLabelFont",
              backgroundColor=C_ROW)
    cmds.optionMenu("ci_charMenu", label="", backgroundColor=C_BTN,
                    changeCommand=_on_char_change, height=ROW_H - 2)
    cmds.menuItem(label=ALL_CHARS)
    for ns, jnt in rigs:
        cmds.menuItem(label=ns or jnt)
    cmds.setParent("..")
    cmds.separator(height=2, style="none")

    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1,"both",MARGIN)], height=20,
                   backgroundColor=C_BG)
    cmds.text(label="  All Characters = shared.  Individual = per-rig override.",
              align="left", font="smallPlainLabelFont", backgroundColor=C_BG)
    cmds.setParent("..")
    cmds.separator(height=4, style="none")

    cmds.rowLayout(numberOfColumns=2,
                   columnWidth2=(LBL_W, W - LBL_W - MARGIN * 2),
                   columnAttach=[(1,"left",MARGIN),(2,"both",4)],
                   height=ROW_H, backgroundColor=C_ROW)
    cmds.text(label="Separator", align="left", font="boldLabelFont",
              backgroundColor=C_ROW)
    cmds.textField("ci_separator", text=" ",
                   backgroundColor=(0.20, 0.20, 0.20),
                   changeCommand=_apply)
    cmds.setParent("..")
    cmds.separator(height=4, style="none")

    # ── Sliders — always visible, never inside a frameLayout ─────────────────
    slider("ci_posX", "Position X", -2.0,  2.0, s["x"])
    slider("ci_posY", "Position Y", -2.0,  2.0, s["y"])
    slider("ci_size", "Text Size",   1.0, 20.0, s["size"], prec=1)
    slider("ci_gap",  "Line Gap",   0.01,  0.3,  s["gap"])
    cmds.separator(height=4, style="none")
    cmds.colorSliderGrp("ci_color", label="Text Colour", rgbValue=s["col"],
                        columnWidth3=(LBL_W, 30, 250),
                        columnAttach3=("left","both","both"),
                        columnOffset3=(MARGIN, 4, 4),
                        backgroundColor=C_ROW,
                        changeCommand=_apply, dragCommand=_apply)
    cmds.separator(height=6, style="none")

    # ── Status ────────────────────────────────────────────────────────────────
    cmds.separator(height=8, style="none")
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1, height=22,
                   columnAttach=[(1,"both",MARGIN)], backgroundColor=C_STATUS)
    cmds.text("ci_status", label="  Ready.", align="left",
              font="boldLabelFont", backgroundColor=C_STATUS, height=22)
    cmds.setParent("..")
    cmds.separator(height=8, style="none")

    cmds.showWindow(WINDOW_ID)

    if first_cam:
        _pilot_viewport(first_cam)


build_ui()
