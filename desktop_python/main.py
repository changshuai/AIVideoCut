# =============================================
# AI智能剪辑口播视频工具 桌面端 v1.1.0
# 主要更新：
# - 编辑器重构为QListWidget横向流式排列，所有字/词/空隙为块状item，空隙整体为一块
# - 支持点击高亮、批量选择、Delete/Backspace删除
# - 禁止插入/粘贴/输入
# - 自动换行，交互体验大幅提升
# =============================================
import sys
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QLabel, QMessageBox, QScrollArea, QFrame, QTextEdit, QListView
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, QRectF, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QTextCursor, QTextCharFormat, QKeySequence
from moviepy.editor import VideoFileClip, concatenate_videoclips
import os
import signal

ASR_API = 'http://localhost:8000/asr'

class WordItem(QListWidgetItem):
    def __init__(self, word, start, end, is_gap=False):
        super().__init__(word)
        self.word = word
        self.start = start
        self.end = end
        self.is_gap = is_gap

class TimelineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.words = []  # [{word, start, end, is_gap}]
        self.duration = 1.0
        self.position = 0.0
        self.setMinimumHeight(40)
        self.setMouseTracking(True)

    def set_words(self, words, duration):
        self.words = words
        self.duration = max(duration, 1e-3)
        self.update()

    def set_position(self, pos):
        self.position = pos
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w, h = self.width(), self.height()
        # 背景
        painter.fillRect(0, 0, w, h, QColor('#f5f5f5'))
        # 绘制每个word/空隙区块
        for word in self.words:
            x1 = int(word['start'] / self.duration * w)
            x2 = int(word['end'] / self.duration * w)
            color = QColor('#bae7ff') if not word['is_gap'] else QColor('#eee')
            painter.fillRect(x1, 10, max(x2-x1,1), h-20, color)
        # 当前播放进度线
        px = int(self.position / self.duration * w)
        pen = QPen(QColor('#fa541c'), 2)
        painter.setPen(pen)
        painter.drawLine(px, 0, px, h)

    def mousePressEvent(self, event):
        if not self.words:
            return
        x = event.x()
        w = self.width()
        t = x / w * self.duration
        self.parent().on_timeline_clicked(t)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('AI智能剪辑口播视频工具 - 桌面版')
        self.resize(1100, 800)
        self.video_path = None
        self.asr_result = []
        self.words = []  # [{word, start, end, is_gap}]
        self.deleted_ranges = []
        self.selected_edit_idx = (-1, -1)  # (行, 列)
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        # 左侧：视频播放器
        left_layout = QVBoxLayout()
        self.video_widget = QVideoWidget()
        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.player.setVideoOutput(self.video_widget)
        left_layout.addWidget(self.video_widget)
        self.open_btn = QPushButton('选择音/视频文件')
        self.open_btn.clicked.connect(self.open_file)
        left_layout.addWidget(self.open_btn)
        self.export_btn = QPushButton('导出剪辑视频')
        self.export_btn.clicked.connect(self.export_video)
        left_layout.addWidget(self.export_btn)
        # 右侧：编辑器+时间轴
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel('只能删除的编辑器（点击定位，Delete删除）：'))
        # 用QListWidget替换QTextEdit
        self.list_edit = QListWidget()
        self.list_edit.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_edit.setFont(QFont("PingFang SC", 16))
        self.list_edit.setMinimumHeight(120)
        # 横向流式排列，自动换行
        self.list_edit.setViewMode(QListView.IconMode)
        self.list_edit.setFlow(QListView.LeftToRight)
        self.list_edit.setWrapping(True)
        self.list_edit.setResizeMode(QListView.Adjust)
        self.list_edit.setSpacing(2)
        right_layout.addWidget(self.list_edit, 2)
        right_layout.addWidget(QLabel('可视化时间轴：'))
        self.timeline = TimelineWidget(self)
        right_layout.addWidget(self.timeline)
        main_layout.addLayout(left_layout, 2)
        main_layout.addLayout(right_layout, 3)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        # 事件过滤器
        self.list_edit.installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timeline)
        self.timer.start(100)
        self.selected_idx = 0

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, '选择音/视频文件', '', '视频/音频 (*.mp4 *.mov *.avi *.mp3 *.wav *.m4a)')
        if not file_path:
            self.load_test_data()
            return
        self.video_path = file_path
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.player.pause()
        self.upload_and_asr(file_path)

    def load_test_data(self):
        # 模拟ASR后端返回结构
        self.asr_result = [
            {
                'start': 0.0, 'end': 1.2, 'text': '你好，',
                'words': [
                    {'word': '你', 'start': 0.0, 'end': 0.4},
                    {'word': '好', 'start': 0.4, 'end': 0.8},
                    {'word': '，', 'start': 0.8, 'end': 1.2},
                ]
            },
            {
                'start': 1.2, 'end': 2.0, 'text': '[0.800 sec]',
                'words': [
                    {'word': '[0.800 sec]', 'start': 1.2, 'end': 2.0}
                ]
            },
            {
                'start': 2.0, 'end': 3.5, 'text': '世界！',
                'words': [
                    {'word': '世', 'start': 2.0, 'end': 2.7},
                    {'word': '界', 'start': 2.7, 'end': 3.2},
                    {'word': '！', 'start': 3.2, 'end': 3.5},
                ]
            },
            {
                'start': 3.5, 'end': 4.0, 'text': '[0.500 sec]',
                'words': [
                    {'word': '[0.500 sec]', 'start': 3.5, 'end': 4.0}
                ]
            },
            {
                'start': 4.0, 'end': 6.0, 'text': '欢迎使用AI剪辑',
                'words': [
                    {'word': '欢', 'start': 4.0, 'end': 4.5},
                    {'word': '迎', 'start': 4.5, 'end': 5.0},
                    {'word': '使', 'start': 5.0, 'end': 5.5},
                    {'word': '用', 'start': 5.5, 'end': 6.0},
                ]
            }
        ]
        self.words = []
        for seg in self.asr_result:
            is_gap = seg['text'].startswith('[') and seg['text'].endswith('sec]')
            for w in seg['words']:
                self.words.append({
                    'word': w['word'],
                    'start': w['start'],
                    'end': w['end'],
                    'is_gap': is_gap
                })
        # 初始化 editable_words
        self.editable_words = []
        for seg in self.asr_result:
            for w in seg['words']:
                self.editable_words.append(w)
        self.refresh_edit_text()
        # 设置时间轴
        duration = 0
        if self.words:
            duration = max(w['end'] for w in self.words)
        self.timeline.set_words(self.words, duration)

    def upload_and_asr(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                resp = requests.post(ASR_API, files=files)
            resp.raise_for_status()
            data = resp.json()['result']
            self.asr_result = data
            self.words = []
            for seg in data:
                is_gap = seg['text'].startswith('[') and seg['text'].endswith('sec]')
                for w in seg['words']:
                    self.words.append({
                        'word': w['word'],
                        'start': w['start'],
                        'end': w['end'],
                        'is_gap': is_gap
                    })
            # 初始化 editable_words
            self.editable_words = []
            for seg in self.asr_result:
                for w in seg['words']:
                    self.editable_words.append(w)
            self.refresh_edit_text()
            # 设置时间轴
            duration = 0
            if self.words:
                duration = max(w['end'] for w in self.words)
            self.timeline.set_words(self.words, duration)
        except Exception as e:
            QMessageBox.critical(self, 'ASR失败', f'语音识别失败: {e}')

    def refresh_edit_text(self, cursor_pos=None, selection_len=0):
        # 用QListWidget刷新显示
        self.list_edit.clear()
        for idx, w in enumerate(self.editable_words):
            item = QListWidgetItem(w['word'])
            # 空隙高亮灰色
            if w.get('is_gap'):
                item.setBackground(QColor('#eee'))
            self.list_edit.addItem(item)
        # 恢复选区
        if cursor_pos is not None:
            self.list_edit.setCurrentRow(min(max(cursor_pos, 0), self.list_edit.count()-1))
            if selection_len > 0:
                for i in range(cursor_pos, min(cursor_pos+selection_len, self.list_edit.count())):
                    self.list_edit.item(i).setSelected(True)

    def eventFilter(self, obj, event):
        if obj == self.list_edit:
            if event.type() == event.KeyPress:
                selected = self.list_edit.selectedIndexes()
                # 防止空列表
                if not self.editable_words:
                    print(f"[LOG] 空列表，无法删除。")
                    return True
                if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                    # 支持批量删除
                    rows = sorted(set(idx.row() for idx in selected), reverse=True)
                    if not rows and self.list_edit.currentRow() >= 0:
                        rows = [self.list_edit.currentRow()]
                    print(f"[LOG] 删除rows: {rows}")
                    for row in rows:
                        if 0 <= row < len(self.editable_words):
                            del self.editable_words[row]
                    self.refresh_edit_text(cursor_pos=min(rows[0], len(self.editable_words)-1) if rows else 0)
                    return True
                # 禁止输入/粘贴
                if event.text():
                    print(f"[LOG] 禁止输入: {event.text()}")
                    return True
            if event.type() == event.ShortcutOverride and event.matches(QKeySequence.Paste):
                print(f"[LOG] 禁止粘贴")
                return True
        return super().eventFilter(obj, event)

    def export_video(self):
        if not self.video_path or not self.editable_words:
            QMessageBox.warning(self, '导出失败', '请先选择视频并完成编辑')
            return
        # 合并连续区间
        keep_ranges = []
        for w in self.editable_words:
            if not keep_ranges or abs(w['start'] - keep_ranges[-1][1]) > 1e-3:
                keep_ranges.append([w['start'], w['end']])
            else:
                keep_ranges[-1][1] = w['end']
        save_path, _ = QFileDialog.getSaveFileName(self, '保存剪辑后视频', '', 'MP4文件 (*.mp4)')
        if not save_path:
            return
        try:
            clip = VideoFileClip(self.video_path)
            subclips = [clip.subclip(start, end) for start, end in keep_ranges]
            final = concatenate_videoclips(subclips)
            final.write_videofile(save_path, codec='libx264', audio_codec='aac')
            QMessageBox.information(self, '导出成功', f'剪辑后视频已保存到：{save_path}')
        except Exception as e:
            QMessageBox.critical(self, '导出失败', f'剪辑失败: {e}')

    def update_timeline(self):
        # 定时刷新时间轴播放进度
        if self.player and self.player.duration() > 0:
            pos = self.player.position() / 1000.0
            duration = self.player.duration() / 1000.0
            self.timeline.set_position(pos)
            self.timeline.duration = duration

    def on_timeline_clicked(self, t):
        # 点击时间轴跳转
        if self.player:
            self.player.setPosition(int(t * 1000))
            self.player.pause()

if __name__ == '__main__':
    import sys
    import signal
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    # 让 Ctrl+C 能终止 Qt 应用
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    sys.exit(app.exec_()) 