from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance

from maya import OpenMayaUI


def maya_window():
    ptr = OpenMayaUI.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class StageFbxGUI(QtWidgets.QDialog):
    gui_instance = None

    @classmethod
    def show_ui(cls):
        if not cls.gui_instance:
            cls.gui_instance = StageFbxGUI()

        if cls.gui_instance.isHidden():
            cls.gui_instance.show()
        else:
            cls.gui_instance.raise_()
            cls.gui_instance.activateWindow()

    def __init__(self, parent=maya_window()):
        super(StageFbxGUI, self).__init__(parent)

        self.setWindowTitle("Stage FBX")
        self.setMinimumWidth(280)

        self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)

        self.create_widgets()

    def create_widgets(self):
        main_layout = QtWidgets.QVBoxLayout(self)
