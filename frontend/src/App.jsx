import React from 'react';
import { Layout } from 'antd';
import AudioUpload from './components/AudioUpload';
import AudioExtractor from './components/AudioExtractor';

const { Header, Content, Footer } = Layout;

function App() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <div style={{ color: '#fff', fontSize: 20 }}>AI智能剪辑口播视频工具</div>
      </Header>
      <Content style={{ padding: '24px' }}>
        <AudioUpload />
        <div style={{ marginTop: 32 }}>
          <AudioExtractor />
        </div>
      </Content>
      <Footer style={{ textAlign: 'center' }}>
        AI Cut Video ©2024
      </Footer>
    </Layout>
  );
}

export default App; 