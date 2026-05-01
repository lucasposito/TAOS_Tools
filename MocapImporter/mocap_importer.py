"""
TAOS MoCap Importer for Maya
==============================
Browses S:/Shared drives/TAOS/mocap for FBX files,
filtered by solve type, character, shot, and search term.

How to use:
  1. Open Maya's Time Editor (Windows > Animation Editors > Time Editor).
  2. Select the track you want to import onto.
  3. Run this script, pick filters, select a clip, hit Import.
"""

import maya.cmds as cmds
import maya.mel as mel
import os
import re

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MOCAP_ROOT    = "Q:/Shared drives/TAOS/mocap"
SOLVE_FOLDERS = ["live_solve", "final_solve"]

CHARACTERS = {
    "All Characters": None,
    "Lavina (KM)":    "_lavina_KM",
    "Lavina (NI)":    "_lavina_NI",
    "Demon (BB)":     "_demon_BB",
    "404a (BB)":      "_404a_BB",
    "404b (NI)":      "_404b_NI",
}

SHOTS = ["All Shots", "AOP", "APT", "ELE", "ESC", "FAM", "LAB", "PEN", "ROF", "SRV"]

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

C_BG      = (0.18, 0.18, 0.18)
C_HEADER  = (0.13, 0.13, 0.13)
C_ROW     = (0.22, 0.22, 0.22)
C_BTN     = (0.30, 0.30, 0.30)
C_APPLY   = (0.26, 0.26, 0.26)
C_STATUS  = (0.15, 0.15, 0.15)
C_NOTE    = (0.16, 0.14, 0.10)
C_LIST_BG = (0.14, 0.14, 0.14)
C_OK      = (0.13, 0.28, 0.13)
C_ERR     = (0.28, 0.10, 0.10)

W      = 580
LBL_W  = 150
ROW_H  = 28
BTN_H  = 32
MARGIN = 8

# ---------------------------------------------------------------------------
# Name helpers
# ---------------------------------------------------------------------------

ALL_CHAR_SUFFIXES = [s for s in CHARACTERS.values() if s is not None]


def _extract_shot(fname):
    """Return the shot code found in the filename, or empty string."""
    upper = fname.upper()
    for shot in SHOTS[1:]:
        if re.search(r'(?<![A-Z])' + shot + r'(?![A-Z])', upper):
            return shot
    return ""


def _shorten_name(fname):
    """
    Strip the scene/date prefix and return from the shot code onward.
    e.g. THU_ASF_01_004_005_AOP_wakingUP__KM_01_rigA_lavina_KM.fbx
      -> AOP_wakingUP__KM_01_rigA_lavina_KM.fbx
    Falls back to the full name if no shot code is found.
    """
    upper = fname.upper()
    for shot in SHOTS[1:]:
        m = re.search(r'(?<![A-Z])' + shot + r'(?![A-Z])', upper)
        if m:
            return fname[m.start():]
    return fname


def _make_clip_name(fname, use_full):
    """
    Build a safe clip name from a filename.
    If use_full is False, use the shortened display name.
    """
    base = os.path.splitext(fname)[0]
    if not use_full:
        base = os.path.splitext(_shorten_name(fname))[0]
    return re.sub(r"[^A-Za-z0-9_]", "_", base)


# ---------------------------------------------------------------------------
# File scanning
# ---------------------------------------------------------------------------

def _scan_files(solve_type, char_suffix):
    base = os.path.join(MOCAP_ROOT, solve_type).replace("\\", "/")
    results = []
    if not os.path.isdir(base):
        return results
    for shoot_day in sorted(os.listdir(base)):
        shoot_path = os.path.join(base, shoot_day)
        if not os.path.isdir(shoot_path):
            continue
        for fname in sorted(os.listdir(shoot_path)):
            if not fname.lower().endswith(".fbx"):
                continue
            flow = fname.lower()
            if char_suffix is not None:
                if char_suffix.lower() not in flow:
                    continue
            else:
                if not any(s.lower() in flow for s in ALL_CHAR_SUFFIXES):
                    continue
            full = os.path.join(shoot_path, fname).replace("\\", "/")
            results.append((shoot_day, fname, full))
    return results


