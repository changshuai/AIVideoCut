from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QPixmap, QImage
from PyQt5.QtCore import Qt, pyqtSignal
import threading
from moviepy.editor import VideoFileClip
import numpy as np

class TimelineWidget(QWidget):
    previewFrameChanged = pyqtSignal(object)  # QPixmap or None
    jumpToPosition = pyqtSignal(float)  # 新增：跳转到某个时间点（秒）
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []  # [{word, start, end, is_gap}]
        self.duration = 1.0
        self.position = 0.0
        self.setMinimumHeight(40)
        self.setMouseTracking(True)
        self.video_path = None
        self.thumbnails = []  # [(time, QPixmap)]
        self.thumb_interval = 1.0
        self.thumb_height = 40
        self.hover_pixmap = None
        self.hover_pos = None
        self._dragging = False

    def set_words(self, words, duration):
        self.words = words
        self.duration = max(duration, 1e-3)
        self.update()

    def set_position(self, pos):
        self.position = pos
        self.update()

    def set_video(self, video_path, duration):
        self.video_path = video_path
        self.duration = duration
        self.thumbnails = []
        self._start_extract_thumbnails()

    def _start_extract_thumbnails(self):
        if not self.video_path or self.duration <= 0:
            return
        width = self.width()
        n_thumbs = max(1, width // 40)  # 每40像素一帧
        interval = self.duration / n_thumbs
        self.thumb_interval = interval
        self.thumb_height = 40  # 固定帧带高度
        self.thumbnails = [None] * n_thumbs
        def extract():
            clip = VideoFileClip(self.video_path)
            for i in range(n_thumbs):
                t = min(self.duration, i * interval)
                frame = clip.get_frame(t)
                img = QImage(frame, frame.shape[1], frame.shape[0], QImage.Format_RGB888).rgbSwapped()
                pix = QPixmap.fromImage(img).scaledToHeight(self.thumb_height, Qt.SmoothTransformation)
                self.thumbnails[i] = (t, pix)
                self.update()
        threading.Thread(target=extract, daemon=True).start()

    def resizeEvent(self, event):
        self._start_extract_thumbnails()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor('#222'))
        # 缩略图帧带垂直居中
        band_h = self.thumb_height
        band_y = (h - band_h) // 2
        if self.thumbnails:
            n = len(self.thumbnails)
            for i, thumb in enumerate(self.thumbnails):
                if thumb is not None:
                    t, pix = thumb
                    x1 = int(i / n * w)
                    x2 = int((i+1) / n * w)
                    target_width = max(1, x2 - x1)
                    painter.drawPixmap(x1, band_y, target_width, band_h, pix)
        # 时间刻度
        duration = self.duration
        if duration > 0:
            # 计算刻度间隔
            if duration <= 30:
                step = 1
            elif duration <= 120:
                step = 5
            else:
                step = 10
            font = QFont()
            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QPen(QColor('#999'), 1))
            for t in range(0, int(duration)+1, step):
                x = int(t / duration * w)
                painter.drawLine(x, 0, x, 8)
                painter.drawText(x-10, 0, 20, 12, Qt.AlignCenter, f"{t}s")
        # 绘制每个word/空隙区块
        # for word in self.words:
        #     x1 = int(word['start'] / self.duration * w)
        #     x2 = int(word['end'] / self.duration * w)
        #     color = QColor('#bae7ff') if not word['is_gap'] else QColor('#444')
        #     painter.fillRect(x1, 10, max(x2-x1,1), h-20, color)
        # 当前播放进度线
        px = int(self.position / self.duration * w)
        pen = QPen(QColor('#fa541c'), 2)
        painter.setPen(pen)
        painter.drawLine(px, 0, px, h)

    def enterEvent(self, event):
        print("[LOG] enterEvent")
        super().enterEvent(event)

    def leaveEvent(self, event):
        print("[LOG] leaveEvent")
        self.hover_pixmap = None
        self.hover_pos = None
        self.previewFrameChanged.emit(None)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        print(f"[LOG] mousePressEvent: button={event.button()}, pos=({event.x()},{event.y()})")
        has_words = bool(self.words)
        x = event.x()
        w = self.width()
        t = x / w * self.duration
        print(f"[LOG] mousePressEvent: x={x}, t={t:.2f}, has_words={has_words}")
        if event.button() == Qt.LeftButton:
            self._dragging = True
            print(f"[LOG] Start dragging at t={t:.2f}")
            self.jumpToPosition.emit(t)
        elif event.button() == Qt.RightButton:
            if has_words and hasattr(self, 'fullResPreviewRequest'):
                self.fullResPreviewRequest(t)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        #print(f"[LOG] mouseMoveEvent: pos=({event.x()},{event.y()}), dragging={self._dragging}")
        has_words = bool(self.words)
        if self._dragging and event.buttons() & Qt.LeftButton:
            x = event.x()
            w = self.width()
            t = x / w * self.duration
            #print(f"[LOG] mouseMoveEvent: dragging, x={x}, t={t:.2f}")
            self.jumpToPosition.emit(t)
        if has_words and self.video_path and self.thumbnails:
            x = event.x()
            w = self.width()
            t = x / w * self.duration
            idx = int(t / self.thumb_interval)
            if 0 <= idx < len(self.thumbnails) and self.thumbnails[idx]:
                _, pix = self.thumbnails[idx]
                self.hover_pixmap = pix
                self.hover_pos = (x, 0)
                self.previewFrameChanged.emit(pix)
            else:
                self.hover_pixmap = None
                self.hover_pos = None
                self.previewFrameChanged.emit(None)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        print(f"[LOG] mouseReleaseEvent: button={event.button()}, pos=({event.x()},{event.y()})")
        if event.button() == Qt.LeftButton:
            print(f"[LOG] mouseReleaseEvent: dragging end")
            self._dragging = False
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        print(f"[LOG] mouseDoubleClickEvent: button={event.button()}, pos=({event.x()},{event.y()})")
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        print(f"[LOG] wheelEvent: delta={event.angleDelta()}")
        super().wheelEvent(event) 

    def fullResPreviewRequest(self, t):
        if not keep_idxs or len(''.join([orig_words[i]['word'] for i in keep_idxs])) < len(llm_text_clean):
            debug_info = (
                f"原文words: {[w['word'] for w in orig_words]}\n"
                f"大模型原文: {llm_text}\n"
                f"大模型去标点: {llm_text_clean}\n"
                f"已匹配: {''.join([orig_words[i]['word'] for i in keep_idxs])}\n"
            )
            QMessageBox.warning(self, '大模型优化', '大模型返回内容与原文对齐失败，请重试或检查API返回。\\n\\n' + debug_info)
            return 