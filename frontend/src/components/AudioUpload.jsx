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

  // 视频时间轴联动
  const handleTimeUpdate = (e) => {
    const current = e.target.currentTime;
    
    // 查找当前段落
    let idx = result.findIndex(
      (seg) => current >= seg.start && current < seg.end
    );
    setCurrentIdx(idx);

    // 查找当前单词
    if (idx !== -1 && result[idx].words) {
      let wordIdx = result[idx].words.findIndex(
        (word) => current >= word.start && current < word.end
      );
      setCurrentWordIdx(wordIdx);
    } else {
      setCurrentWordIdx(-1);
    }
  };

  // 点击识别结果跳转视频
  const handleListClick = (seg) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seg.start;
      videoRef.current.play();
    }
  };

  // 点击单个字跳转到对应时间
  const handleWordClick = (word, event) => {
    event.stopPropagation(); // 阻止事件冒泡，避免触发段落的点击事件
    if (videoRef.current) {
      videoRef.current.currentTime = word.start;
      // 暂停一小段时间后开始播放，让用户能听到当前字
      videoRef.current.pause();
      setTimeout(() => {
        videoRef.current.play();
      }, 100);
    }
  };

  // 渲染带高亮的文本
  const renderHighlightedText = (segment, idx) => {
    if (!segment.words || segment.words.length === 0) {
      return segment.text;
    }

    return (
      <span>
        {segment.words.map((word, wordIdx) => (
          <span
            key={wordIdx}
            onClick={(e) => handleWordClick(word, e)}
            style={{
              backgroundColor: idx === currentIdx && wordIdx === currentWordIdx ? '#ffd591' : 'transparent',
              padding: '0 2px',
              borderRadius: '2px',
              transition: 'background-color 0.3s',
              cursor: 'pointer',
              position: 'relative',
              display: 'inline-block',
              margin: '0 1px',
              border: '1px solid transparent',
              '&:hover': {
                border: '1px solid #1890ff',
              }
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
              display: idx === currentIdx && wordIdx === currentWordIdx ? 'block' : 'none',
            }}>
              {word.start.toFixed(2)}s
            </span>
          </span>
        ))}
      </span>
    );
  };

  // 获取第一个字的时间
  const getFirstWordTime = (segment) => {
    if (segment.words && segment.words.length > 0) {
      return segment.words[0].start;
    }
    return segment.start;
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
            onTimeUpdate={handleTimeUpdate}
            src={videoUrl}
          />
        </div>
      )}
      <List
        style={{ marginTop: 24 }}
        header={result.length > 0 ? <div>识别结果</div> : null}
        dataSource={result}
        renderItem={(item, idx) => (
          <List.Item
            style={{
              background: idx === currentIdx ? '#e6f7ff' : undefined,
              cursor: videoFile ? 'pointer' : 'default',
              padding: '12px',
              borderRadius: '4px',
            }}
            onClick={() => videoFile && handleListClick(item)}
          >
            <div>
              <div style={{ color: '#666', fontSize: '12px', marginBottom: '4px' }}>
                <span style={{ color: '#1890ff', fontWeight: 'bold' }}>
                  首字时间: {getFirstWordTime(item).toFixed(2)}s
                </span>
                {' | '}
                <span>
                  段落时间: [{item.start.toFixed(2)}s - {item.end.toFixed(2)}s]
                </span>
              </div>
              <div style={{ fontSize: '16px', lineHeight: '2.5' }}>
                {renderHighlightedText(item, idx)}
              </div>
            </div>
          </List.Item>
        )}
      />
    </div>
  );
};

export default AudioUpload; 