def _apply_list_filters():
    """Re-populate the flat scroll list from cached files using active filters."""
    files        = UI_STATE.get("files", [])
    shot_filt    = UI_STATE.get("shot", "All Shots")
    search       = UI_STATE.get("search", "").strip().lower()
    show_full    = UI_STATE.get("show_full_list", False)

    UI_STATE["selected"]  = None
    UI_STATE["label_map"] = {}   # display label -> full_path

    cmds.textScrollList("mocap_fileList", edit=True, removeAll=True)
    cmds.text("mocap_selectedLabel", edit=True, label="  -- none selected --")
    cmds.textField("mocap_clipName",   edit=True, text="")

    filtered = []
    for shoot_day, fname, full_path in files:
        if shot_filt != "All Shots" and _extract_shot(fname) != shot_filt:
            continue
        # Search applies to the full filename always so it's predictable
        if search and search not in fname.lower():
            continue
        filtered.append((shoot_day, fname, full_path))

    if not filtered:
        cmds.textScrollList("mocap_fileList", edit=True,
                            append=["  -- no files match filters --"])
        _set_status("No clips match current filters.", "err")
        return

    # Flat list — no folder headers, just files sorted as-is
    for shoot_day, fname, full_path in filtered:
        display = fname if show_full else _shorten_name(fname)
        label   = f"  {display}"
        cmds.textScrollList("mocap_fileList", edit=True, append=[label])
        UI_STATE["label_map"][label] = full_path

    _set_status(f"Showing {len(filtered)} clip(s).", "ok")


# ---------------------------------------------------------------------------
# Time Editor helpers
# ---------------------------------------------------------------------------

def _ensure_composition():
    try:
        comps = cmds.timeEditorComposition(query=True, allCompositions=True) or []
        if comps:
            return comps[0]
        return cmds.timeEditorComposition("MoCap_Composition")
    except Exception:
        raise RuntimeError(
            "Time Editor not available.\n"
            "Open it first: Windows > Animation Editors > Time Editor"
        )


def _get_selected_track(comp):
    try:
        sel = cmds.timeEditorTracks(comp, query=True, selectedTracks=True) or []
        if sel:
            return sel[0]
    except Exception:
        pass
    return 0


# ---------------------------------------------------------------------------
# Core import
# ---------------------------------------------------------------------------

def import_mocap(fbx_path, clip_name, status_fn=None):

    def log(msg, state="neutral"):
        if status_fn:
            status_fn(msg, state)
        print("[TAOS MoCap] " + msg)

    if not os.path.isfile(fbx_path):
        log("ERROR: File not found: " + fbx_path, "err")
        return False

    comp    = _ensure_composition()
    fbx_esc = fbx_path.replace("\\", "/")

    # Snapshot timeline so Maya's clip placement doesn't reset the frame range
    anim_start = cmds.playbackOptions(q=True, animationStartTime=True)
    anim_end   = cmds.playbackOptions(q=True, animationEndTime=True)
    play_start = cmds.playbackOptions(q=True, minTime=True)
    play_end   = cmds.playbackOptions(q=True, maxTime=True)
    track_idx = _get_selected_track(comp)
    track_arg = f"{comp}:{track_idx}"
    log(f"Importing onto track: {track_arg}")

    # Use the same command the Time Editor fires when you use
    # File > Import Animation Clip interactively.
    # -importAllFbxTakes and -showAnimSourceRemapping trigger the
    # namespace mapping dialog after the FBX is loaded.
    import_cmd = (
        f'timeEditorClip'
        f' -importFbx "{fbx_esc}"'
        f' -importOption generate'
        f' -importPopulateOption "curves;"'
        f' -importAllFbxTakes'
        f' -showAnimSourceRemapping'
        f' -track "{track_arg}"'
        f' "{clip_name}"'
        f';'
    )

    log(f"Running: {import_cmd}")
    try:
        mel.eval(import_cmd)
    except Exception as e:
        err_str = str(e)
        # "Maximum value must be greater than minimum value" is a non-fatal
        # Maya timeline validation warning that fires during the async namespace
        # dialog setup — the import itself still proceeds normally.
        if "Maximum value" in err_str or "minimum value" in err_str:
            log("Note: timeline range warning (non-fatal). Import continuing...")
        else:
            log(f"ERROR: Import failed: {err_str}", "err")
            return False

    # Restore timeline — guard against invalid ranges
    try:
        safe_anim_start = anim_start
        safe_anim_end   = anim_end if anim_end > anim_start else anim_start + 1
        safe_play_start = play_start
        safe_play_end   = play_end if play_end > play_start else play_start + 1
        cmds.playbackOptions(
            animationStartTime=safe_anim_start, animationEndTime=safe_anim_end,
            minTime=safe_play_start, maxTime=safe_play_end,
        )
    except Exception as e:
        log(f"Note: could not restore timeline ({e})")

    log("Import sent. Complete the namespace dialog if it appeared.", "ok")
    return True


