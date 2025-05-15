import React, { useState } from 'react';
import { Upload, Button, message } from 'antd';
import { SoundOutlined } from '@ant-design/icons';
import axios from 'axios';

const AudioExtractor = () => {
  const [audioUrl, setAudioUrl] = useState(null);

  const handleExtract = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    message.loading({ content: '正在分离音频...', key: 'extract' });
    try {
      const res = await axios.post('/extract-audio', formData, {
        baseURL: 'http://localhost:8000',
        responseType: 'blob',
      });
      const url = URL.createObjectURL(res.data);
      setAudioUrl(url);
      message.success({ content: '音频分离成功', key: 'extract' });
    } catch (err) {
      message.error({ content: '音频分离失败', key: 'extract' });
    }
    return false;
  };

  return (
    <div>
      <Upload
        beforeUpload={handleExtract}
        showUploadList={false}
        accept=".mp4,.mov,.avi"
      >
        <Button icon={<SoundOutlined />}>分离视频音频</Button>
      </Upload>
      {audioUrl && (
        <div style={{ marginTop: 16 }}>
          <audio controls src={audioUrl} style={{ width: '100%' }} />
          <a href={audioUrl} download="audio.wav">
            <Button type="link">下载音频</Button>
          </a>
        </div>
      )}
    </div>
  );
};

export default AudioExtractor; 