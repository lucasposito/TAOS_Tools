import maya.cmds as cmds

if not cmds.about(batch=True):
    cmds.evalDeferred('import taos_shelf; taos_shelf.install()')