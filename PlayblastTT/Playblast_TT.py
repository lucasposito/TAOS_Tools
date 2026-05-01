"""
Turntable Camera Setup Tool for Maya  –  TAOS
==============================================
Dockable, multi-rig turntable tool. Namespace-aware.

Hierarchy per rig:
  TAOS_tt_rig_<name>_GRP          root (tagged, stores metadata)
    <name>_start_rot              initial-rotation group (live slider)
      <name>_pivot                turntable spin + roll (rotateY / rotateX)
        <name>_offset             dolly Z / pedestal Y / truck X
          <name>_camera

Usage: run in Maya Script Editor (Python tab).
"""

import maya.cmds as cmds
import math

WINDOW_ID  = "turntableCamTool"
DOCK_ID    = "turntableCamDock"
RIG_TAG    = "tt_rig"
RIG_PREFIX = "TAOS_tt_rig_"
GRP_SUFFIX = "_GRP"

# --------------------------------------------------------------------------- #
#  Scene helpers
# --------------------------------------------------------------------------- #

def get_scene_bounds():
    meshes = cmds.ls(type="mesh", visible=True, long=True)
    if not meshes:
        return None
    all_min = [float("inf")]  * 3
    all_max = [float("-inf")] * 3
    for mesh in meshes:
        try:
            bb = cmds.exactWorldBoundingBox(mesh)
            for i in range(3):
                all_min[i] = min(all_min[i], bb[i])
                all_max[i] = max(all_max[i], bb[i + 3])
        except Exception:
            continue
    if all_min[0] == float("inf"):
        return None
    center = [(all_min[i] + all_max[i]) * 0.5 for i in range(3)]
    size   = [all_max[i] - all_min[i] for i in range(3)]
    radius = math.sqrt(sum(s * s for s in size)) * 0.5
    return center, size, radius

# --------------------------------------------------------------------------- #
#  Namespace helpers
# --------------------------------------------------------------------------- #

def _strip_ns(name):
    return name.split(":")[-1] if name else name

def _resolve_node(stored):
    if not stored:
        return None
    if cmds.objExists(stored):
        return stored
    base = _strip_ns(stored)
    for candidate in (cmds.ls("*:{}".format(base)) or []) + (cmds.ls(base) or []):
        return candidate
    return None

# --------------------------------------------------------------------------- #
#  Rig registry
# --------------------------------------------------------------------------- #

def list_rigs():
    rigs = []
    for t in (cmds.ls(type="transform") or []):
        try:
            if cmds.attributeQuery(RIG_TAG, node=t, exists=True):
                rigs.append(t)
        except Exception:
            pass
    return sorted(rigs)

def rig_is_valid(grp):
    if not grp or not cmds.objExists(grp):
        return False
    try:
        cam = _resolve_node(_grp_attr(grp, "tt_cam_transform"))
        piv = _resolve_node(_grp_attr(grp, "tt_pivot_node"))
        return bool(cam and piv)
    except Exception:
        return False

def _grp_attr(grp, attr):
    try:
        return cmds.getAttr("{}.{}".format(grp, attr))
    except Exception:
        return None

# --------------------------------------------------------------------------- #
#  Build
# --------------------------------------------------------------------------- #

