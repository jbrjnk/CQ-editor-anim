from PyQt5.QtWidgets import QWidget, QLineEdit, QPushButton, QHBoxLayout, QSizePolicy
from cq_editor.utils import get_save_dirname

class FolderPathPicker(QWidget):
    path : str = None

    def __init__(self):
        super().__init__()
        hLayout = QHBoxLayout()
        hLayout.setSpacing(0)
        hLayout.setContentsMargins(0,0,0,0)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setLayout(hLayout)
        
        pathInput = QLineEdit()
        pathInput.setEnabled(False)
        pathInput.setText("<not selected>")
        hLayout.addWidget(pathInput)

        selectButton = QPushButton("Select ...")
        def onSelectButtonClicked():
            dirname = get_save_dirname(pathInput.text())
            if dirname is not None:
                pathInput.setText(dirname)
                self.path = dirname

        selectButton.clicked.connect(onSelectButtonClicked)
        hLayout.addWidget(selectButton)
