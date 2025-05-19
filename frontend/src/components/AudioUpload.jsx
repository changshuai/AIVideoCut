import React, { useState, useRef, useEffect } from 'react';
import { Upload, Button, message, List, Alert } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import axios from 'axios';

const AudioUpload = () => {
  const [result, setResult] = useState([]);
  const [loading, setLoading] = useState(false);
  const [videoFile, setVideoFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [currentIdx, setCurrentIdx] = useState(-1);
  const [currentWordIdx, setCurrentWordIdx] = useState(-1);
  const [errorMsg, setErrorMsg] = useState('');
  const videoRef = useRef(null);
  // 只能删除的编辑器
  const [editableWords, setEditableWords] = useState([]);

  // 处理 videoFile 变化时的 URL 创建与释放
  useEffect(() => {
    if (videoFile) {
      const url = URL.createObjectURL(videoFile);
      setVideoUrl(url);
      return () => {
        URL.revokeObjectURL(url);
        setVideoUrl(null);
      };
    } else {
      setVideoUrl(null);
    }
  }, [videoFile]);

  useEffect(() => {
    setEditableWords(result.flatMap(seg => seg.words.map(word => ({ ...word }))));
  }, [result]);

  const handleUpload = async (file) => {
    setVideoFile(null);
    setCurrentIdx(-1);
    setCurrentWordIdx(-1);
    setErrorMsg('');
    const isVideo = file.type.startsWith('video');
    if (isVideo) setVideoFile(file);
    const formData = new FormData();
    formData.append('file', file);
    setLoading(true);
    message.loading({ content: '正在识别...', key: 'asr' });
    try {
      const res = await axios.post('/asr', formData, {
        baseURL: 'http://localhost:8000',
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res.data.result);
      message.success({ content: '识别完成', key: 'asr' });
    } catch (err) {
      let msg = '识别失败';
      if (err.response && err.response.data && err.response.data.detail) {
        msg = `识别失败: ${err.response.data.detail}`;
      } else if (err.message) {
        msg = `识别失败: ${err.message}`;
      }
      setErrorMsg(msg);
      message.error({ content: msg, key: 'asr' });
    }
    setLoading(false);
    return false;
  };

  // 合并所有 words
  const allWords = result.flatMap(seg => seg.words.map(word => ({ ...word })));

  // 当前播放 word 高亮
  const getCurrentWordIdx = () => {
    if (!videoRef.current) return -1;
    const current = videoRef.current.currentTime;
    return allWords.findIndex(word => current >= word.start && current < word.end);
  };

  // 点击单个字跳转到对应时间
  const handleWordClick = (word, event) => {
    event.stopPropagation();
    if (videoRef.current) {
      videoRef.current.currentTime = word.start;
      videoRef.current.pause();
    }
  };

  // 编辑器点击跳转
  const [selectedEditorIdx, setSelectedEditorIdx] = useState(-1);
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.key === 'Backspace' || e.key === 'Delete') && selectedEditorIdx !== -1) {
        setEditableWords(words => words.filter((_, i) => i !== selectedEditorIdx));
        setSelectedEditorIdx(-1);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedEditorIdx]);

  // 渲染所有 words
  const renderAllWords = () => {
    const currentWordIdx = getCurrentWordIdx();
    return (
      <div style={{ fontSize: '16px', lineHeight: '2.5', wordBreak: 'break-all' }}>
        {allWords.map((word, idx) => {
          if (/^\[\d+ms\]$/.test(word.word)) {
            // 空隙
            return (
              <span key={idx} style={{ color: '#aaa', fontStyle: 'italic', background: '#f5f5f5', padding: '2px 6px', borderRadius: 4, margin: '0 2px' }}>
                {word.word}
              </span>
            );
          }
          return (
            <span
              key={idx}
              onClick={e => handleWordClick(word, e)}
              style={{
                backgroundColor: idx === currentWordIdx ? '#ffd591' : 'transparent',
                padding: '0 2px',
                borderRadius: '2px',
                transition: 'background-color 0.3s',
                cursor: 'pointer',
                position: 'relative',
                display: 'inline-block',
                margin: '0 1px',
                border: '1px solid transparent',
              }}
              title={`${word.word}: ${word.start.toFixed(2)}s - ${word.end.toFixed(2)}s`}
            >
              {word.word}
              <span style={{
                position: 'absolute',
                bottom: '-16px',
                left: '50%',
                transform: 'translateX(-50%)',
                fontSize: '10px',
                color: '#666',
                whiteSpace: 'nowrap',
                display: idx === currentWordIdx ? 'block' : 'none',
              }}>
                {word.start.toFixed(2)}s
              </span>
            </span>
          );
        })}
      </div>
    );
  };

  // 渲染只能删除的编辑器
  const renderEditableWords = () => (
    <div style={{ marginTop: 24 }}>
      <div>只能删除的编辑器：</div>
      <div style={{ minHeight: 40, border: '1px solid #eee', borderRadius: 4, padding: 8, background: '#fafafa', cursor: 'pointer', userSelect: 'none' }}>
        {editableWords.map((word, idx) => (
          <span
            key={idx}
            onClick={() => handleEditorWordClick(idx)}
            style={{
              display: 'inline-block',
              margin: '0 2px',
              padding: '2px 4px',
              borderRadius: 3,
              background: idx === selectedEditorIdx ? '#bae7ff' : '#f0f0f0',
              cursor: 'pointer',
              fontWeight: /^\[.*sec\]$/.test(word.word) ? 'normal' : 'bold',
              color: /^\[.*sec\]$/.test(word.word) ? '#aaa' : '#222',
              fontStyle: /^\[.*sec\]$/.test(word.word) ? 'italic' : 'normal',
              transition: 'background 0.2s',
            }}
          >
            {word.word}
          </span>
        ))}
      </div>
      <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>点击选中字块，按Delete/Backspace删除</div>
    </div>
  );

  // 编辑器点击跳转
  const handleEditorWordClick = (idx) => {
    const word = editableWords[idx];
    if (videoRef.current) {
      videoRef.current.currentTime = word.start;
      videoRef.current.pause();
    }
    setSelectedEditorIdx(idx);
  };

  return (
    <div>
      <Upload
        beforeUpload={handleUpload}
        showUploadList={false}
        accept=".mp3,.wav,.m4a,.mp4,.mov,.avi"
        disabled={loading}
      >
        <Button icon={<UploadOutlined />} loading={loading}>
          上传音频/视频文件
        </Button>
      </Upload>
      {errorMsg && (
        <Alert style={{ marginTop: 16 }} message={errorMsg} type="error" showIcon />
      )}
      {videoFile && videoUrl && (
        <div style={{ marginTop: 24 }}>
          <video
            ref={videoRef}
            controls
            style={{ width: '100%', maxHeight: 400 }}
            onTimeUpdate={() => setCurrentWordIdx(getCurrentWordIdx())}
            src={videoUrl}
          />
        </div>
      )}
      {/* 渲染所有words，不再分行 */}
      <div style={{ marginTop: 24 }}>
        {allWords.length > 0 && <div>识别结果</div>}
        {renderAllWords()}
      </div>
      {renderEditableWords()}
    </div>
  );
};

export default AudioUpload; 