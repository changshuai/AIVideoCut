import stable_whisper
import os
import tempfile
from typing import List, Dict, Any

class ASRService:
    def __init__(self, model_name: str = "large-v3"):
        """
        初始化 ASR 服务
        :param model_name: whisper 模型名称，可选值：tiny, base, small, medium, large
        """
        self.model = stable_whisper.load_model(model_name)
    
    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        转录音频文件
        :param audio_path: 音频文件路径
        :return: 包含时间戳的转录结果列表
        """
        # 使用 stable-ts 进行转录，启用 VAD 以获得更好的非语音检测
        result = self.model.transcribe(
            audio_path,
            vad=True,  # 使用 VAD 进行语音检测
            word_timestamps=True,  # 启用词级别时间戳
            language="zh",  # 设置语言为中文
        )
        
        # 将结果转换为所需的格式，并插入空隙时间
        segments = []
        last_end = None
        for segment in result.segments:
            # 插入空隙时间标注
            if last_end is not None and segment.start > last_end:
                gap_sec = segment.start - last_end
                gap_sec_str = f"[{gap_sec:.3f} sec]"
                segments.append({
                    "start": last_end,
                    "end": segment.start,
                    "text": gap_sec_str,
                    "words": [
                        {
                            "word": gap_sec_str,
                            "start": last_end,
                            "end": segment.start
                        }
                    ]
                })
            segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end
                    }
                    for word in segment.words
                ] if hasattr(segment, 'words') else []
            })
            last_end = segment.end
        return segments

# 创建全局 ASR 服务实例
asr_service = ASRService() 