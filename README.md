# AI智能剪辑口播视频工具

## 项目简介
本工具用于自动识别视频中的语音，将语音转为文字，并支持基于文字稿的智能剪辑。结合大语言模型（LLM）对口播内容进行优化，自动剪辑生成更流畅的视频。

## 主要功能
1. 语音识别（ASR），自动转文字并标注停顿。
2. 文字稿展示与编辑，支持基于文字的剪辑。
3. 文字与视频时间轴对齐。
4. LLM智能优化文字稿，只做删减。
5. 剪辑后视频预览与导出。

## 目录结构
```
AI_cut_video/
├── backend/         # 后端服务（FastAPI, ASR, LLM, 视频剪辑）
├── frontend/        # 前端界面（React）
├── README.md        # 项目说明
```

## 快速开始

### 1. 后端（FastAPI）

1. 进入 `backend` 目录：
   ```bash
   cd backend
   ```
2. 安装依赖（建议使用Python 3.8+，推荐虚拟环境）：
   ```bash
   pip install -r requirements.txt
   ```
3. 启动后端服务（默认8000端口）：
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
4. 后端API接口文档可访问：http://localhost:8000/docs

### 2. 前端（React）

1. 进入 `frontend` 目录：
   ```bash
   cd frontend
   ```
2. 安装依赖：
   ```bash
   npm install
   ```
3. 启动前端开发服务器（默认3000端口）：
   ```bash
   npm start
   ```
4. 打开浏览器访问：http://localhost:3000

### 3. 使用说明
- 上传音频（mp3/wav/m4a）或视频（mp4/mov/avi）文件，自动识别并展示文字稿。
- 上传视频时，支持视频预览与识别结果时间轴联动。
- 后续可扩展剪辑、导出等功能。

## 配置大模型API_KEY（重要）

1. 在 `desktop_python` 目录下新建 `config.json` 文件，内容如下：

```json
{
  "API_KEY": "你的key"
}
```

2. 建议将 `config.json` 加入 `.gitignore`，避免上传到GitHub泄露密钥。

3. 未配置或配置错误时，桌面端会弹窗提示。

---
如遇依赖安装或运行问题，请确保Python、Node.js、ffmpeg等环境已正确安装。

## Demo 视频示例

本项目在 `Demo/` 目录下提供了两段示例视频，便于对比优化前后的效果：

- [`Demo/original.mov`](Demo/original.mov)：**优化前** 的原始口播视频
- [`Demo/optimized.mp4`](Demo/optimized.mp4)：**优化后** 的AI剪辑视频

可用于功能演示、效果对比或测试。 