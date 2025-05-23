from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QListView
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, pyqtSignal

class EditorWidget(QListWidget):
    wordClicked = pyqtSignal(float)  # 新增：点击字时发射该字的起始时间
    wordDeleted = pyqtSignal(list)  # 新增：发射被删除的索引列表
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setFont(QFont("PingFang SC", 16))
        self.setMinimumHeight(120)
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(2)
        self.setSelectionRectVisible(True)
        self.editable_words = []
        self.itemClicked.connect(self._on_item_clicked)

    def refresh(self, editable_words, cursor_pos=None, selection_len=0):
        self.clear()
        self.editable_words = editable_words  # 保存用于高亮
        for idx, w in enumerate(editable_words):
            item = QListWidgetItem(w['word'])
            if w.get('is_gap'):
                item.setBackground(QColor('#eee'))
            self.addItem(item)
        if cursor_pos is not None:
            self.setCurrentRow(min(max(cursor_pos, 0), self.count()-1))
            if selection_len > 0:
                for i in range(cursor_pos, min(cursor_pos+selection_len, self.count())):
                    self.item(i).setSelected(True)

    def _on_item_clicked(self, item):
        idx = self.row(item)
        if 0 <= idx < len(self.editable_words):
            time = self.editable_words[idx]['start']
            self.wordClicked.emit(time)

    def highlight_word_at(self, time):
        # 找到当前时间属于哪个字
        for i, w in enumerate(self.editable_words):
            if w['start'] <= time < w['end']:
                self.setCurrentRow(i)
                self.scrollToItem(self.item(i))
                return
        self.setCurrentRow(-1)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            selected = self.selectedIndexes()
            if selected:
                idxs = sorted([i.row() for i in selected], reverse=True)
                self.wordDeleted.emit(idxs)
                return
        super().keyPressEvent(event) 