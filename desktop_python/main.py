# -*- coding: utf-8 -*-
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
    QListWidget, QListWidgetItem, QLabel, QMessageBox, QScrollArea, QFrame, QTextEdit, QListView, QToolButton
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, QRectF, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QTextCursor, QTextCharFormat, QKeySequence
from moviepy.editor import VideoFileClip, concatenate_videoclips
import os
import signal
import copy
from timeline_widget import TimelineWidget
from editor_widget import EditorWidget
from video_player import VideoPlayerWidget
from frame_preview import FramePreviewWidget
import threading
import numpy as np
import tempfile
import re
import json  # 新增

ASR_API = 'http://localhost:8000/asr'

def safe_str(s):
    if isinstance(s, bytes):
        return s.decode('utf-8', errors='replace')
    try:
        return str(s)
    except Exception:
        return repr(s)

class WordItem(QListWidgetItem):
    def __init__(self, word, start, end, is_gap=False):
        super().__init__(word)
        self.word = word
        self.start = start
        self.end = end
        self.is_gap = is_gap

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
        self.undo_stack = []  # 撤销栈
        self.last_open_dir = os.path.expanduser('~')
        self.last_manual_seek_time = None
        self.user_clicked_word = False  # 新增：标记是否用户点击了文字
        self._last_preview_tempfile = None  # 记录上一次预览的临时文件路径
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        # 左侧：视频播放器+时间轴
        left_layout = QVBoxLayout()
        # 工具栏按钮（横向排列在播放器上方）
        tool_btn_layout = QHBoxLayout()
        self.open_btn = QToolButton()
        self.open_btn.setText('选择音/视频')
        self.open_btn.clicked.connect(self.open_file)
        tool_btn_layout.addWidget(self.open_btn)
        self.asr_btn = QToolButton()
        self.asr_btn.setText('AI口播识别')
        self.asr_btn.clicked.connect(self.start_asr)
        tool_btn_layout.addWidget(self.asr_btn)
        self.export_btn = QToolButton()
        self.export_btn.setText('导出剪辑视频')
        self.export_btn.clicked.connect(self.export_video)
        tool_btn_layout.addWidget(self.export_btn)
        self.undo_btn = QToolButton()
        self.undo_btn.setText('撤销（Ctrl+Z）')
        self.undo_btn.clicked.connect(self.undo)
        tool_btn_layout.addWidget(self.undo_btn)
        left_layout.addLayout(tool_btn_layout)
        # 视频播放器和时间轴
        self.video_player = VideoPlayerWidget()
        left_layout.addWidget(self.video_player, 3)
        self.timeline = TimelineWidget(self)
        print("[LOG] MainWindow: TimelineWidget created", self.timeline)
        self.timeline.jumpToPosition.connect(self.on_timeline_jump)
        print("[LOG] MainWindow: jumpToPosition signal connected")
        left_layout.addWidget(self.timeline, 1)
        self.timeline.previewFrameChanged.connect(self.video_player.show_preview_frame)
        # 全屏帧预览控件
        self.frame_preview = FramePreviewWidget(self)
        # 右键帧带全屏预览
        self.timeline.fullResPreviewRequest = self.full_res_preview_request
        # 右侧：编辑器
        right_layout = QVBoxLayout()
        # 新增：大模型优化按钮
        self.llm_btn = QPushButton('AI优化文案')
        self.llm_btn.clicked.connect(self.llm_optimize)
        self.llm_btn.setEnabled(False)  # 初始不可用
        right_layout.addWidget(self.llm_btn)
        right_layout.addWidget(QLabel('只能删除的编辑器（点击定位，Delete删除）：'))
        self.editor = EditorWidget()
        # --- 联动：点击文字跳转视频和帧带 ---
        self.editor.wordClicked.connect(self.on_word_clicked)
        self.editor.wordDeleted.connect(self.on_word_deleted)
        right_layout.addWidget(self.editor, 2)
        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 1)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        # 事件过滤器
        self.editor.installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timeline)
        self.timer.start(100)
        self.selected_idx = 0
        # 保持按钮状态同步
        self.video_player.player.stateChanged.connect(self.update_play_pause_btn)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, '选择音/视频文件',
            self.last_open_dir,
            '视频/音频 (*.mp4 *.mov *.avi *.mp3 *.wav *.m4a)'
        )
        if not file_path:
            self.load_test_data()  # 用户取消时加载测试数据
            return
        self.last_open_dir = os.path.dirname(file_path)
        self.video_path = file_path
        self.video_player.player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.video_player.player.pause()
        # 获取视频时长并设置timeline缩略图
        try:
            clip = VideoFileClip(file_path)
            duration = clip.duration
            print(f"[LOG] 视频时长: {duration}s")
        except Exception as e:
            print(f"[LOG] 获取视频时长失败: {e}")
            duration = 0
        self.timeline.set_video(self.video_path, duration)
        self.editor.refresh([{'word': '请点击"AI口播识别"按钮进行识别...'}])

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
            self.editor.refresh(self.editable_words)
        self.refresh_llm_btn()
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
            print("[ASR识别返回完整结果]", data)  # 新增日志
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
            self.editor.refresh(self.editable_words)
            self.refresh_llm_btn()
            # 设置时间轴
            duration = 0
            if self.words:
                duration = max(w['end'] for w in self.words)
            self.timeline.set_words(self.words, duration)
        except Exception as e:
            QMessageBox.critical(self, 'ASR失败', f'语音识别失败: {e}')
        finally:
            self.asr_btn.setEnabled(True)  # 无论成功失败都恢复按钮

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
        if self.video_player.player and self.video_player.player.duration() > 0:
            pos = self.video_player.player.position() / 1000.0
            duration = self.video_player.player.duration() / 1000.0
            self.timeline.set_position(pos)
            self.timeline.duration = duration
            if self.editable_words:
                if not self.user_clicked_word:
                    self.editor.highlight_word_at(pos)
            # 如果视频在播放，自动高亮可以恢复
            if self.video_player.player.state() == QMediaPlayer.PlayingState:
                self.user_clicked_word = False

    def on_timeline_clicked(self, t):
        # 点击时间轴跳转
        if self.video_player.player:
            self.video_player.player.setPosition(int(t * 1000))
            self.video_player.player.pause()

    def on_timeline_jump(self, t):
        print(f"[LOG] MainWindow.on_timeline_jump: t={t}")
        if self.video_player.player:
            print(f"[LOG] setPosition({int(t * 1000)}) called")
            self.video_player.player.pause()
            self.video_player.player.setPosition(int(t * 1000))
        # 帧带跳转时高亮文字
        self.editor.highlight_word_at(t)

    def undo(self):
        if self.undo_stack:
            self.editable_words = self.undo_stack.pop()
            self.editor.refresh(self.editable_words)
            self.refresh_llm_btn()
            # 撤销时不自动生成预览视频

    def preview_video(self):
        # 用当前editable_words生成剪辑后预览视频，并自动播放
        if not self.video_path or not self.editable_words:
            return
        # 合并连续区间
        keep_ranges = []
        for w in self.editable_words:
            if not keep_ranges or abs(w['start'] - keep_ranges[-1][1]) > 1e-3:
                keep_ranges.append([w['start'], w['end']])
            else:
                keep_ranges[-1][1] = w['end']
        if not keep_ranges:
            return
        # 清理上一次的临时文件
        if hasattr(self, '_last_preview_tempfile') and self._last_preview_tempfile:
            try:
                os.remove(self._last_preview_tempfile)
            except Exception:
                pass
            self._last_preview_tempfile = None
        # 生成新的临时文件
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            preview_path = tmp.name
        self._last_preview_tempfile = preview_path
        clip = VideoFileClip(self.video_path)
        subclips = [clip.subclip(start, end) for start, end in keep_ranges]
        final = concatenate_videoclips(subclips)
        final.write_videofile(preview_path, codec='libx264', audio_codec='aac', verbose=False, logger=None)
        # 用 QMediaPlayer 播放临时文件
        self.video_player.player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(preview_path))))
        self.video_player.player.play()

    def update_play_pause_btn(self, state):
        if state == QMediaPlayer.PlayingState:
            self.video_player.play_pause_btn.setText('暂停')
        else:
            self.video_player.play_pause_btn.setText('播放')

    def start_asr(self):
        if not self.video_path:
            QMessageBox.warning(self, '未选择视频', '请先选择音/视频文件')
            return
        # 识别中提示
        self.editor.refresh([{'word': '识别中...'}])
        self.repaint()
        self.asr_btn.setEnabled(False)  # 禁用按钮，防止重复点击
        try:
            self.upload_and_asr(self.video_path)
        except Exception as e:
            self.asr_btn.setEnabled(True)  # 异常时恢复按钮
            raise

    def full_res_preview_request(self, t):
        # t: 时间戳（秒）
        if not self.video_path:
            return
        def extract_and_show():
            try:
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(self.video_path)
                frame = clip.get_frame(t)  # numpy array, RGB
                self.frame_preview.show_frame(frame)
            except Exception as e:
                print(f"[LOG] 高分辨率帧提取失败: {e}")
        threading.Thread(target=extract_and_show, daemon=True).start()

    def on_word_clicked(self, time_):
        # 文字优先：强制同步所有视图
        self.user_clicked_word = True
        if self.video_player.player:
            self.video_player.player.blockSignals(True)  # 防止 positionChanged 触发自动高亮
            self.video_player.player.setPosition(int(time_ * 1000))
            self.video_player.player.blockSignals(False)
        self.timeline.set_position(time_)
        self.editor.highlight_word_at(time_)

    def on_word_deleted(self, idxs):
        # idxs: 被删除的索引列表（降序）
        self.undo_stack.append(copy.deepcopy(self.editable_words))  # 撤销栈 push
        for idx in idxs:
            if 0 <= idx < len(self.editable_words):
                self.editable_words.pop(idx)
        self.editor.refresh(self.editable_words)
        self.refresh_llm_btn()
        # 同步 timeline
        duration = 0
        if self.editable_words:
            duration = max(w['end'] for w in self.editable_words)
        self.timeline.set_words(self.editable_words, duration)

    def clean_llm_text(self, llm_text):
        # 只保留汉字
        return ''.join(re.findall(r'[\u4e00-\u9fa5]', llm_text))

    def align_words_by_chars(self, llm_text, asr_words):
        """
        llm_text: 大模型返回的纯文本（按字输出，已去除标点）
        asr_words: [{'word': '可能', ...}, {'word': '问题', ...}, ...]
        返回：保留的 asr_words 的下标列表
        """
        keep_idxs = []
        i = 0  # asr_words指针
        j = 0  # llm_text指针
        while i < len(asr_words) and j < len(llm_text):
            w = asr_words[i]['word']
            # 跳过空隙词组
            if w.startswith('[') and w.endswith(']'):
                i += 1
                continue
            wlen = len(w)
            if llm_text[j:j+wlen] == w:
                keep_idxs.append(i)
                j += wlen
            else:
                j += 1
                continue
            i += 1
        return keep_idxs

    def align_words_by_content(self, llm_words, orig_words):
        """
        llm_words: [{'word': '你好'}, ...]
        orig_words: [{'word': '你好', 'start': ..., 'end': ...}, ...]
        返回：保留的 orig_words 的结构化数据（带start/end）
        """
        result = []
        j = 0
        for i, w in enumerate(orig_words):
            if j < len(llm_words) and w['word'] == llm_words[j]['word']:
                result.append(w)
                j += 1
            if j >= len(llm_words):
                break
        print("优化后的结构化数据：", result)
        return result

    def llm_optimize(self):
        # 读取API_KEY
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(config_path):
            QMessageBox.critical(self, '配置缺失', '未找到config.json配置文件，请在项目目录下创建并写入{"API_KEY": "你的key"}')
            return
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        API_KEY = config.get('API_KEY', '').strip()
        MODEL_NAME = config.get('MODEL', 'deepseek-r1')
        BASE_URL = config.get('BASE_URL', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        if not API_KEY:
            QMessageBox.critical(self, '配置错误', 'config.json中未配置API_KEY')
            return
        # 1. 组织结构化words数据（只包含word）
        orig_words = self.editable_words
        if not orig_words:
            QMessageBox.warning(self, 'AI优化文案', '当前没有可优化的文字内容！')
            return
        words_struct = [{"word": w["word"]} for w in orig_words]
        print('输入AI的结构化文字', words_struct)
        self.llm_btn.setEnabled(False)
        self.llm_btn.setText('AI优化中...')
        try:
            llm_text = llm_struct_optimize(words_struct, API_KEY, MODEL_NAME, BASE_URL)
            print(safe_str("AI返回内容：" + llm_text))
            json_str = extract_json(llm_text)

            #QMessageBox.information(self, 'AI返回内容', safe_str(llm_text))

            # 解析返回的结构化words数组
            try:
                llm_words = json.loads(json_str)
                if not isinstance(llm_words, list) or not all(
                    isinstance(w, dict) and "word" in w for w in llm_words
                ):
                    raise ValueError('返回内容不是结构化words数组')
            except Exception as e:
                debug_info = safe_str(f"原始words: {json.dumps(words_struct, ensure_ascii=False)}\nAI返回: {llm_text}\n解析异常: {e}")
                print(debug_info)
                QMessageBox.warning(self, 'AI优化文案', safe_str('AI返回内容解析失败，请重试或检查API返回。\n\n' + debug_info))
                return
            # 对齐，生成新 editable_words
            new_editable_words = self.align_words_by_content(llm_words, orig_words)
            self.undo_stack.append(copy.deepcopy(self.editable_words))
            self.editable_words = new_editable_words
            self.editor.refresh(self.editable_words)
            self.refresh_llm_btn()
            # 同步 timeline
            duration = 0
            if self.editable_words:
                duration = max(w['end'] for w in self.editable_words)
            self.timeline.set_words(self.editable_words, duration)
            QMessageBox.information(self, 'AI优化文案', safe_str('优化完成！'))
        except Exception as e:
            QMessageBox.critical(self, 'AI优化文案失败', safe_str(str(e)))
        finally:
            self.llm_btn.setEnabled(True)
            self.llm_btn.setText('AI优化文案')

    def refresh_llm_btn(self):
        # 只有有可用文字时才可用
        self.llm_btn.setEnabled(bool(self.editable_words))

def llm_struct_optimize(words_struct, api_key, model_name, base_url=None):
    import json
    try:
        from openai import OpenAI
    except ImportError:
        raise Exception("未安装 openai SDK，请先运行 pip install --upgrade openai")

    # 初始化OpenAI客户端
    client = OpenAI(
        api_key=api_key,
        #base_url=base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        base_url="https://openkey.cloud/v1" 
    )

    prompt = (
        "你是一个视频剪辑助手。下面是ASR识别的结构化结果，每个元素只包含：\n"
        "- word：文字内容（可能是单字或词组）\n"
        "你的任务：将列表中所有的word组成连贯通顺的新段落。只能删除整个{}，不能增加、不能修改、不能打乱顺序，不能合并或拆分，不能将多个item合并为一个，也不能将一个item拆分为多个，只能按原顺序重新组合成你认为通顺简洁有意义的新段落或语句。\n"
        "【重要】每个item只能整体保留或整体删除，不能对item内容做任何修改。\n"
        "请严格返回你认为应该保留的词组的结构化JSON数组，格式与输入完全一致，不要有多余解释或内容。\n"
        "【正例】\n"
        "输入：[{\"word\":\"刚\"},{\"word\":\"才\"},{\"word\":\"运行\"},{\"word\":\"代码\"},{\"word\":\"啊\"}]\n"
        "如果你认为'啊'是多余的，返回：[{\"word\":\"刚\"},{\"word\":\"才\"},{\"word\":\"运行\"},{\"word\":\"代码\"}]\n"
        "【反例1】合并item是错误的：[{\"word\":\"刚才\"},{\"word\":\"运行代码\"}]\n"
        "【反例2】拆分item是错误的：[{\"word\":\"运\"},{\"word\":\"行\"}]\n"
        "【反例3】修改item内容是错误的：[{\"word\":\"刚才运行代码\"}]\n"
        "下面是需要优化的数据：\n" + json.dumps(words_struct, ensure_ascii=False)
    )

    # 创建聊天完成请求
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        stream=False
    )

    # 兼容不同返回格式
    if hasattr(completion, "choices") and completion.choices:
        llm_text = completion.choices[0].message.content
    else:
        raise Exception(f"API返回格式异常: {completion}")

    return llm_text.strip()

