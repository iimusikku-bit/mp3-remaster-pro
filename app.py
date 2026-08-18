import uuid, subprocess, shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

BASE=Path(__file__).resolve().parent
TMP=BASE/"tmp"; OUT=BASE/"outputs"
TMP.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
app=FastAPI(title="MP3 Remaster Pro")
app.mount("/static",StaticFiles(directory=BASE/"static"),name="static")

@app.get("/",response_class=HTMLResponse)
def home():
    return (BASE/"static/index.html").read_text(encoding="utf-8")

def filters(preset,clarity,loudness):
    c=max(0,min(100,int(clarity))); l=max(0,min(100,int(loudness)))
    if preset=="vocal": eq=f"equalizer=f=3000:t=q:w=1:g={3+c/30:.2f}"
    elif preset=="bass": eq=f"bass=g={3+c/25:.2f}:f=110"
    elif preset=="loud": eq="equalizer=f=3000:t=q:w=1:g=3"
    elif preset=="gentle": eq="equalizer=f=3000:t=q:w=1:g=1"
    else: eq=f"equalizer=f=3000:t=q:w=1:g={(c-30)/15:.2f}"
    gain=-2+l*.025
    return f"highpass=f=35,{eq},volume={gain:.2f}dB,acompressor=threshold=-18dB:ratio=3:attack=5:release=120,alimiter=limit=0.95,loudnorm=I=-14:LRA=11:TP=-1"

@app.post("/api/remaster")
async def remaster(file:UploadFile=File(...),preset:str=Form("clean"),
                   clarity:int=Form(55),loudness:int=Form(70),bitrate:str=Form("320k")):
    if not file.filename: return {"error":"File tidak ada"}
    ext=Path(file.filename).suffix.lower()
    if ext not in {".mp3",".wav",".flac",".m4a",".aac",".ogg"}:
        return {"error":"Format audio tidak didukung"}
    if bitrate not in {"320k","256k","192k"}: bitrate="320k"
    job=uuid.uuid4().hex; inp=TMP/f"{job}{ext}"; out=OUT/f"{job}.mp3"
    try:
        with inp.open("wb") as f:
            while chunk:=await file.read(1024*1024): f.write(chunk)
        if shutil.which("ffmpeg") is None:
            return {"error":"FFmpeg belum tersedia di server."}
        cmd=["ffmpeg","-y","-i",str(inp),"-vn","-af",filters(preset,clarity,loudness),
             "-c:a","libmp3lame","-b:a",bitrate,"-ar","44100","-ac","2",str(out)]
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=900)
        if p.returncode!=0: return {"error":"FFmpeg gagal memproses audio.","detail":p.stderr[-2500:]}
        return {"download":f"/api/download/{out.name}","filename":Path(file.filename).stem+"_remastered.mp3"}
    except subprocess.TimeoutExpired: return {"error":"Proses terlalu lama dan dihentikan."}
    except Exception as e: return {"error":str(e)}
    finally: inp.unlink(missing_ok=True)

@app.get("/api/download/{name}")
def download(name:str):
    p=OUT/Path(name).name
    if not p.exists(): return HTMLResponse("File tidak ditemukan",404)
    return FileResponse(p,media_type="audio/mpeg",filename=p.name)

@app.get("/health")
def health(): return {"ok":True,"ffmpeg":shutil.which("ffmpeg") is not None}
