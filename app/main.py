from __future__ import annotations
import hmac, os, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data/casal.db")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(ROOT / "uploads")))
MAX_UPLOAD_MB = max(1, int(os.getenv("MAX_UPLOAD_MB", "8")))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "felipe67@")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
if not ADMIN_PASSWORD:
    raise RuntimeError("Defina ADMIN_PASSWORD no arquivo .env.")
if len(SESSION_SECRET) < 24:
    raise RuntimeError("Defina SESSION_SECRET com pelo menos 24 caracteres.")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Nosso cantinho 💗")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, session_cookie="cantinho_session",
                   same_site="lax", https_only=COOKIE_SECURE, max_age=604800)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(ROOT / "app/static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "app/templates"))
ALLOWED_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

with connect() as conn:
    conn.execute("""CREATE TABLE IF NOT EXISTS photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL UNIQUE,
        caption TEXT NOT NULL DEFAULT '', taken_on TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL)""")

def is_admin(request: Request):
    return request.session.get("admin") is True

def page(request: Request, template: str, **context):
    return templates.TemplateResponse(request=request, name=template,
                                      context={"request": request, **context})

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "index.html", active="home")

@app.get("/album", response_class=HTMLResponse)
def album(request: Request):
    with connect() as conn:
        photos = conn.execute("SELECT * FROM photos ORDER BY id DESC").fetchall()
    return page(request, "album.html", photos=photos, active="album")

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    if not is_admin(request):
        return page(request, "login.html", error=None, active="")
    with connect() as conn:
        photos = conn.execute("SELECT * FROM photos ORDER BY id DESC").fetchall()
    return page(request, "admin.html", photos=photos, active="")

@app.post("/admin/login")
def login(request: Request, email: Annotated[str, Form()], password: Annotated[str, Form()]):
    ok_email = hmac.compare_digest(email.strip().casefold(), ADMIN_EMAIL.strip().casefold())
    ok_password = hmac.compare_digest(password, ADMIN_PASSWORD)
    if not (ok_email and ok_password):
        return page(request, "login.html", error="E-mail ou senha incorretos.", active="")
    request.session.clear()
    request.session["admin"] = True
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/upload")
async def upload_photos(request: Request, files: Annotated[list[UploadFile], File()],
                        caption: Annotated[str, Form()] = "",
                        taken_on: Annotated[str, Form()] = ""):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Faça login para enviar fotos.")
    saved = []
    try:
        for item in files:
            suffix = ALLOWED_TYPES.get(item.content_type or "")
            if not suffix:
                raise HTTPException(status_code=400, detail="Use JPG, PNG, WEBP ou GIF.")
            content = await item.read(MAX_UPLOAD_BYTES + 1)
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"Cada imagem deve ter até {MAX_UPLOAD_MB} MB.")
            if not content:
                continue
            signatures = {".jpg": (b"\xff\xd8\xff",), ".png": (b"\x89PNG\r\n\x1a\n",),
                          ".webp": (b"RIFF",), ".gif": (b"GIF87a", b"GIF89a")}
            if not any(content.startswith(sig) for sig in signatures[suffix]):
                raise HTTPException(status_code=400, detail="Um arquivo não parece ser uma imagem válida.")
            if suffix == ".webp" and content[8:12] != b"WEBP":
                raise HTTPException(status_code=400, detail="Arquivo WEBP inválido.")
            name = f"{uuid.uuid4().hex}{suffix}"
            (UPLOAD_DIR / name).write_bytes(content)
            saved.append(name)
        with connect() as conn:
            for name in saved:
                conn.execute("INSERT INTO photos(filename, caption, taken_on, created_at) VALUES (?, ?, ?, ?)",
                             (name, caption.strip()[:180], taken_on.strip()[:10],
                              datetime.now().isoformat(timespec="seconds")))
    except Exception:
        for name in saved:
            (UPLOAD_DIR / name).unlink(missing_ok=True)
        raise
    return RedirectResponse("/admin?uploaded=1", status_code=303)

@app.post("/admin/delete/{photo_id}")
def delete_photo(request: Request, photo_id: int):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Faça login para excluir fotos.")
    with connect() as conn:
        row = conn.execute("SELECT filename FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row:
            conn.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
            (UPLOAD_DIR / row["filename"]).unlink(missing_ok=True)
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/edit/{photo_id}")
def edit_photo(request: Request, photo_id: int, caption: Annotated[str, Form()] = "",
               taken_on: Annotated[str, Form()] = ""):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Faça login para editar fotos.")
    with connect() as conn:
        conn.execute("UPDATE photos SET caption = ?, taken_on = ? WHERE id = ?",
                     (caption.strip()[:180], taken_on.strip()[:10], photo_id))
    return RedirectResponse("/admin", status_code=303)
