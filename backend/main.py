from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import os
import tempfile
from asr import transcribe_with_pauses
import traceback
from fastapi.middleware.cors import CORSMiddleware

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
            result = transcribe_with_pauses(tmp_path)
            print(f"[ASR] Transcription result: {result[:2]} ... total {len(result)} segments")
        finally:
            os.remove(tmp_path)
            print(f"[ASR] Temp file removed: {tmp_path}")
        return JSONResponse(content={"result": result})
    except Exception as e:
        print("[ASR] ERROR during transcription:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ASR error: {e}") 