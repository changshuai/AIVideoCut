import React, { useRef, useEffect } from 'react';

const VideoPreview = ({ file }) => {
  const videoRef = useRef(null);

  useEffect(() => {
    if (file && videoRef.current) {
      const url = URL.createObjectURL(file);
      videoRef.current.src = url;
      return () => URL.revokeObjectURL(url);
    }
  }, [file]);

  if (!file) return null;

  return (
    <div style={{ marginTop: 24 }}>
      <video ref={videoRef} controls style={{ width: '100%', maxHeight: 400 }} />
    </div>
  );
};

export default VideoPreview; 