def build_turntable_rig(name, focal_length=50.0, start_frame=1001, num_frames=120):
    grp_name = "{}{}{}".format(RIG_PREFIX, name, GRP_SUFFIX)
    if cmds.objExists(grp_name):
        cmds.delete(grp_name)

    result = get_scene_bounds()
    center, size, radius = result if result else ([0,0,0],[1,1,1],1.0)

    render_w = cmds.getAttr("defaultResolution.width")
    render_h = cmds.getAttr("defaultResolution.height")
    aspect   = float(render_w) / float(render_h) if render_h else 1.7778

    half_w    = size[0] * 0.5
    half_h    = size[1] * 0.5
    half_d    = size[2] * 0.5
    max_horiz = math.sqrt(half_w * half_w + half_d * half_d)

    hfov_rad    = 2.0 * math.atan(18.0 / focal_length)
    film_aspect = 1.5
    eff_vfov    = (2.0 * math.atan(math.tan(hfov_rad * 0.5) / aspect)
                   if aspect > film_aspect
                   else 2.0 * math.atan(12.0 / focal_length))

    distance = max((half_h    / math.tan(eff_vfov  * 0.5)) * 1.15,
                   (max_horiz / math.tan(hfov_rad  * 0.5)) * 1.15)

    # -- start_rot group: lives at scene origin, controls initial Y offset --
    start_rot = cmds.group(empty=True, name="{}_start_rot".format(name))
    cmds.xform(start_rot, worldSpace=True, translation=center)

    # -- pivot: child of start_rot, gets the turntable keyframes + roll --
    pivot = cmds.spaceLocator(name="{}_pivot".format(name))[0]
    cmds.parent(pivot, start_rot)
    cmds.xform(pivot, objectSpace=True, translation=[0, 0, 0])
    for ax in ("localScaleX", "localScaleY", "localScaleZ"):
        cmds.setAttr("{}.{}".format(pivot, ax), radius * 0.15)

    # -- offset group --
    offset_grp = cmds.group(empty=True, name="{}_offset".format(name))
    cmds.parent(offset_grp, pivot)
    cmds.xform(offset_grp, objectSpace=True, translation=[0, 0, distance])

    # -- camera --
    cam_transform, cam_shape = cmds.camera(
        name="{}_camera".format(name),
        focalLength=focal_length,
        nearClipPlane=max(0.1, distance * 0.001),
        farClipPlane=distance * 20.0
    )
    cmds.parent(cam_transform, offset_grp)
    cmds.xform(cam_transform, objectSpace=True, translation=[0, 0, 0])
    cmds.xform(cam_transform, objectSpace=True, rotation=[0, 0, 0])

    aim_con = cmds.aimConstraint(
        pivot, cam_transform,
        aimVector=[0, 0, -1], upVector=[0, 1, 0],
        worldUpType="scene", maintainOffset=False
    )
    cmds.delete(aim_con)

    # -- root group --
    grp = cmds.group(start_rot, name=grp_name)

    # metadata
    cmds.addAttr(grp, longName=RIG_TAG,              attributeType="bool",   defaultValue=True)
    cmds.addAttr(grp, longName="tt_rig_name",        dataType="string")
    cmds.addAttr(grp, longName="tt_base_distance",   attributeType="double", defaultValue=distance)
    cmds.addAttr(grp, longName="tt_truck",           attributeType="double", defaultValue=0.0)
    cmds.addAttr(grp, longName="tt_pedestal",        attributeType="double", defaultValue=0.0)
    cmds.addAttr(grp, longName="tt_roll",            attributeType="double", defaultValue=0.0)
    cmds.addAttr(grp, longName="tt_initial_rot",     attributeType="double", defaultValue=0.0)
    cmds.addAttr(grp, longName="tt_focal_length",    attributeType="double", defaultValue=focal_length)
    cmds.addAttr(grp, longName="tt_cam_transform",   dataType="string")
    cmds.addAttr(grp, longName="tt_cam_shape",       dataType="string")
    cmds.addAttr(grp, longName="tt_pivot_node",      dataType="string")
    cmds.addAttr(grp, longName="tt_start_rot_node",  dataType="string")
    cmds.addAttr(grp, longName="tt_offset_node",     dataType="string")

    cmds.setAttr(grp + ".tt_rig_name",       name,          type="string")
    cmds.setAttr(grp + ".tt_cam_transform",  cam_transform, type="string")
    cmds.setAttr(grp + ".tt_cam_shape",      cam_shape,     type="string")
    cmds.setAttr(grp + ".tt_pivot_node",     pivot,         type="string")
    cmds.setAttr(grp + ".tt_start_rot_node", start_rot,     type="string")
    cmds.setAttr(grp + ".tt_offset_node",    offset_grp,    type="string")

    # turntable keyframes on pivot rotateY
    end_frame = start_frame + num_frames
    cmds.setKeyframe(pivot, attribute="rotateY", time=start_frame, value=0)
    cmds.setKeyframe(pivot, attribute="rotateY", time=end_frame,   value=360)
    cmds.selectKey(pivot, attribute="rotateY", time=(start_frame, end_frame))
    cmds.keyTangent(inTangentType="linear", outTangentType="linear")
    cmds.playbackOptions(animationStartTime=start_frame, minTime=start_frame,
                         animationEndTime=end_frame,     maxTime=end_frame)
    cmds.currentTime(start_frame)

    _look_through_cam(cam_transform, cam_shape)
    return grp

