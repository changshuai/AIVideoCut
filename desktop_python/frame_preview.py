from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QImage

class FramePreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent;")
        self.hide()

    def show_frame(self, frame_np):
        # frame_np: numpy array (H, W, 3), RGB
        h, w, ch = frame_np.shape
        bytes_per_line = ch * w
        qimg = QImage(frame_np.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.label.setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.label.resize(self.size())
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.hide()
        super().mousePressEvent(event)

    def resizeEvent(self, event):
        if self.label.pixmap():
            self.label.setPixmap(self.label.pixmap().scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.label.resize(self.size())
        super().resizeEvent(event) 