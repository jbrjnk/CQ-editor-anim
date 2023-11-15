import datetime
from enum import Enum
from typing import List, Union
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QGridLayout, QPushButton, QLabel, QLineEdit, QSizePolicy, QApplication
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont, QIntValidator, QImage
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QMetaObject
from cq_editor.widgets.folder_path_picker import FolderPathPicker

from ..mixins import ComponentMixin, InjectedFunction
from tempfile import mkstemp
import os
import time

class StopRequestType(Enum):
    Nothing = 0
    CancelledByUser = 1 # User pressed 'cancel' button
    Finished = 2 # The script called 'animation_complete' function

class AnimationPanel(QWidget, ComponentMixin):
    _widthInput : QLineEdit      # width (in pixels) of captured frame
    _heightInput : QLineEdit     # height (in pixels) of captured frame
    _frameIndexInput : QLineEdit # current frame index (zero based)
    _runButton : QPushButton     # button to start capturing
    _cancelButton : QPushButton    # button to stop (cancel) capturing
    _refreshButton : QPushButton # button to refresh frame preview (renders just one frame with animation_isActive returning True and without saving to file)
    _statusLine : QLabel         # One text line to display user message / warning / error / progress info
    _outputDirInput : FolderPathPicker # Picker to choose output directory

    _isRunning : bool = False            # True if capturing is running
    _previewInProgress : bool = False    # True if just preview of one frame is to be rendered and displayed (without saving to file)
    _isActive : bool = False                # isRunning or previewInProgress 
    _stopRequest : StopRequestType = StopRequestType.Nothing # The reason why capturing has been stopped
    _startTime : float = 0              # Time when capturing started (to compute total execution time / fps)

    sigCaptureFrameRequest = pyqtSignal(str, int, int) # Requests viewer component to save frame to file (filePath, pixelWidth, pixelHeight)
    sigRenderFrameRequest = pyqtSignal()               # Requests debugger component to run script for the current frame
    sigActivated = pyqtSignal()                        # Notifies that isActive property has been changed to True
    sigDeactivated = pyqtSignal()                      # Notifies that isActive property has been changed to False

    def __init__(self,*args,**kwargs):
        super(AnimationPanel,self).__init__(*args,**kwargs)
        self.setupUI()
        self.createInjectedFunctions()

    def setupUI(self):
        grid : QGridLayout = QGridLayout()
        self.setLayout(grid)

        widthLabel = QLabel('Bitmap width:')
        widthValidator = QIntValidator(1, 6400)
        widthValidator.fixup = lambda input: "1280"
        self._widthInput = QLineEdit()
        self._widthInput.setText("1280")
        self._widthInput.setValidator(widthValidator)

        heightLabel = QLabel('Bitmap height:')
        self._heightInput = QLineEdit()
        heightValidator = QIntValidator(1, 3600)
        heightValidator.fixup = lambda input: "720"
        self._heightInput.setValidator(heightValidator)
        self._heightInput.setText("720")

        grid.addWidget(widthLabel, 0, 0)
        grid.addWidget(self._widthInput, 0, 1)
        grid.addWidget(heightLabel, 0, 2)
        grid.addWidget(self._heightInput, 0, 3)

        frameIndexLabel = QLabel('Frame index:')
        frameIndexValidator = QIntValidator(0, 10000)
        frameIndexValidator.fixup = lambda input: "0"
        self._frameIndexInput = QLineEdit()
        self._frameIndexInput.setValidator(frameIndexValidator)
        self._frameIndexInput.setText("0");
        grid.addWidget(frameIndexLabel, 1, 0)
        grid.addWidget(self._frameIndexInput, 1, 1)

        outputDirLabel = QLabel("Output folder")
        grid.addWidget(outputDirLabel, 2, 0)

        self._outputDirInput = FolderPathPicker()
        grid.addWidget(self._outputDirInput, 2, 1, 1, 3)

        self.bitmapPreview = BitmapPreview()
        self.bitmapPreview.setMinimumHeight(96)
        self.bitmapPreview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        grid.addWidget(self.bitmapPreview, 3, 0, 1, 4)

        self._statusLine = QLabel("")
        self._statusLine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._statusLine.setWordWrap(True)
        grid.addWidget(self._statusLine, 4, 0, 1, 4)

        self._refreshButton = QPushButton("Refresh preview")
        self._refreshButton.clicked.connect(self.rerenderPreview)
        grid.addWidget(self._refreshButton, 5, 0, 1, 2)

        self._runButton = QPushButton("Capture frames")
        self._runButton.clicked.connect(self.run)
        grid.addWidget(self._runButton, 5, 2, 1, 2)

        self._cancelButton = QPushButton("Cancel")
        self._cancelButton.clicked.connect(self.cancelByUser)
        self._cancelButton.setVisible(False)
        grid.addWidget(self._cancelButton, 5, 2, 1, 2)


    # Returns list of functions that are accessible within 3D model script
    def createInjectedFunctions(self):
        self._injectedFunctions = [InjectedFunction("animation_getFrameIndex", self.getFrameIndex),
                                   InjectedFunction("animation_isActive", self.isActive),
                                   InjectedFunction("animation_complete", self.complete)]

    @pyqtSlot(object,str)
    def addTraceback(self,exc_info,code):
        # if the script execution failed and capturing is running, stop it
        if self.isActive() and exc_info is not None:
            self.stop()
            frameIndex = self.getFrameIndex()
            self.setStatus(f'Execution failed on frame {frameIndex}', True)

    @pyqtSlot()
    def _requestRenderFrame(self):
        self.sigRenderFrameRequest.emit()


    @pyqtSlot(dict,bool)
    @pyqtSlot(dict)
    def addObjects(self,objects,clean=False,root=None):
        # display preview and store frame to file
        self.refreshPreview()
        self.setStatus('', False)
        if self._isRunning:
            try:
                # store frame to file
                frameIndex = int(self._frameIndexInput.text())
                fileName = os.path.join(self._outputDirInput.path, str(frameIndex).zfill(6) + ".png")
                self.captureToFile(fileName)
                self.setStatus(f'Frame {frameIndex}, {self.getFps(self._startTime, frameIndex + 1)} fps', False)

                # go to next frame
                frameIndex+=1

                # check stop conditions
                if self._stopRequest != StopRequestType.Nothing:
                    self.stop()
                    if self._stopRequest == StopRequestType.CancelledByUser:
                        self.setStatus(f'Cancelled by user after {self.formatDuration(self._startTime)}, {frameIndex} frames captured ({self.getFps(self._startTime, frameIndex)} fps)', False)
                    elif self._stopRequest == StopRequestType.Finished:
                        self.setStatus(f'Successfully finished in {self.formatDuration(self._startTime)}, {frameIndex} frames captured ({self.getFps(self._startTime, frameIndex)} fps)', False)
                    return

                self._frameIndexInput.setText(str(frameIndex))

                # enqueue rendering next frame
                QMetaObject.invokeMethod(self, '_requestRenderFrame', Qt.QueuedConnection)

            except Exception as ex:
                self.stop()
                self.setStatus(f'An exception {type(ex).__name__} occurred {ex}', True)

    def run(self):
        if self._outputDirInput.path is None or os.path.isdir(self._outputDirInput.path) == False:
            self.setStatus("Output directory doesn't esist", True)
            return
        self._cancelButton.setVisible(True)
        self._runButton.setVisible(False)
        self._stopRequest = StopRequestType.Nothing
        self._startTime = time.time()
        self.setIsRunning(True)

        # disable all widgets on animation panel (except 'cancel' button)
        for widget in self.children():
            if widget is not self._cancelButton:
                widget.setEnabled(False)
        self._frameIndexInput.setText("0") # start from the first frame (zero based indexing)
        self.setStatus("Running...", False)
        self.sigRenderFrameRequest.emit() # request rendering the first frame

    def cancelByUser(self):
        self._cancelButton.setVisible(False)
        self._runButton.setVisible(True)
        self._stopRequest = StopRequestType.CancelledByUser

    def stop(self):
        self._cancelButton.setVisible(False)
        self._runButton.setVisible(True)
        self.setIsRunning(False)
        self.setStatus("", False)
        for widget in self.children():
            widget.setEnabled(True)

    # Function accessible within 3d model script (should be called during execution of the last frame)
    def complete(self):
        if self._stopRequest == StopRequestType.Nothing:
            self._stopRequest = StopRequestType.Finished

    # Function accessible within 3D model script
    # Returns True if capturing is in progress or preview is being rendered
    # For example, the script can use this funciton to decide whether it should call or not
    def isActive(self) -> bool:
        return self._isActive

    # Function accessible withing 3D model script
    # Returns zero base index of the frame currently being captured
    def getFrameIndex(self) -> int:
        return int(self._frameIndexInput.text())

    # Displays message to user
    def setStatus(self, text : str, highlight : bool):
        self._statusLine.setText(text)
        if highlight:
            self._statusLine.setStyleSheet("color: red")
        else:
            self._statusLine.setStyleSheet("color: black")

    # Format elapsed duration as string (00:00:00)
    def formatDuration(self, beginTime : float) -> str:
        endTime = time.time()
        elapsed = endTime - beginTime
        return str(datetime.timedelta(seconds=round(elapsed)))

    # Compute FPS
    def getFps(self, beginTime : float, framesCount : int) -> float:
        endTime = time.time()
        elapsed = endTime - beginTime
        return round(framesCount / elapsed, 2)

    def rerenderPreview(self):
        self.setPreviewInProgress(True)
        self.sigRenderFrameRequest.emit()
        self.setPreviewInProgress(False)

    # Refresh preview
    def refreshPreview(self):
        tempFileName = None
        try:
            # Create temp file to store preview
            # In my opinion there is currently no other way how to convert Image_PixMap to QImage directly, without storing it to a file
            # Image_AlienPixMap.Data returns just single byte, not array (probably same issue as https://github.com/CadQuery/pywrap/issues/51 ?)
            fd, tempFileName = mkstemp(".png")
            os.close(fd)
            self.captureToFile(tempFileName)
        finally:
            os.remove(tempFileName)
            self._previewInProgress = False

    # Store current frame to file and display it as preview
    def captureToFile(self, fileName : str):
            frameW = int(self._widthInput.text())
            frameH = int(self._heightInput.text())
            self.sigCaptureFrameRequest.emit(fileName, frameW, frameH)
            framePreview = QPixmap(fileName)
            self.bitmapPreview.setPixmap(framePreview)

    def setPreviewInProgress(self, isInProgress : bool):
        self._previewInProgress = isInProgress
        self.updateIsActive()

    def setIsRunning(self, isRunning : bool):
        self._isRunning = isRunning
        self.updateIsActive()

    def updateIsActive(self):
        newIsActive = self._isRunning or self._previewInProgress
        if newIsActive != self._isActive:
            self._isActive = newIsActive
            if self._isActive:
                self.sigActivated.emit();
            else:
                self.sigDeactivated.emit()

# Component to display frame preview
class BitmapPreview(QWidget):
    pixmap : QImage = None
    def __init__(self):
        super().__init__()

    def setPixmap(self, pixmap : QPixmap):
        self.pixmap : QPixmap = pixmap
        self.update()

    def paintEvent(self, event):
        if self.pixmap is not None:
            qp = QPainter()
            qp.begin(self)
            previewPixmap = self.pixmap
            scaleX = self.width() / previewPixmap.width()
            scaleY = self.height() / previewPixmap.height()
            scale = min(scaleX, scaleY)
            w = round(previewPixmap.width() * scale)
            h = round(previewPixmap.height() * scale)
            x = round((self.width() - w) / 2)
            y = round((self.height() - h) / 2)
            qp.drawPixmap(x, y, w, h, previewPixmap)
            qp.end()