# ---------------------------------------------------------------------------
# UI state
# ---------------------------------------------------------------------------

WINDOW_ID = "taosMocapBrowserWin"

UI_STATE = {
    "solve":          SOLVE_FOLDERS[0],
    "char_label":     "All Characters",
    "shot":           "All Shots",
    "search":         "",
    "show_full_list": False,   # show full filename in scroll list
    "show_full_clip": False,   # use full filename for clip name
    "files":          [],
    "selected":       None,
    "label_map":      {},
}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _section_header(title):
    cmds.columnLayout(adjustableColumn=True, rowSpacing=0)
    cmds.separator(height=10, style="none", backgroundColor=C_BG)
    cmds.rowLayout(
        numberOfColumns=1, adjustableColumn=1, height=24,
        backgroundColor=C_HEADER, columnAttach=[(1, "both", 0)],
    )
    cmds.text(label=f"  {title}", align="left", font="boldLabelFont",
              height=24, backgroundColor=C_HEADER)
    cmds.setParent("..")
    cmds.separator(height=1, style="in")
    cmds.separator(height=6, style="none", backgroundColor=C_BG)
    cmds.setParent("..")


def _labeled_row(label, widget_fn):
    cmds.rowLayout(
        numberOfColumns=2,
        columnWidth2=(LBL_W, W - LBL_W - MARGIN * 2),
        columnAttach=[(1, "left", MARGIN), (2, "both", 4)],
        height=ROW_H, backgroundColor=C_ROW,
    )
    cmds.text(label=label, align="left", font="boldLabelFont", backgroundColor=C_ROW)
    widget_fn()
    cmds.setParent("..")
    cmds.separator(height=2, style="none")


def _checkbox_row(label, ctrl_name, default, callback):
    cmds.rowLayout(
        numberOfColumns=2,
        columnWidth2=(LBL_W, W - LBL_W - MARGIN * 2),
        columnAttach=[(1, "left", MARGIN), (2, "left", 4)],
        height=ROW_H, backgroundColor=C_ROW,
    )
    cmds.text(label=label, align="left", font="boldLabelFont", backgroundColor=C_ROW)
    cmds.checkBox(ctrl_name, label="", value=default,
                  backgroundColor=C_ROW, changeCommand=callback)
    cmds.setParent("..")
    cmds.separator(height=2, style="none")


# ---------------------------------------------------------------------------
# UI build
# ---------------------------------------------------------------------------