def delete_rig(grp):
    if grp and cmds.objExists(grp):
        cmds.delete(grp)

# --------------------------------------------------------------------------- #
#  Per-rig controls
# --------------------------------------------------------------------------- #

def apply_dolly(grp, value):
    ogrp = _resolve_node(_grp_attr(grp, "tt_offset_node"))
    base = _grp_attr(grp, "tt_base_distance") or 0.0
    if ogrp:
        cmds.setAttr(ogrp + ".translateZ", base + value)

def apply_pedestal(grp, value):
    ogrp = _resolve_node(_grp_attr(grp, "tt_offset_node"))
    if ogrp:
        cmds.setAttr(ogrp + ".translateY", value)
    if grp and cmds.objExists(grp):
        cmds.setAttr(grp + ".tt_pedestal", value)

def apply_truck(grp, value):
    ogrp = _resolve_node(_grp_attr(grp, "tt_offset_node"))
    if ogrp:
        cmds.setAttr(ogrp + ".translateX", value)
    if grp and cmds.objExists(grp):
        cmds.setAttr(grp + ".tt_truck", value)

def apply_roll(grp, value):
    """Roll: tilt camera up/down by rotating the pivot on X."""
    pivot = _resolve_node(_grp_attr(grp, "tt_pivot_node"))
    if pivot:
        cmds.setAttr(pivot + ".rotateX", value)
    if grp and cmds.objExists(grp):
        cmds.setAttr(grp + ".tt_roll", value)

def apply_initial_rot(grp, value):
    """Initial rotation: rotates the start_rot group on Y (live, no keys)."""
    srot = _resolve_node(_grp_attr(grp, "tt_start_rot_node"))
    if srot:
        cmds.setAttr(srot + ".rotateY", value)
    if grp and cmds.objExists(grp):
        cmds.setAttr(grp + ".tt_initial_rot", value)

def apply_focal_length(grp, value):
    cam_shape = _resolve_node(_grp_attr(grp, "tt_cam_shape"))
    if cam_shape:
        cmds.setAttr(cam_shape + ".focalLength", value)
    if grp and cmds.objExists(grp):
        cmds.setAttr(grp + ".tt_focal_length", value)

def set_pivot_from_selection(grp):
    sel = cmds.ls(selection=True, long=True)
    if not sel:
        cmds.warning("Select at least one object first.")
        return None
    bb = cmds.exactWorldBoundingBox(*sel)
    cx, cy, cz = (bb[0]+bb[3])*0.5, (bb[1]+bb[4])*0.5, (bb[2]+bb[5])*0.5
    # Move the start_rot group so the whole rig re-centers
    srot = _resolve_node(_grp_attr(grp, "tt_start_rot_node"))
    if srot:
        cmds.xform(srot, worldSpace=True, translation=[cx, cy, cz])
    return cx, cy, cz

def select_rig_camera(grp, include_shape=False):
    """
    Select the camera transform (and optionally its shape) for the active rig.
    Useful for publishing workflows — call this, then export/publish selection.

    Args:
        grp           : the rig root group node
        include_shape : if True, also adds the camera shape to the selection
                        (needed by some exporters that expect the shape node)

    Returns:
        cam_transform name if successful, else None.
    """
    if not rig_is_valid(grp):
        cmds.warning("TAOS: No valid active rig to select camera from.")
        return None

    cam = _resolve_node(_grp_attr(grp, "tt_cam_transform"))
    shp = _resolve_node(_grp_attr(grp, "tt_cam_shape"))

    if not cam:
        cmds.warning("TAOS: Could not resolve camera transform for rig.")
        return None

    nodes = [cam]
    if include_shape and shp:
        nodes.append(shp)

    cmds.select(nodes, replace=True)

    rig_name = _grp_attr(grp, "tt_rig_name") or _strip_ns(grp)
    label = cam if not include_shape else "{} + shape".format(cam)
    print("TAOS: Selected camera  {}  (rig: {})".format(label, rig_name))
    return cam

