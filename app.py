import os
import re
import sqlite3
import uuid
from pathlib import Path
from functools import wraps
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, abort, send_from_directory
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "manga.db"
UPLOAD_ROOT = BASE_DIR / "static" / "uploads"
COVER_DIR = UPLOAD_ROOT / "covers"
CHAPTER_DIR = UPLOAD_ROOT / "chapters"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_IMAGE_SIZE = 12 * 1024 * 1024

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("MANGA_SECRET_KEY", "change-this-secret-key-before-deploying")
app.config["MAX_CONTENT_LENGTH"] = 120 * 1024 * 1024  # Toi da 120 MB moi lan gui form
csrf = CSRFProtect(app)

for folder in (COVER_DIR, CHAPTER_DIR):
    folder.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS comics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'Khac',
            status TEXT DEFAULT 'Dang cap nhat',
            cover TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comic_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            chapter_number REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(comic_id) REFERENCES comics(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chapter_id INTEGER NOT NULL,
            image TEXT NOT NULL,
            page_order INTEGER NOT NULL,
            FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS readers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reader_id INTEGER NOT NULL,
            comic_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(reader_id, comic_id),
            FOREIGN KEY(reader_id) REFERENCES readers(id) ON DELETE CASCADE,
            FOREIGN KEY(comic_id) REFERENCES comics(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS reading_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reader_id INTEGER NOT NULL,
            comic_id INTEGER NOT NULL,
            chapter_id INTEGER NOT NULL,
            last_read_at TEXT NOT NULL,
            UNIQUE(reader_id, chapter_id),
            FOREIGN KEY(reader_id) REFERENCES readers(id) ON DELETE CASCADE,
            FOREIGN KEY(comic_id) REFERENCES comics(id) ON DELETE CASCADE,
            FOREIGN KEY(chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
        );
        """)
        # Tai khoan mac dinh chi dung cho lan chay dau; hay doi ngay sau khi dang nhap.
        username = os.environ.get("MANGA_ADMIN_USER", "admin")
        password = os.environ.get("MANGA_ADMIN_PASSWORD", "admin12345")
        exists = db.execute("SELECT id FROM admins WHERE username = ?", (username,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password))
            )


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Vui long dang nhap bang tai khoan quan tri.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file_storage, folder: Path):
    if not file_storage or not file_storage.filename:
        return None
    original = secure_filename(file_storage.filename)
    if not original or not allowed_file(original):
        raise ValueError("Chi chap nhan anh PNG, JPG, JPEG, WEBP hoac GIF.")
    # Kiem tra dung luong tung anh (toi da 12 MB/anh).
    stream = file_storage.stream
    current_position = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current_position)
    if size > MAX_IMAGE_SIZE:
        raise ValueError("Moi anh toi da 12 MB.")
    ext = original.rsplit(".", 1)[1].lower()
    new_name = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(folder / new_name)
    return new_name


def delete_image(folder: Path, filename):
    if filename:
        path = folder / Path(filename).name
        if path.exists() and path.is_file():
            path.unlink()


@app.errorhandler(413)
def too_large(_error):
    flash("Anh qua lon. Moi anh toi da 12 MB.", "danger")
    return redirect(request.referrer or url_for("index"))


@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    with get_db() as db:
        categories = [r["category"] for r in db.execute(
            "SELECT DISTINCT category FROM comics WHERE category <> '' ORDER BY category"
        )]
        sql = """
            SELECT c.*, COUNT(ch.id) AS chapter_count
            FROM comics c LEFT JOIN chapters ch ON ch.comic_id = c.id
            WHERE 1=1
        """
        params = []
        if q:
            sql += " AND (c.title LIKE ? OR c.author LIKE ?)"
            params.extend([f"%{q}%", f"%{q}%"])
        if category:
            sql += " AND c.category = ?"
            params.append(category)
        sql += " GROUP BY c.id ORDER BY c.id DESC"
        comics = db.execute(sql, params).fetchall()
    return render_template("index.html", comics=comics, categories=categories, q=q, selected_category=category)


@app.route("/comic/<int:comic_id>")
def comic_detail(comic_id):
    with get_db() as db:
        comic = db.execute("SELECT * FROM comics WHERE id = ?", (comic_id,)).fetchone()
        if not comic:
            abort(404)
        chapters = db.execute(
            "SELECT * FROM chapters WHERE comic_id = ? ORDER BY chapter_number DESC, id DESC",
            (comic_id,)
        ).fetchall()
        is_bookmarked = False
        if session.get("reader_id"):
            is_bookmarked = bool(db.execute(
                "SELECT id FROM bookmarks WHERE reader_id=? AND comic_id=?",
                (session["reader_id"], comic_id)
            ).fetchone())
    return render_template("comic.html", comic=comic, chapters=chapters, is_bookmarked=is_bookmarked)


@app.route("/read/<int:chapter_id>")
def read_chapter(chapter_id):
    with get_db() as db:
        chapter = db.execute("""
            SELECT ch.*, c.id AS comic_id, c.title AS comic_title
            FROM chapters ch JOIN comics c ON c.id = ch.comic_id
            WHERE ch.id = ?
        """, (chapter_id,)).fetchone()
        if not chapter:
            abort(404)
        pages = db.execute(
            "SELECT * FROM pages WHERE chapter_id = ? ORDER BY page_order, id",
            (chapter_id,)
        ).fetchall()
        if session.get("reader_id"):
            db.execute("""
                INSERT INTO reading_history(reader_id, comic_id, chapter_id, last_read_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(reader_id, chapter_id) DO UPDATE SET last_read_at=excluded.last_read_at
            """, (session["reader_id"], chapter["comic_id"], chapter_id,
                  datetime.now().isoformat(timespec="seconds")))
        nav = db.execute("""
            SELECT id FROM chapters
            WHERE comic_id = ? AND chapter_number < ?
            ORDER BY chapter_number DESC LIMIT 1
        """, (chapter["comic_id"], chapter["chapter_number"])).fetchone()
        next_chapter = db.execute("""
            SELECT id FROM chapters
            WHERE comic_id = ? AND chapter_number > ?
            ORDER BY chapter_number ASC LIMIT 1
        """, (chapter["comic_id"], chapter["chapter_number"])).fetchone()
    return render_template("reader.html", chapter=chapter, pages=pages,
                           prev_chapter=nav, next_chapter=next_chapter)


@app.route("/account/register", methods=["GET", "POST"])
def reader_register():
    if session.get("reader_id"):
        return redirect(url_for("profile"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        display_name = request.form.get("display_name", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_]{3,24}", username):
            flash("Tên đăng nhập phải dài 3–24 ký tự, chỉ gồm chữ, số hoặc dấu gạch dưới.", "danger")
        elif len(password) < 8:
            flash("Mật khẩu cần ít nhất 8 ký tự.", "danger")
        elif password != confirm:
            flash("Mật khẩu xác nhận không khớp.", "danger")
        else:
            try:
                with get_db() as db:
                    cur = db.execute(
                        "INSERT INTO readers(username, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
                        (username, generate_password_hash(password), display_name or username,
                         datetime.now().isoformat(timespec="seconds"))
                    )
                    reader_id = cur.lastrowid
                session.clear()
                session["reader_id"] = reader_id
                session["reader_name"] = display_name or username
                flash("Tạo tài khoản thành công. Chào mừng bạn!", "success")
                return redirect(url_for("profile"))
            except sqlite3.IntegrityError:
                flash("Tên đăng nhập đã được sử dụng.", "danger")
    return render_template("reader_auth.html", mode="register")


@app.route("/account/login", methods=["GET", "POST"])
def reader_login():
    if session.get("reader_id"):
        return redirect(url_for("profile"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            reader = db.execute("SELECT * FROM readers WHERE username = ?", (username,)).fetchone()
        if reader and check_password_hash(reader["password_hash"], password):
            session.clear()
            session["reader_id"] = reader["id"]
            session["reader_name"] = reader["display_name"] or reader["username"]
            flash("Đăng nhập thành công.", "success")
            next_url = request.args.get("next", "")
            if next_url.startswith("/") and not next_url.startswith("//"):
                return redirect(next_url)
            return redirect(url_for("profile"))
        flash("Tên đăng nhập hoặc mật khẩu không đúng.", "danger")
    return render_template("reader_auth.html", mode="login")


@app.route("/account/logout", methods=["POST"])
def reader_logout():
    if not session.get("reader_id"):
        return redirect(url_for("index"))
    session.pop("reader_id", None)
    session.pop("reader_name", None)
    flash("Bạn đã đăng xuất tài khoản độc giả.", "success")
    return redirect(url_for("index"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("reader_id"):
        flash("Vui lòng đăng nhập để xem hồ sơ độc giả.", "warning")
        return redirect(url_for("reader_login", next=request.path))
    reader_id = session["reader_id"]
    with get_db() as db:
        reader = db.execute("SELECT * FROM readers WHERE id = ?", (reader_id,)).fetchone()
        if not reader:
            session.pop("reader_id", None)
            session.pop("reader_name", None)
            flash("Tài khoản không còn tồn tại. Vui lòng đăng nhập lại.", "warning")
            return redirect(url_for("reader_login"))
        if request.method == "POST":
            display_name = request.form.get("display_name", "").strip()[:40]
            if not display_name:
                flash("Tên hiển thị không được để trống.", "danger")
            else:
                db.execute("UPDATE readers SET display_name=? WHERE id=?", (display_name, reader_id))
                session["reader_name"] = display_name
                flash("Đã cập nhật hồ sơ.", "success")
                return redirect(url_for("profile"))
        bookmarks = db.execute("""
            SELECT c.*, b.created_at, (SELECT COUNT(*) FROM chapters ch WHERE ch.comic_id=c.id) AS chapter_count
            FROM bookmarks b JOIN comics c ON c.id=b.comic_id
            WHERE b.reader_id=? ORDER BY b.created_at DESC
        """, (reader_id,)).fetchall()
        history = db.execute("""
            SELECT h.last_read_at, c.id AS comic_id, c.title AS comic_title, c.cover,
                   ch.id AS chapter_id, ch.title AS chapter_title, ch.chapter_number
            FROM reading_history h JOIN comics c ON c.id=h.comic_id
            JOIN chapters ch ON ch.id=h.chapter_id
            WHERE h.reader_id=? ORDER BY h.last_read_at DESC LIMIT 30
        """, (reader_id,)).fetchall()
    return render_template("profile.html", reader=reader, bookmarks=bookmarks, history=history)


@app.route("/comic/<int:comic_id>/bookmark", methods=["POST"])
def toggle_bookmark(comic_id):
    if not session.get("reader_id"):
        flash("Đăng nhập để thêm truyện vào danh sách yêu thích nhé.", "warning")
        return redirect(url_for("reader_login", next=url_for("comic_detail", comic_id=comic_id)))
    with get_db() as db:
        comic = db.execute("SELECT id FROM comics WHERE id=?", (comic_id,)).fetchone()
        if not comic:
            abort(404)
        existing = db.execute("SELECT id FROM bookmarks WHERE reader_id=? AND comic_id=?",
                              (session["reader_id"], comic_id)).fetchone()
        if existing:
            db.execute("DELETE FROM bookmarks WHERE id=?", (existing["id"],))
            flash("Đã bỏ truyện khỏi danh sách yêu thích.", "success")
        else:
            db.execute("INSERT INTO bookmarks(reader_id, comic_id, created_at) VALUES (?, ?, ?)",
                       (session["reader_id"], comic_id, datetime.now().isoformat(timespec="seconds")))
            flash("Đã thêm truyện vào danh sách yêu thích.", "success")
    return redirect(url_for("comic_detail", comic_id=comic_id))


@app.route("/admin/login", methods=["GET", "POST"])
def login():
    if session.get("admin_id"):
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with get_db() as db:
            admin = db.execute("SELECT * FROM admins WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_name"] = admin["username"]
            flash("Dang nhap thanh cong.", "success")
            return redirect(request.args.get("next") or url_for("dashboard"))
        flash("Ten dang nhap hoac mat khau khong dung.", "danger")
    return render_template("login.html")


@app.route("/admin/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    flash("Da dang xuat.", "success")
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def dashboard():
    with get_db() as db:
        comics = db.execute("""
            SELECT c.*, COUNT(ch.id) AS chapter_count
            FROM comics c LEFT JOIN chapters ch ON ch.comic_id = c.id
            GROUP BY c.id ORDER BY c.id DESC
        """).fetchall()
        stats = {
            "comics": db.execute("SELECT COUNT(*) FROM comics").fetchone()[0],
            "chapters": db.execute("SELECT COUNT(*) FROM chapters").fetchone()[0],
            "pages": db.execute("SELECT COUNT(*) FROM pages").fetchone()[0],
        }
    return render_template("dashboard.html", comics=comics, stats=stats)


@app.route("/admin/comic/new", methods=["GET", "POST"])
@admin_required
def comic_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if not title:
            flash("Ten truyen khong duoc de trong.", "danger")
            return render_template("comic_form.html", comic=None)
        cover = ""
        try:
            cover = save_image(request.files.get("cover"), COVER_DIR) or ""
        except ValueError as exc:
            flash(str(exc), "danger")
            return render_template("comic_form.html", comic=None)
        with get_db() as db:
            db.execute("""
                INSERT INTO comics(title, author, description, category, status, cover, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                title, request.form.get("author", "").strip(),
                request.form.get("description", "").strip(),
                request.form.get("category", "Khac").strip() or "Khac",
                request.form.get("status", "Dang cap nhat"),
                cover, datetime.now().isoformat(timespec="seconds")
            ))
        flash("Da them truyen moi.", "success")
        return redirect(url_for("dashboard"))
    return render_template("comic_form.html", comic=None)


@app.route("/admin/comic/<int:comic_id>/edit", methods=["GET", "POST"])
@admin_required
def comic_edit(comic_id):
    with get_db() as db:
        comic = db.execute("SELECT * FROM comics WHERE id = ?", (comic_id,)).fetchone()
        if not comic:
            abort(404)
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            if not title:
                flash("Ten truyen khong duoc de trong.", "danger")
                return render_template("comic_form.html", comic=comic)
            cover = comic["cover"]
            try:
                new_cover = save_image(request.files.get("cover"), COVER_DIR)
                if new_cover:
                    delete_image(COVER_DIR, cover)
                    cover = new_cover
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("comic_form.html", comic=comic)
            db.execute("""
                UPDATE comics SET title=?, author=?, description=?, category=?, status=?, cover=?
                WHERE id=?
            """, (
                title, request.form.get("author", "").strip(),
                request.form.get("description", "").strip(),
                request.form.get("category", "Khac").strip() or "Khac",
                request.form.get("status", "Dang cap nhat"), cover, comic_id
            ))
            flash("Da cap nhat truyen.", "success")
            return redirect(url_for("dashboard"))
    return render_template("comic_form.html", comic=comic)


@app.route("/admin/comic/<int:comic_id>/delete", methods=["POST"])
@admin_required
def comic_delete(comic_id):
    with get_db() as db:
        comic = db.execute("SELECT * FROM comics WHERE id = ?", (comic_id,)).fetchone()
        if not comic:
            abort(404)
        chapters = db.execute("SELECT id FROM chapters WHERE comic_id = ?", (comic_id,)).fetchall()
        for chapter in chapters:
            pages = db.execute("SELECT image FROM pages WHERE chapter_id = ?", (chapter["id"],)).fetchall()
            for page in pages:
                delete_image(CHAPTER_DIR, page["image"])
        delete_image(COVER_DIR, comic["cover"])
        db.execute("DELETE FROM comics WHERE id = ?", (comic_id,))
    flash("Da xoa truyen va cac chuong lien quan.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/comic/<int:comic_id>/chapter/new", methods=["GET", "POST"])
@admin_required
def chapter_new(comic_id):
    with get_db() as db:
        comic = db.execute("SELECT * FROM comics WHERE id = ?", (comic_id,)).fetchone()
        if not comic:
            abort(404)
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            try:
                number = float(request.form.get("chapter_number", ""))
            except ValueError:
                number = None
            images = request.files.getlist("pages")
            images = [f for f in images if f and f.filename]
            if not title or number is None or not images:
                flash("Can nhap ten chuong, so chuong va it nhat mot anh trang truyen.", "danger")
                return render_template("chapter_form.html", comic=comic)
            if len(images) > 100:
                flash("Moi chuong toi da 100 anh.", "danger")
                return render_template("chapter_form.html", comic=comic)
            saved = []
            try:
                for image in images:
                    name = save_image(image, CHAPTER_DIR)
                    if name:
                        saved.append(name)
            except ValueError as exc:
                for name in saved:
                    delete_image(CHAPTER_DIR, name)
                flash(str(exc), "danger")
                return render_template("chapter_form.html", comic=comic)
            cur = db.execute("""
                INSERT INTO chapters(comic_id, title, chapter_number, created_at)
                VALUES (?, ?, ?, ?)
            """, (comic_id, title, number, datetime.now().isoformat(timespec="seconds")))
            chapter_id = cur.lastrowid
            for order, name in enumerate(saved, start=1):
                db.execute(
                    "INSERT INTO pages(chapter_id, image, page_order) VALUES (?, ?, ?)",
                    (chapter_id, name, order)
                )
            flash(f"Da dang chuong voi {len(saved)} trang.", "success")
            return redirect(url_for("dashboard"))
    return render_template("chapter_form.html", comic=comic)


@app.route("/admin/chapter/<int:chapter_id>/delete", methods=["POST"])
@admin_required
def chapter_delete(chapter_id):
    with get_db() as db:
        chapter = db.execute("SELECT * FROM chapters WHERE id = ?", (chapter_id,)).fetchone()
        if not chapter:
            abort(404)
        pages = db.execute("SELECT image FROM pages WHERE chapter_id = ?", (chapter_id,)).fetchall()
        for page in pages:
            delete_image(CHAPTER_DIR, page["image"])
        db.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
    flash("Da xoa chuong.", "success")
    return redirect(url_for("dashboard"))


@app.route("/admin/password", methods=["GET", "POST"])
@admin_required
def change_password():
    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        with get_db() as db:
            admin = db.execute("SELECT * FROM admins WHERE id = ?", (session["admin_id"],)).fetchone()
            if not check_password_hash(admin["password_hash"], old):
                flash("Mat khau hien tai khong dung.", "danger")
            elif len(new) < 10:
                flash("Mat khau moi can it nhat 10 ky tu.", "danger")
            elif new != confirm:
                flash("Mat khau xac nhan khong khop.", "danger")
            else:
                db.execute(
                    "UPDATE admins SET password_hash=? WHERE id=?",
                    (generate_password_hash(new), session["admin_id"])
                )
                flash("Da doi mat khau.", "success")
                return redirect(url_for("dashboard"))
    return render_template("password.html")


@app.context_processor
def inject_globals():
    return {"admin_logged_in": bool(session.get("admin_id")),
            "admin_name": session.get("admin_name"),
            "reader_logged_in": bool(session.get("reader_id")),
            "reader_name": session.get("reader_name")}


with app.app_context():
    init_db()

if __name__ == "__main__":
    # Chi phuc vu phat trien tren may ca nhan; khong dung debug=True khi dua len mang.
    app.run(host="127.0.0.1", port=5000, debug=True)