def build_ui():
    if cmds.window(WINDOW_ID, exists=True):
        cmds.deleteUI(WINDOW_ID)

    cmds.window(
        WINDOW_ID,
        title="TAOS MoCap Importer",
        width=W, height=720,
        sizeable=True,
        minimizeButton=True,
        maximizeButton=False,
        backgroundColor=C_BG,
    )

    cmds.columnLayout(
        adjustableColumn=True, rowSpacing=0,
        backgroundColor=C_BG, columnAttach=("both", 0),
    )

    cmds.separator(height=6, style="none")

    # ── FILTERS ──────────────────────────────────────────────────────────────
    _section_header("FILTERS")

    def _solve_fn():
        cmds.optionMenu("mocap_solveMenu", label="",
                        changeCommand=_on_solve_char_change,
                        backgroundColor=C_BTN, height=ROW_H - 2)
        for s in SOLVE_FOLDERS:
            cmds.menuItem(label=s)

    _labeled_row("Solve Type", _solve_fn)

    def _char_fn():
        cmds.optionMenu("mocap_charMenu", label="",
                        changeCommand=_on_solve_char_change,
                        backgroundColor=C_BTN, height=ROW_H - 2)
        for c in CHARACTERS:
            cmds.menuItem(label=c)

    _labeled_row("Character", _char_fn)

    def _shot_fn():
        cmds.optionMenu("mocap_shotMenu", label="",
                        changeCommand=_on_shot_change,
                        backgroundColor=C_BTN, height=ROW_H - 2)
        for s in SHOTS:
            cmds.menuItem(label=s)

    _labeled_row("Shot", _shot_fn)

    def _search_fn():
        cmds.textField("mocap_searchField",
                       placeholderText="type to filter...",
                       backgroundColor=(0.20, 0.20, 0.20),
                       changeCommand=_on_search_change)

    _labeled_row("Search", _search_fn)

    cmds.separator(height=6, style="none")
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1, "both", MARGIN)], backgroundColor=C_BG)
    cmds.button(label="Clear Filters", height=BTN_H, backgroundColor=C_BTN,
                command=lambda *_: _clear_filters())
    cmds.setParent("..")

    # ── DISPLAY OPTIONS (collapsible) ────────────────────────────────────────
    cmds.separator(height=10, style="none")
    cmds.frameLayout(
        "mocap_displayFrame",
        label="  DISPLAY OPTIONS",
        collapsable=True,
        collapse=True,
        backgroundColor=C_HEADER,
        marginWidth=0,
        marginHeight=4,
    )
    cmds.columnLayout(adjustableColumn=True, rowSpacing=0)
    cmds.separator(height=4, style="none")
    _checkbox_row("Full List Names", "mocap_fullListChk", False,
                  lambda v: _on_full_list_change(v))
    _checkbox_row("Full Clip Name",  "mocap_fullClipChk", False,
                  lambda v: _on_full_clip_change(v))
    cmds.separator(height=4, style="none")
    cmds.setParent("..")   # columnLayout
    cmds.setParent("..")   # frameLayout

    # ── FILE LIST ────────────────────────────────────────────────────────────
    _section_header("MOCAP FILES")

    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1, "both", MARGIN)], backgroundColor=C_BG)
    cmds.textScrollList(
        "mocap_fileList",
        numberOfRows=14,
        allowMultiSelection=False,
        backgroundColor=C_LIST_BG,
        font="plainLabelFont",
        height=290,
        selectCommand=_on_file_select,
    )
    cmds.setParent("..")

    # ── SELECTED CLIP ────────────────────────────────────────────────────────
    _section_header("SELECTED CLIP")

    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1, "both", MARGIN)],
                   height=28, backgroundColor=C_ROW)
    cmds.text("mocap_selectedLabel", label="  -- none selected --",
              align="left", font="boldLabelFont", backgroundColor=C_ROW)
    cmds.setParent("..")
    cmds.separator(height=2, style="none")

    def _clip_fn():
        cmds.textField("mocap_clipName", text="",
                       placeholderText="auto-filled from filename",
                       backgroundColor=(0.20, 0.20, 0.20))

    _labeled_row("Clip Name", _clip_fn)

    # ── REMINDER NOTE ────────────────────────────────────────────────────────
    cmds.separator(height=8, style="none")
    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1, "both", MARGIN)],
                   height=32, backgroundColor=C_NOTE)
    cmds.text(label="  \u26a0  Select a track in the Time Editor before importing.",
              align="left", font="boldLabelFont", backgroundColor=C_NOTE)
    cmds.setParent("..")

    # ── STATUS + IMPORT ──────────────────────────────────────────────────────
    cmds.separator(height=8, style="none")

    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1, "both", MARGIN)],
                   height=26, backgroundColor=C_STATUS)
    cmds.text("mocap_status", label="  Select a clip and click Import.",
              align="left", font="boldLabelFont",
              backgroundColor=C_STATUS, height=26)
    cmds.setParent("..")

    cmds.separator(height=8, style="none")

    cmds.rowLayout(numberOfColumns=1, adjustableColumn=1,
                   columnAttach=[(1, "both", MARGIN)], backgroundColor=C_BG)
    cmds.button("mocap_importBtn", label="Import Animation Clip",
                height=40, backgroundColor=C_APPLY,
                command=lambda *_: _on_import())
    cmds.setParent("..")

    cmds.separator(height=10, style="none")

    cmds.showWindow(WINDOW_ID)
    _refresh_file_list()


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

def _on_solve_char_change(*_):
    UI_STATE["solve"]      = cmds.optionMenu("mocap_solveMenu", q=True, value=True)
    UI_STATE["char_label"] = cmds.optionMenu("mocap_charMenu",  q=True, value=True)
    _refresh_file_list()


def _on_shot_change(value):
    UI_STATE["shot"] = value
    _apply_list_filters()


def _on_search_change(value):
    UI_STATE["search"] = value
    _apply_list_filters()


def _on_full_list_change(value):
    """Full list names toggled.
    ON  -> force clip name full as well, disable that checkbox.
    OFF -> reset clip name to short, disable clip checkbox (user must re-enable).
    """
    UI_STATE["show_full_list"] = bool(value)
    if value:
        UI_STATE["show_full_clip"] = True
        cmds.checkBox("mocap_fullClipChk", edit=True, value=True, enable=False)
    else:
        # Reset clip name to short and disable checkbox so it defaults to short.
        # The user can still manually tick it to get a full clip name.
        UI_STATE["show_full_clip"] = False
        cmds.checkBox("mocap_fullClipChk", edit=True, value=False, enable=True)
    _apply_list_filters()
    _refresh_selected_clip_name()


