MANGA DARK - FLASK WEBSITE
==========================

QUAN TRONG: Khi upload len GitHub, phai upload CAC NOI DUNG BEN TRONG thu muc nay.
Khong upload nguyen thu muc long thanh manga_website/manga_website.

Cau truc dung tai repository root:
  app.py
  requirements.txt
  Procfile
  templates/ (cac file .html nam trong day)
  static/css/style.css
  static/js/main.js
  static/uploads/covers/
  static/uploads/chapters/

Deploy Render:
  Build Command: pip install -r requirements.txt
  Start Command: gunicorn app:app
  Root Directory: de trong

Tai khoan Admin mac dinh lan dau:
  username: admin
  password: admin12345
  Doi mat khau ngay sau khi dang nhap tai /admin/password.

Doc gia:
  Dang ky: /account/register
  Dang nhap: /account/login
  Ho so: /profile

Admin:
  Dang nhap: /admin/login
  Quan tri: /admin

Luu y du lieu:
  Ban nay dung SQLite (manga.db) va luu anh trong static/uploads.
  Tren Render Free, filesystem khong ben vung; database va anh co the mat khi deploy/restart.
  Khong dung de van hanh lau dai truoc khi cau hinh PostgreSQL va object storage/persistent disk.

Noi dung truyen va anh phai la noi dung ban co quyen su dung.
