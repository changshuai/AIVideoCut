from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QStyle, QLabel
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl, Qt

class VideoPlayerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.player.setVideoOutput(self.video_widget)
        # 播放/暂停按钮直接加在视频widget上
        self.play_pause_btn = QPushButton(self.video_widget)
        self.play_pause_btn.setFixedSize(60, 60)
        self.play_pause_btn.setText("")
        self.play_pause_btn.setStyleSheet('QPushButton { background: transparent; border: none; } QPushButton:hover { background: transparent; }')
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        self.play_pause_btn.hide()
        self.player.stateChanged.connect(self.update_play_pause_btn)
        self.update_play_pause_btn(self.player.state())
        self.video_widget.installEventFilter(self)
        # 预览帧label，居中覆盖在视频上
        self.preview_label = QLabel(self.video_widget)
        self.preview_label.setStyleSheet('background: transparent; border: none;')
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.hide()
        self.resizeEvent(None)

    def toggle_play_pause(self):
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def update_play_pause_btn(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_pause_btn.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def eventFilter(self, obj, event):
        if obj == self.video_widget:
            if event.type() == event.Enter:
                self.play_pause_btn.show()
            elif event.type() == event.Leave:
                self.play_pause_btn.hide()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        # 按钮始终居中
        vw = self.video_widget.width()
        vh = self.video_widget.height()
        bw = self.play_pause_btn.width()
        bh = self.play_pause_btn.height()
        self.play_pause_btn.move((vw-bw)//2, (vh-bh)//2)
        super().resizeEvent(event)
        # 保证预览帧始终居中
        if self.preview_label.isVisible() and self.preview_label.pixmap():
            pw, ph = self.preview_label.pixmap().width(), self.preview_label.pixmap().height()
            self.preview_label.setGeometry((vw-pw)//2, (vh-ph)//2, pw, ph)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.toggle_play_pause()
        else:
            super().keyPressEvent(event)

    def set_media(self, file_path):
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))

    def set_position(self, ms):
        self.player.setPosition(ms)

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def show_preview_frame(self, pixmap):
        self.preview_label.hide() 
        # if pixmap is not None:
        #     self.preview_label.setPixmap(pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        #     # 居中
        #     vw, vh = self.video_widget.width(), self.video_widget.height()
        #     pw, ph = self.preview_label.pixmap().width(), self.preview_label.pixmap().height()
        #     self.preview_label.setGeometry((vw-pw)//2, (vh-ph)//2, pw, ph)
        #     self.preview_label.show()
        # else:
        #     self.preview_label.hide()

    def hide_preview_frame(self):
        self.preview_label.hide() 