def extract_json(text):
    # 匹配三引号包裹的内容
    match = re.search(r"'''json\s*(\[[\s\S]*\])\s*'''", text)
    if match:
        return match.group(1)
    # 兜底：匹配第一个中括号
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return match.group(0)
    return text

if __name__ == '__main__':
    import sys
    import signal
    # 如果命令行参数包含 --test-llm，则只做大模型结构化测试
    if '--test-llm' in sys.argv:
        import os, json
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        API_KEY = config.get('API_KEY', '').strip()
        MODEL_NAME = config.get('MODEL', 'deepseek-r1')
        # 示例words_struct
        words_struct = [{'word': '刚', 'start': 0.84, 'end': 0.94}, {'word': '才', 'start': 0.94, 'end': 1.1}, {'word': '我', 'start': 1.1, 'end': 1.22}, {'word': '运', 'start': 1.22, 'end': 1.32}, {'word': '行', 'start': 1.32, 'end': 1.4}, {'word': '代', 'start': 1.4, 'end': 1.5}, {'word': '码', 'start': 1.5, 'end': 1.64}, {'word': '可能', 'start': 1.64, 'end': 1.8}, {'word': '出', 'start': 1.8, 'end': 1.94}, {'word': '现', 'start': 1.94, 'end': 2.1}, {'word': '问题', 'start': 2.1, 'end': 2.34}, {'word': '了', 'start': 2.34, 'end': 2.52}, {'word': '[0.060 sec]', 'start': 2.52, 'end': 2.58}, {'word': '所以', 'start': 2.58, 'end': 2.76}, {'word': '我就', 'start': 2.76, 'end': 3.6}, {'word': '让', 'start': 3.6, 'end': 3.82}, {'word': '他', 'start': 3.82, 'end': 3.96}, {'word': '帮', 'start': 3.96, 'end': 4.32}, {'word': '我', 'start': 4.32, 'end': 4.42}, {'word': '检', 'start': 4.42, 'end': 4.56}, {'word': '查', 'start': 4.56, 'end': 4.68}, {'word': '一下', 'start': 4.68, 'end': 4.76}, {'word': '代', 'start': 4.76, 'end': 4.92}, {'word': '码', 'start': 4.92, 'end': 5.1}, {'word': '[0.060 sec]', 'start': 5.1, 'end': 5.16}, {'word': '为什么', 'start': 5.16, 'end': 5.32}, {'word': '刚', 'start': 5.32, 'end': 5.58}, {'word': '才', 'start': 5.58, 'end': 5.72}, {'word': '运', 'start': 5.72, 'end': 5.88}, {'word': '行', 'start': 5.88, 'end': 6.0}, {'word': '的', 'start': 6.0, 'end': 6.08}, {'word': '代', 'start': 6.08, 'end': 6.22}, {'word': '码', 'start': 6.22, 'end': 6.42}, {'word': '没有', 'start': 6.42, 'end': 6.62}, {'word': '反', 'start': 6.62, 'end': 6.76}, {'word': '应', 'start': 6.76, 'end': 6.94}, {'word': '了', 'start': 6.94, 'end': 7.06}, {'word': '[0.020 sec]', 'start': 7.06, 'end': 7.08}, {'word': '看', 'start': 7.08, 'end': 7.22}, {'word': '他', 'start': 7.22, 'end': 7.34}, {'word': '怎么', 'start': 7.34, 'end': 7.54}, {'word': '帮', 'start': 7.54, 'end': 7.88}, {'word': '我', 'start': 7.88, 'end': 7.98}, {'word': '处', 'start': 7.98, 'end': 8.14}, {'word': '理', 'start': 8.14, 'end': 8.26}, {'word': '了', 'start': 8.26, 'end': 8.28}, {'word': '[0.550 sec]', 'start': 8.28, 'end': 8.83}, {'word': '就', 'start': 8.83, 'end': 9.56}, {'word': '可能', 'start': 9.568, 'end': 9.86}, {'word': '我在', 'start': 9.86, 'end': 10.24}, {'word': '之前', 'start': 10.24, 'end': 10.74}, {'word': '整', 'start': 10.74, 'end': 11.8}, {'word': '理', 'start': 11.808, 'end': 11.94}, {'word': '代', 'start': 11.94, 'end': 12.0}, {'word': '码', 'start': 12.0, 'end': 12.18}, {'word': '的时候', 'start': 12.18, 'end': 12.36}, {'word': '[0.200 sec]', 'start': 12.36, 'end': 12.56}, {'word': '多', 'start': 12.56, 'end': 12.7}, {'word': '删', 'start': 12.7, 'end': 12.94}, {'word': '除', 'start': 12.94, 'end': 13.1}, {'word': '了', 'start': 13.1, 'end': 13.2}, {'word': '或', 'start': 13.2, 'end': 13.32}, {'word': '怎么', 'start': 13.32, 'end': 13.62}, {'word': '误', 'start': 13.62, 'end': 13.96}, {'word': '删', 'start': 13.96, 'end': 14.12}, {'word': '除', 'start': 14.12, 'end': 14.28}, {'word': '了', 'start': 14.28, 'end': 14.38}, {'word': '某', 'start': 14.38, 'end': 14.52}, {'word': '些', 'start': 14.52, 'end': 14.62}, {'word': '文', 'start': 14.62, 'end': 14.74}, {'word': '件', 'start': 14.74, 'end': 14.94}, {'word': '之', 'start': 14.94, 'end': 15.08}, {'word': '类', 'start': 15.08, 'end': 15.26}, {'word': '的', 'start': 15.26, 'end': 15.36}, {'word': '东', 'start': 15.36, 'end': 15.48}, {'word': '西', 'start': 15.48, 'end': 15.68}, {'word': '[0.420 sec]', 'start': 15.68, 'end': 16.1}, {'word': '所以', 'start': 16.1, 'end': 16.54}, {'word': '我们', 'start': 16.544, 'end': 16.72}, {'word': '让', 'start': 16.72, 'end': 17.06}, {'word': '他', 'start': 17.06, 'end': 17.18}, {'word': '去', 'start': 17.18, 'end': 17.32}, {'word': '检', 'start': 17.32, 'end': 17.52}, {'word': '查', 'start': 17.52, 'end': 17.66}, {'word': '一下', 'start': 17.66, 'end': 17.76}, {'word': '现在', 'start': 17.76, 'end': 18.0}, {'word': '的', 'start': 18.0, 'end': 18.1}, {'word': '代', 'start': 18.1, 'end': 18.18}, {'word': '码', 'start': 18.18, 'end': 18.4}, {'word': '[0.650 sec]', 'start': 18.4, 'end': 19.05}, {'word': '看', 'start': 19.05, 'end': 19.5}, {'word': '啥', 'start': 19.52, 'end': 19.7}, {'word': '样', 'start': 19.7, 'end': 19.84}, {'word': '子', 'start': 19.84, 'end': 19.94}, {'word': '[0.060 sec]', 'start': 19.94, 'end': 20.0}, {'word': '看', 'start': 20.0, 'end': 20.28}, {'word': '能', 'start': 20.28, 'end': 20.46}, {'word': '不能', 'start': 20.46, 'end': 20.56}, {'word': '解', 'start': 20.56, 'end': 20.68}, {'word': '决', 'start': 20.68, 'end': 20.82}, {'word': '掉', 'start': 20.82, 'end': 20.9}, {'word': '这个', 'start': 20.9, 'end': 21.12}, {'word': '问题', 'start': 21.12, 'end': 21.38}, {'word': '[1.020 sec]', 'start': 21.38, 'end': 22.4}, {'word': '大家', 'start': 22.4, 'end': 22.5}, {'word': '能', 'start': 22.5, 'end': 22.66}, {'word': '看', 'start': 22.66, 'end': 22.82}, {'word': '清', 'start': 22.82, 'end': 22.96}, {'word': '这个', 'start': 22.96, 'end': 23.2}, {'word': '文', 'start': 23.2, 'end': 24.0}, {'word': '字', 'start': 24.0, 'end': 24.18}, {'word': '吗', 'start': 24.18, 'end': 24.3}, {'word': '[14.280 sec]', 'start': 24.3, 'end': 38.58}, {'word': '他', 'start': 38.58, 'end': 38.98}, {'word': '就', 'start': 38.98, 'end': 39.16}, {'word': '检', 'start': 39.168, 'end': 39.58}, {'word': '查', 'start': 39.58, 'end': 39.64}, {'word': '了', 'start': 39.64, 'end': 39.76}, {'word': '半', 'start': 39.76, 'end': 39.88}, {'word': '天', 'start': 39.88, 'end': 40.02}, {'word': '就', 'start': 40.02, 'end': 40.12}, {'word': '检', 'start': 40.12, 'end': 40.28}, {'word': '查', 'start': 40.28, 'end': 40.38}, {'word': '了', 'start': 40.38, 'end': 40.44}, {'word': '也', 'start': 40.44, 'end': 41.18}, {'word': '没有', 'start': 41.248, 'end': 41.72}, {'word': '啥', 'start': 41.72, 'end': 42.04}, {'word': '啊', 'start': 42.04, 'end': 42.2}, {'word': '[1.350 sec]', 'start': 42.2, 'end': 43.55}, {'word': '这个', 'start': 43.55, 'end': 44.0}, {'word': '窗', 'start': 44.032, 'end': 44.28}, {'word': '口', 'start': 44.28, 'end': 44.4}, {'word': '他', 'start': 44.4, 'end': 45.98}, {'word': '为什么', 'start': 46.08, 'end': 46.18}, {'word': '不', 'start': 46.18, 'end': 46.36}, {'word': '跟', 'start': 46.36, 'end': 46.5}, {'word': '着', 'start': 46.5, 'end': 46.56}, {'word': '缩', 'start': 46.56, 'end': 46.78}, {'word': '小', 'start': 46.78, 'end': 46.98}, {'word': '呢', 'start': 46.98, 'end': 47.12}, {'word': '[3.340 sec]', 'start': 47.12, 'end': 50.46}, {'word': '你', 'start': 50.46, 'end': 50.86}, {'word': '妈', 'start': 50.86, 'end': 51.08}, {'word': '的', 'start': 51.08, 'end': 51.22}, {'word': '这个', 'start': 51.28, 'end': 51.38}, {'word': '玩', 'start': 51.38, 'end': 51.54}, {'word': '意', 'start': 51.54, 'end': 51.58}, {'word': '有', 'start': 51.58, 'end': 51.72}, {'word': '问题', 'start': 51.72, 'end': 52.04}, {'word': '啊', 'start': 52.04, 'end': 52.22}, {'word': '[13.760 sec]', 'start': 52.22, 'end': 65.98}, {'word': '是不是', 'start': 65.98, 'end': 66.08}, {'word': '我', 'start': 66.08, 'end': 66.46}, {'word': '把', 'start': 66.46, 'end': 66.68}, {'word': '屏', 'start': 66.68, 'end': 67.34}, {'word': '幕', 'start': 67.36, 'end': 67.46}, {'word': '放', 'start': 67.46, 'end': 67.58}, {'word': '大', 'start': 67.58, 'end': 67.76}, {'word': '了', 'start': 67.76, 'end': 67.88}, {'word': '他', 'start': 67.88, 'end': 67.98}, {'word': '没有', 'start': 67.98, 'end': 68.74}, {'word': '放', 'start': 68.8, 'end': 68.98}, {'word': '大', 'start': 68.98, 'end': 69.2}, {'word': '呀', 'start': 69.2, 'end': 69.32}]
        words_struct = [{"word": w["word"]} for w in words_struct]
        print('测试AI结构化优化...')
        llm_text = llm_struct_optimize(words_struct, API_KEY, MODEL_NAME)
        json_str = extract_json(llm_text)
        print('AI返回：', json_str)
        try:
            new_words = json.loads(json_str)
            print('解析后结构：', new_words)
        except Exception as e:
            print('解析异常：', e)
        sys.exit(0)
    # 否则正常启动桌面端
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    sys.exit(app.exec_()) 