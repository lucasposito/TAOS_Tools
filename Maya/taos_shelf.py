from maya import cmds
from StageFbx.gui import StageFbxGUI


def _null(*args):
    pass


def _stage_fbx(*args):
    StageFbxGUI.show_ui()


class TaosShelf(object):
    def __init__(self):
        self.name = 'TAOS'
        self.icon_path = ''

        self._clean_old_shelf()
        self.build()

    def build(self):
        self.add_button(label='StgFBX', command=_stage_fbx)
        # cmds.separator(style='single', w=10)

    def add_button(self, label, icon='commandButton.png', command=_null):
        cmds.setParent(self.name)
        if icon:
            icon = self.icon_path + icon
        cmds.shelfButton(width=37, height=37, image=icon, l=label, command=command,
                         imageOverlayLabel=label)

    def add_menu_item(self, parent, label, command=_null, icon=''):
        if icon:
            icon = self.icon_path + icon
        return cmds.menuItem(p=parent, l=label, c=command, i='')

    def _clean_old_shelf(self):
        try:
            cmds.deleteUI(self.name)
        except RuntimeError:
            pass

        cmds.shelfLayout(self.name, p='ShelfLayout')


TaosShelf()