def _on_full_clip_change(value):
    """Full clip name toggled independently (only when full list names is OFF)."""
    UI_STATE["show_full_clip"] = bool(value)
    _refresh_selected_clip_name()


def _refresh_selected_clip_name():
    """Re-derive the clip name from the currently selected file."""
    full_path = UI_STATE.get("selected")
    if not full_path:
        return
    fname     = os.path.basename(full_path)
    use_full  = UI_STATE.get("show_full_clip", False)
    clip_name = _make_clip_name(fname, use_full)
    cmds.textField("mocap_clipName", edit=True, text=clip_name)


def _clear_filters():
    UI_STATE["shot"]   = "All Shots"
    UI_STATE["search"] = ""
    cmds.optionMenu("mocap_shotMenu",   edit=True, value="All Shots")
    cmds.textField("mocap_searchField", edit=True, text="")
    _apply_list_filters()


def _refresh_file_list():
    solve      = UI_STATE["solve"]
    char_label = UI_STATE["char_label"]
    suffix     = CHARACTERS[char_label]

    label = char_label if char_label != "All Characters" else "all characters"
    _set_status(f"Scanning {solve} for {label}...")
    cmds.refresh()

    files = _scan_files(solve, suffix)
    UI_STATE["files"] = files

    if not files:
        cmds.textScrollList("mocap_fileList", edit=True, removeAll=True)
        cmds.textScrollList("mocap_fileList", edit=True,
                            append=["  -- no files found --"])
        _set_status(f"No files found in {solve}.", "err")
        return

    _apply_list_filters()


def _on_file_select():
    sel = cmds.textScrollList("mocap_fileList", q=True, selectItem=True) or []
    if not sel:
        return

    item = sel[0]

    if "no files" in item.strip():
        cmds.textScrollList("mocap_fileList", edit=True, deselectAll=True)
        UI_STATE["selected"] = None
        return

    full_path = UI_STATE["label_map"].get(item)
    if not full_path:
        UI_STATE["selected"] = None
        return

    fname     = os.path.basename(full_path)
    shoot_day = os.path.basename(os.path.dirname(full_path))

    UI_STATE["selected"] = full_path

    # Selected label always shows full folder + full filename
    cmds.text("mocap_selectedLabel", edit=True,
              label=f"  {shoot_day}  /  {fname}")

    # Clip name follows the full/short setting
    use_full  = UI_STATE.get("show_full_clip", False)
    clip_name = _make_clip_name(fname, use_full)
    cmds.textField("mocap_clipName", edit=True, text=clip_name)

    short = _shorten_name(fname)
    _set_status(f"Selected: {short}", "ok")


def _set_status(msg, state="neutral"):
    bg = {"ok": C_OK, "err": C_ERR}.get(state, C_STATUS)
    cmds.text("mocap_status", edit=True, label=f"  {msg}", backgroundColor=bg)


def _on_import():
    fbx_path  = UI_STATE.get("selected")
    clip_name = cmds.textField("mocap_clipName", q=True, text=True).strip()

    if not fbx_path or not os.path.isfile(fbx_path):
        cmds.confirmDialog(title="TAOS MoCap Importer",
                           message="Please select a clip from the list first.",
                           button=["OK"])
        return

    if not clip_name:
        fname     = os.path.basename(fbx_path)
        use_full  = UI_STATE.get("show_full_clip", False)
        clip_name = _make_clip_name(fname, use_full)

    _set_status("Importing...  (complete the namespace dialog if it appears)", "neutral")
    cmds.button("mocap_importBtn", edit=True, enable=False, label="Importing...")
    cmds.refresh()

    try:
        ok = import_mocap(
            fbx_path=fbx_path,
            clip_name=clip_name,
            status_fn=lambda m, s="neutral": _set_status(m, s),
        )
        if ok:
            _set_status("Import sent  |  complete the namespace dialog if it appeared.", "ok")
        else:
            _set_status("Import failed — see Script Editor for details.", "err")
    except Exception as e:
        _set_status(f"Error: {e}", "err")
        import traceback
        traceback.print_exc()
    finally:
        cmds.button("mocap_importBtn", edit=True, enable=True,
                    label="Import Animation Clip")


# ---------------------------------------------------------------------------
build_ui()