def update_frame_range(grp, start_frame, num_frames):
    """
    Re-key the turntable rotation on the active rig's pivot and update
    the scene playback range to match.

    Removes any existing rotateY keys on the pivot, then sets fresh
    linear keys:  start_frame -> 0 deg,  start_frame + num_frames -> 360 deg.

    Args:
        grp         : rig root group node
        start_frame : new start frame (int)
        num_frames  : total number of frames for one full 360° spin (int >= 1)

    Returns:
        (start_frame, end_frame) tuple on success, else None.
    """
    if not rig_is_valid(grp):
        cmds.warning("TAOS: No valid active rig to update frame range on.")
        return None

    pivot = _resolve_node(_grp_attr(grp, "tt_pivot_node"))
    if not pivot:
        cmds.warning("TAOS: Could not resolve pivot node.")
        return None

    num_frames  = max(1, int(num_frames))
    start_frame = int(start_frame)
    end_frame   = start_frame + num_frames

    # Remove existing rotateY keys on the pivot
    try:
        cmds.cutKey(pivot, attribute="rotateY", clear=True)
    except Exception:
        pass

    # Set new linear keys
    cmds.setKeyframe(pivot, attribute="rotateY", time=start_frame, value=0)
    cmds.setKeyframe(pivot, attribute="rotateY", time=end_frame,   value=360)
    cmds.selectKey(pivot, attribute="rotateY", time=(start_frame, end_frame))
    cmds.keyTangent(inTangentType="linear", outTangentType="linear")

    # Update playback range
    cmds.playbackOptions(animationStartTime=start_frame, minTime=start_frame,
                         animationEndTime=end_frame,     maxTime=end_frame)
    cmds.currentTime(start_frame)

    rig_name = _grp_attr(grp, "tt_rig_name") or _strip_ns(grp)
    print("TAOS: Frame range updated  {}-{}  ({} frames)  rig: {}".format(
        start_frame, end_frame, num_frames, rig_name))
    return start_frame, end_frame


def _look_through_cam(cam_transform, cam_shape):
    panels  = cmds.getPanel(type="modelPanel") or []
    focused = cmds.getPanel(withFocus=True)
    target  = focused if focused in panels else (panels[0] if panels else None)
    if target:
        cmds.modelEditor(target, edit=True, camera=cam_transform)
        cmds.setAttr(cam_shape + ".displayResolution", 1)
        cmds.setAttr(cam_shape + ".displayFilmGate",   0)
        cmds.camera(cam_transform, edit=True, displayResolution=True)
        cmds.setAttr(cam_shape + ".overscan", 1.1)

def look_through_rig(grp):
    cam = _resolve_node(_grp_attr(grp, "tt_cam_transform"))
    shp = _resolve_node(_grp_attr(grp, "tt_cam_shape"))
    if cam and shp:
        _look_through_cam(cam, shp)

# --------------------------------------------------------------------------- #
#  UI
# --------------------------------------------------------------------------- #

