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
    let idx = result.findIndex(
      (seg) => current >= seg.start && current < seg.end
    );
    setCurrentIdx(idx);
  };

  // 点击识别结果跳转视频
  const handleListClick = (seg) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seg.start;
      videoRef.current.play();
    }
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
            }}
            onClick={() => videoFile && handleListClick(item)}
          >
            <span>
              [{item.start.toFixed(2)}s - {item.end.toFixed(2)}s]
              {item.pause > 0.5 ? ` [${item.pause}s pause]` : ''} ：{item.text}
            </span>
          </List.Item>
        )}
      />
    </div>
  );
};

export default AudioUpload; 