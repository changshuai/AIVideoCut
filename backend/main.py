from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
import os
import tempfile
from asr_service import asr_service
import traceback
from fastapi.middleware.cors import CORSMiddleware
from moviepy.editor import VideoFileClip

app = FastAPI()

# 添加CORS中间件，允许所有来源跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
def ping():
    return {"message": "pong"}

@app.post("/asr")
def asr_transcribe(file: UploadFile = File(...)):
    print(f"[ASR] Received file: {file.filename}, content_type: {file.content_type}")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[-1]) as tmp:
            tmp.write(file.file.read())
            tmp_path = tmp.name
        print(f"[ASR] Saved temp file: {tmp_path}")
        try:
            result = asr_service.transcribe(tmp_path)
            print(f"[ASR] Transcription result: {result[:2]} ... total {len(result)} segments")
        finally:
            os.remove(tmp_path)
            print(f"[ASR] Temp file removed: {tmp_path}")
        return JSONResponse(content={"result": result})
    except Exception as e:
        print("[ASR] ERROR during transcription:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ASR error: {e}")

@app.post("/extract-audio")
def extract_audio(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    print(f"[ExtractAudio] Received file: {file.filename}, content_type: {file.content_type}")
    suffix = os.path.splitext(file.filename)[-1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        video_path = tmp.name
    audio_path = video_path + ".wav"
    try:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(audio_path)
        clip.close()
        print(f"[ExtractAudio] Audio extracted: {audio_path}")
        if background_tasks is not None:
            background_tasks.add_task(os.remove, video_path)
            background_tasks.add_task(os.remove, audio_path)
        return FileResponse(audio_path, filename=os.path.basename(audio_path), media_type="audio/wav")
    except Exception as e:
        print("[ExtractAudio] ERROR:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extract audio error: {e}") 