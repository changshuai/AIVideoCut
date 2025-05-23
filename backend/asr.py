"""
语音识别与停顿检测模块
"""
from typing import List, Dict
import whisper
import os

# 停顿阈值（秒），大于此值认为是换气/停顿
PAUSE_THRESHOLD = 0.2

# 切换为 medium 模型，兼顾细节和CPU稳定性
model = whisper.load_model("medium")

def transcribe_with_pauses(audio_path: str) -> List[Dict]:
    """
    识别音频中的语音，返回每句话/词及其时间戳，检测停顿。
    返回格式: [{"text": str, "start": float, "end": float, "pause": float}]
    """
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        verbose=False,
        language="zh",
        condition_on_previous_text=False,
    )
    segments = result.get("segments", [])
    output = []
    last_end = 0.0
    for seg in segments:
        start = seg["start"]
        end = seg["end"]
        text = seg["text"].strip()
        pause = start - last_end if last_end > 0 else 0.0
        output.append({
            "text": text,
            "start": start,
            "end": end,
            "pause": round(pause, 2)
        })
        last_end = end
    return output 