from PySide6 import QtWidgets, QtCore, QtGui
from shiboken6 import wrapInstance

from maya import OpenMayaUI


solve_path = r'Q:\Shared drives\TAOS\mocap'


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
        self.make_connections()

    def create_widgets(self):
        self.take_name = QtWidgets.QLineEdit()
        self.take_name.setPlaceholderText("Take Name")

        self.solve_group = QtWidgets.QButtonGroup(self)
        solve_layout = QtWidgets.QHBoxLayout()

        for i, label in enumerate(['Live Solve', 'Final Solve']):
            btn = QtWidgets.QRadioButton(label)
            if i == 0:
                btn.setChecked(True)
            self.solve_group.addButton(btn, i)
            solve_layout.addWidget(btn)

        self.takes_list = QtWidgets.QListWidget()
        self.select_button = QtWidgets.QPushButton("SELECT")

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.take_name)
        main_layout.addLayout(solve_layout)
        main_layout.addWidget(self.takes_list)
        main_layout.addWidget(self.select_button)

    def make_connections(self):
        self.select_button.clicked.connect(self.print_everything)

    def print_everything(self):
        take_name = self.take_name.text()
        solve_type = self.solve_group.checkedButton().text()
        print(f"Take Name: {take_name}, Solve Type: {solve_type}")