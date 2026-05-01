from maya import cmds


# ---------------------------------------------------------------------------
# Tool callbacks
# ---------------------------------------------------------------------------

def _mocap_importer(*args):
    from MocapImporter import mocap_importer
    mocap_importer.build_ui()


def _playblast_tt(*args):
    from PlayblastTT import Playblast_TT
    Playblast_TT.launch_ui()

def _character_timecode(*args):
    from CharacterTimecode import character_timecode
    character_timecode.launch_ui()


# ---------------------------------------------------------------------------
# Shelf definition
# ---------------------------------------------------------------------------

SHELF_BUTTONS = [
    
    {'label': 'CamTT', 'command': _playblast_tt,   'icon': 'camera.closed.svg'},
    {'label': 'Mocap', 'command': _mocap_importer, 'icon': 'animateSnapshot.png'},
    {'label': 'Timecode', 'command': _character_timecode, 'icon': 'camera.svg'},
]


class TaosShelf(object):
    NAME = 'TAOS'
    ICON_PATH = ''
    DEFAULT_ICON = 'commandButton.png'

    def __init__(self):
        self._reset_shelf()
        self._build()

    def _reset_shelf(self):
        if cmds.shelfLayout(self.NAME, exists=True):
            cmds.deleteUI(self.NAME)
        cmds.shelfLayout(self.NAME, p='ShelfLayout')

    def _build(self):
        for entry in SHELF_BUTTONS:
            if entry.get('separator'):
                self._add_separator()
            else:
                self._add_button(**entry)

    def _add_button(self, label, command, icon=None, **kwargs):
        icon = (self.ICON_PATH + icon) if icon else self.DEFAULT_ICON
        return cmds.shelfButton(
            parent=self.NAME,
            width=37,
            height=37,
            image=icon,
            label=label,
            command=command,
            imageOverlayLabel=label,
        )

    def _add_separator(self):
        cmds.separator(
            parent=self.NAME,
            style='single',
            horizontal=False,
            width=10,
            height=37,
        )


def install():
    """Entry point — call from userSetup.py."""
    TaosShelf()


if __name__ == '__main__':
    install()