def launch_ui():
    if cmds.dockControl(DOCK_ID, exists=True):
        cmds.deleteUI(DOCK_ID)
    if cmds.window(WINDOW_ID, exists=True):
        cmds.deleteUI(WINDOW_ID)

    win = cmds.window(WINDOW_ID, title="Turntable Camera Tool",
                      widthHeight=(390, 800), sizeable=True, mnb=False, mxb=False)

    header_bg  = [0.13, 0.13, 0.16]
    section_bg = [0.18, 0.18, 0.22]
    accent     = [0.22, 0.60, 0.85]
    publish    = [0.18, 0.52, 0.36]   # green-teal for publish/select actions
    danger     = [0.55, 0.18, 0.18]

    cmds.scrollLayout(horizontalScrollBarThickness=0, verticalScrollBarThickness=8)
    main_col = cmds.columnLayout(adjustableColumn=True, rowSpacing=0)

    # HEADER
    cmds.frameLayout(label="", collapsable=False, backgroundColor=header_bg,
                     marginHeight=10, marginWidth=12, parent=main_col)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=2)
    cmds.text(label="TURNTABLE CAMERA", font="boldLabelFont",
              align="center", height=22, backgroundColor=header_bg)
    cmds.text(label="TAOS  |  Multi-rig turntable tool",
              font="smallBoldLabelFont", align="center", backgroundColor=header_bg)
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.separator(height=4, style="none", parent=main_col)

    # ACTIVE RIG
    cmds.frameLayout(label=" ACTIVE RIG", collapsable=True, collapse=False,
                     backgroundColor=section_bg, marginHeight=8, marginWidth=8,
                     parent=main_col)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
    cmds.rowLayout(numberOfColumns=3, columnWidth3=[80, 210, 60],
                   columnAlign3=["right","left","left"], adjustableColumn=2)
    cmds.text(label="Rig  ")
    rig_dropdown = cmds.optionMenu(changeCommand=lambda v: _on_rig_changed(v))
    cmds.button(label="Refresh", width=58, command=lambda *_: _populate_dropdown())
    cmds.setParent("..")
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    cmds.button(label="Look Through Active", height=26,
                command=lambda *_: _look_through_active())
    cmds.button(label="Delete Active", height=26, backgroundColor=danger,
                command=lambda *_: _delete_active())
    cmds.setParent("..")
    status_txt = cmds.text(label="", align="center", font="smallBoldLabelFont")
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.separator(height=4, style="none", parent=main_col)

    # BUILD NEW RIG
    cmds.frameLayout(label=" BUILD NEW RIG", collapsable=True, collapse=False,
                     backgroundColor=section_bg, marginHeight=8, marginWidth=8,
                     parent=main_col)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    def _field_row(lbl, widget_fn):
        cmds.rowLayout(numberOfColumns=2, columnWidth2=[160, 180],
                       columnAlign2=["right","left"], adjustableColumn=1)
        cmds.text(label=lbl + "  ", align="right")
        w = widget_fn()
        cmds.setParent("..")
        return w

    name_fld     = _field_row("Name",
                       lambda: cmds.textField(text="cam1", width=120))
    fl_field     = _field_row("Focal Length (mm)",
                       lambda: cmds.floatField(value=50.0, minValue=10.0,
                                               maxValue=500.0, step=1.0,
                                               width=80, precision=1))
    sf_build_fld = _field_row("Start Frame",
                       lambda: cmds.intField(value=1001, minValue=0, width=80))
    nf_build_fld = _field_row("Number of Frames",
                       lambda: cmds.intField(value=120, minValue=1, width=80))
    cmds.button(label="Build Rig", height=32, backgroundColor=accent,
                command=lambda *_: _build_cmd())
    cmds.separator(height=4, style="in")
    cmds.text(label="Update active rig's frame range without rebuilding.",
              align="center", font="smallBoldLabelFont")
    cmds.button(label="Update Frame Range on Active Rig", height=28,
                annotation="Re-keys the turntable rotation and updates the playback\n"
                            "range using the Start Frame and Number of Frames values above.\n"
                            "Does not rebuild the rig — camera position is preserved.",
                command=lambda *_: _update_frames_cmd())
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.separator(height=4, style="none", parent=main_col)

    # CAMERA CONTROLS
    cmds.frameLayout(label=" CAMERA CONTROLS", collapsable=True, collapse=False,
                     backgroundColor=section_bg, marginHeight=8, marginWidth=8,
                     parent=main_col)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=4)

    def _sync_fld(f, v): cmds.floatField(f, edit=True, value=v)
    def _sync_sl(s, v):  cmds.floatSlider(s, edit=True, value=v)

    def _slider_row(lbl, tip, minv, maxv, default, step, cmd_fn, reset_val=0.0):
        """Slider row with its own inline Reset button."""
        cmds.rowLayout(numberOfColumns=4, columnWidth4=[95, 185, 55, 40],
                       columnAlign4=["right","left","left","left"],
                       adjustableColumn=2)
        cmds.text(label=lbl + "  ", align="right", annotation=tip)
        sl  = cmds.floatSlider(minValue=minv, maxValue=maxv, value=default, step=step)
        fld = cmds.floatField(value=default, minValue=minv, maxValue=maxv,
                              step=step, precision=2, width=52)
        cmds.floatSlider(sl, edit=True,
                         changeCommand=lambda v: (_sync_fld(fld, v), cmd_fn(v)),
                         dragCommand=lambda v:   (_sync_fld(fld, v), cmd_fn(v)))
        cmds.floatField(fld, edit=True,
                        changeCommand=lambda v: (_sync_sl(sl, v), cmd_fn(v)))
        # inline reset button – resets to reset_val (captured in default arg)
        rv = reset_val
        cmds.button(label="R", width=36, height=20,
                    annotation="Reset {}".format(lbl),
                    command=lambda *_, s=sl, f=fld, r=rv, fn=cmd_fn: (
                        _sync_sl(s, r), _sync_fld(f, r), fn(r)))
        cmds.setParent("..")
        return sl, fld

    dolly_sl,  dolly_fld  = _slider_row(
        "Dolly",        "Push/pull camera",        -500, 500,  0,  1,
        lambda v: apply_dolly(_active_grp(), float(v)))
    ped_sl,    ped_fld    = _slider_row(
        "Pedestal",     "Move up / down",          -200, 200,  0,  1,
        lambda v: apply_pedestal(_active_grp(), float(v)))
    truck_sl,  truck_fld  = _slider_row(
        "Truck",        "Slide left / right",      -200, 200,  0,  1,
        lambda v: apply_truck(_active_grp(), float(v)))
    roll_sl,   roll_fld   = _slider_row(
        "Roll",         "Tilt camera (pivot X)",   -90,   90,  0,  1,
        lambda v: apply_roll(_active_grp(), float(v)))
    init_sl,   init_fld   = _slider_row(
        "Initial Rot",  "Starting Y rotation",    -360,  360,  0,  1,
        lambda v: apply_initial_rot(_active_grp(), float(v)))
    focal_sl,  focal_fld  = _slider_row(
        "Focal Length", "Focal length mm",           10,  200, 50,  1,
        lambda v: apply_focal_length(_active_grp(), float(v)), reset_val=50.0)

    cmds.separator(height=4, style="in")
    cmds.button(label="Reset All Controls", height=26,
                command=lambda *_: _reset_all_controls())
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.separator(height=4, style="none", parent=main_col)

    # PIVOT
    cmds.frameLayout(label=" PIVOT POSITION", collapsable=True, collapse=False,
                     backgroundColor=section_bg, marginHeight=8, marginWidth=8,
                     parent=main_col)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)
    cmds.text(label="Select object(s), then click Set.",
              align="center", font="smallBoldLabelFont")
    cmds.rowLayout(numberOfColumns=6,
                   columnWidth6=[18, 80, 18, 80, 18, 80],
                   adjustableColumn=6,
                   columnAlign6=["right","left","right","left","right","left"])
    cmds.text(label="X ")
    piv_x = cmds.floatField(value=0.0, precision=3, enable=False)
    cmds.text(label="Y ")
    piv_y = cmds.floatField(value=0.0, precision=3, enable=False)
    cmds.text(label="Z ")
    piv_z = cmds.floatField(value=0.0, precision=3, enable=False)
    cmds.setParent("..")
    cmds.button(label="Set Pivot from Selected", height=32,
                backgroundColor=accent, command=lambda *_: _do_set_pivot())
    cmds.setParent("..")
    cmds.setParent("..")
    cmds.separator(height=4, style="none", parent=main_col)

    # DISPLAY
    cmds.frameLayout(label=" DISPLAY", collapsable=True, collapse=False,
                     backgroundColor=section_bg, marginHeight=8, marginWidth=8,
                     parent=main_col)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=6)

    # Locator visibility row
    cmds.rowLayout(numberOfColumns=2, adjustableColumn=1)
    cmds.button(label="Hide All Locators", height=28,
                command=lambda *_: _set_locator_visibility(False))
    cmds.button(label="Show All Locators", height=28,
                command=lambda *_: _set_locator_visibility(True))
    cmds.setParent("..")

    # -- PUBLISH / SELECT CAMERA ------------------------------------------- #
    cmds.separator(height=6, style="in")
    cmds.text(label="Publish", align="left", font="smallBoldLabelFont")
    cmds.separator(height=3, style="none")

    # Read-only field showing the resolved camera node name
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[105, 230],
                   columnAlign2=["right", "left"], adjustableColumn=2)
    cmds.text(label="Camera node  ", align="right", annotation="Resolved camera transform")
    cam_name_fld = cmds.textField(text="--", editable=False, width=200,
                                  annotation="Camera transform that will be selected")
    cmds.setParent("..")

    # Checkbox: also select shape node
    cmds.rowLayout(numberOfColumns=2, columnWidth2=[105, 230],
                   columnAlign2=["right", "left"], adjustableColumn=2)
    cmds.text(label="")
    include_shape_cb = cmds.checkBox(label="Include shape node",
                                     value=False,
                                     annotation="Also add the camera shape to the selection "
                                                 "(required by some export/publish tools)")
    cmds.setParent("..")

    # Select button
    cmds.button(label="Select Camera for Publish", height=32,
                backgroundColor=publish,
                annotation="Selects the active rig's camera transform in the scene.\n"
                            "Use this to then run File > Export Selected or your\n"
                            "pipeline publish command.",
                command=lambda *_: _select_cam_for_publish())

    cmds.separator(height=4, style="none")
    # -- end PUBLISH block ------------------------------------------------- #

    cmds.setParent("..")  # end columnLayout
    cmds.setParent("..")  # end frameLayout
    cmds.separator(height=6, style="none", parent=main_col)

    # INTERNAL STATE
    _state = {"active_grp": None}

    def _active_grp():
        return _state["active_grp"]

    def _set_active(grp):
        _state["active_grp"] = grp
        _load_rig_into_controls(grp)
        _refresh_cam_name_field(grp)

    def _refresh_cam_name_field(grp):
        """Update the read-only camera name field to show the current rig's camera."""
        if rig_is_valid(grp):
            cam = _resolve_node(_grp_attr(grp, "tt_cam_transform")) or "--"
        else:
            cam = "--"
        cmds.textField(cam_name_fld, edit=True, text=cam)

    def _populate_dropdown():
        for it in (cmds.optionMenu(rig_dropdown, q=True, itemListLong=True) or []):
            cmds.deleteUI(it)
        rigs = list_rigs()
        if rigs:
            for r in rigs:
                cmds.menuItem(label=_grp_attr(r, "tt_rig_name") or _strip_ns(r),
                              parent=rig_dropdown)
            current = _state["active_grp"]
            if current and current in rigs:
                cmds.optionMenu(rig_dropdown, edit=True, select=rigs.index(current) + 1)
            else:
                cmds.optionMenu(rig_dropdown, edit=True, select=1)
                _set_active(rigs[0])
        else:
            cmds.menuItem(label="-- no rigs --", parent=rig_dropdown)
            _state["active_grp"] = None
            _refresh_cam_name_field(None)
        _refresh_status()

    def _on_rig_changed(label):
        for r in list_rigs():
            if (_grp_attr(r, "tt_rig_name") or _strip_ns(r)) == label:
                _set_active(r)
                look_through_rig(r)
                break
        _refresh_status()

    def _load_rig_into_controls(grp):
        if not rig_is_valid(grp):
            return
        base     = _grp_attr(grp, "tt_base_distance") or 0.0
        ogrp     = _resolve_node(_grp_attr(grp, "tt_offset_node"))
        dolly_v  = (cmds.getAttr(ogrp + ".translateZ") - base) if ogrp else 0.0
        ped_v    = _grp_attr(grp, "tt_pedestal")     or 0.0
        truck_v  = _grp_attr(grp, "tt_truck")        or 0.0
        roll_v   = _grp_attr(grp, "tt_roll")         or 0.0
        init_v   = _grp_attr(grp, "tt_initial_rot")  or 0.0
        fl_v     = _grp_attr(grp, "tt_focal_length") or 50.0
        for sl, fld, val in [
            (dolly_sl, dolly_fld, dolly_v),
            (ped_sl,   ped_fld,   ped_v),
            (truck_sl, truck_fld, truck_v),
            (roll_sl,  roll_fld,  roll_v),
            (init_sl,  init_fld,  init_v),
            (focal_sl, focal_fld, fl_v),
        ]:
            cmds.floatSlider(sl,  edit=True, value=val)
            cmds.floatField(fld, edit=True, value=val)
        srot = _resolve_node(_grp_attr(grp, "tt_start_rot_node"))
        if srot:
            pos = cmds.xform(srot, q=True, worldSpace=True, translation=True)
            cmds.floatField(piv_x, edit=True, value=pos[0])
            cmds.floatField(piv_y, edit=True, value=pos[1])
            cmds.floatField(piv_z, edit=True, value=pos[2])

    def _build_cmd():
        raw = cmds.textField(name_fld, q=True, text=True).strip()
        if not raw:
            cmds.warning("Enter a name for the rig.")
            return
        safe = raw.replace(" ", "_")
        fl   = cmds.floatField(fl_field,     q=True, value=True)
        sf   = cmds.intField(sf_build_fld,   q=True, value=True)
        nf   = cmds.intField(nf_build_fld,   q=True, value=True)
        grp  = build_turntable_rig(safe, focal_length=fl, start_frame=sf, num_frames=nf)
        _populate_dropdown()
        rigs = list_rigs()
        if grp in rigs:
            cmds.optionMenu(rig_dropdown, edit=True, select=rigs.index(grp) + 1)
        _set_active(grp)
        _refresh_status()

    def _update_frames_cmd():
        grp = _active_grp()
        if not rig_is_valid(grp):
            cmds.warning("TAOS: No active rig to update.")
            return
        sf = cmds.intField(sf_build_fld, q=True, value=True)
        nf = cmds.intField(nf_build_fld, q=True, value=True)
        update_frame_range(grp, start_frame=sf, num_frames=nf)

    def _delete_active():
        grp = _active_grp()
        if not grp:
            cmds.warning("No active rig.")
            return
        delete_rig(grp)
        _state["active_grp"] = None
        _populate_dropdown()

    def _look_through_active():
        grp = _active_grp()
        if grp and rig_is_valid(grp):
            look_through_rig(grp)

    def _reset_all_controls():
        grp = _active_grp()
        if not rig_is_valid(grp):
            return
        fl = _grp_attr(grp, "tt_focal_length") or 50.0
        for sl, fld, val in [
            (dolly_sl, dolly_fld, 0.0),
            (ped_sl,   ped_fld,   0.0),
            (truck_sl, truck_fld, 0.0),
            (roll_sl,  roll_fld,  0.0),
            (init_sl,  init_fld,  0.0),
            (focal_sl, focal_fld, fl),
        ]:
            cmds.floatSlider(sl,  edit=True, value=val)
            cmds.floatField(fld, edit=True, value=val)
        apply_dolly(grp, 0.0)
        apply_pedestal(grp, 0.0)
        apply_truck(grp, 0.0)
        apply_roll(grp, 0.0)
        apply_initial_rot(grp, 0.0)
        apply_focal_length(grp, fl)

    def _do_set_pivot():
        grp = _active_grp()
        if not rig_is_valid(grp):
            cmds.warning("No active rig.")
            return
        result = set_pivot_from_selection(grp)
        if result:
            cmds.floatField(piv_x, edit=True, value=result[0])
            cmds.floatField(piv_y, edit=True, value=result[1])
            cmds.floatField(piv_z, edit=True, value=result[2])

    def _set_locator_visibility(visible):
        for loc in (cmds.ls(type="locator") or []):
            try:
                cmds.setAttr(loc + ".visibility", visible)
            except Exception:
                pass

    def _select_cam_for_publish():
        """Select the active rig's camera, ready for publish / export selected."""
        grp = _active_grp()
        inc_shape = cmds.checkBox(include_shape_cb, q=True, value=True)
        result = select_rig_camera(grp, include_shape=inc_shape)
        if result:
            _refresh_cam_name_field(grp)   # keep field in sync after selection

    def _refresh_status():
        grp = _active_grp()
        if rig_is_valid(grp):
            n = _grp_attr(grp, "tt_rig_name") or _strip_ns(grp)
            cmds.text(status_txt, edit=True, label="[OK]  Active: {}".format(n))
        elif list_rigs():
            cmds.text(status_txt, edit=True, label="[--]  Select a rig above.")
        else:
            cmds.text(status_txt, edit=True, label="[--]  No rigs in scene.")

    _populate_dropdown()

    cmds.dockControl(DOCK_ID, label="Turntable Camera", area="right",
                     content=win, allowedArea=["right","left"], floating=False)

# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #
launch_ui()