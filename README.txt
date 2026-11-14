MANGA DARK - BO MA NGUON HOAN CHINH
===================================

TINH NANG
- Trang chu, tim kiem, loc the loai, trang chi tiet va doc chuong.
- Khach khong can tai khoan van xem duoc truyen va chuong.
- Doc gia dang ky/dang nhap rieng tai /account/register va /account/login.
- Ho so doc gia, doi ten hien thi, lich su doc, doc tiep va danh sach yeu thich.
- Chi Admin duoc dang nhap tai /admin/login de dang/sua/xoa truyen va chuong.
- Nut Admin khong hien tren thanh dieu huong cong khai. Duong dan quan tri van duoc bao ve bang dang nhap.
- Mat khau duoc luu dang hash; form duoc bao ve CSRF.

CHAY TREN WINDOWS
1. Cai Python 3.10 tro len.
2. Mo Terminal tai thu muc co app.py.
3. py -m venv .venv
4. .venv\Scripts\activate
5. py -m pip install -r requirements.txt
6. py app.py
7. Mo http://127.0.0.1:5000

DEPLOY RENDER
Build Command: pip install -r requirements.txt
Start Command: gunicorn app:app
Root Directory: de trong neu app.py nam o thu muc goc repository.
Chon Free neu muon thu nghiem mien phi.

ENVIRONMENT VARIABLES KHUYEN NGHI
MANGA_SECRET_KEY = chuoi ngau nhien dai, rieng tu
MANGA_ADMIN_USER = ten admin muon tao trong lan khoi tao database dau tien
MANGA_ADMIN_PASSWORD = mat khau admin manh trong lan khoi tao database dau tien

QUAN TRONG VE ADMIN
- Tai khoan Admin da ton tai trong database se khong tu dong doi mat khau khi sua Environment Variables.
- Doi mat khau Admin sau khi dang nhap bang trang /admin/password.
- Khong chia se anh chup co mat khau hoac gia tri Environment Variables.

CAP NHAT GITHUB MA KHONG MAT DU LIEU
1. Nen tai ban sao database va tep anh truoc khi cap nhat neu ban dang co du lieu that.
2. Giu nguyen ten cac thu muc va tep: app.py, requirements.txt, templates/, static/.
3. Upload/ghi de cac tep code tu bo ma nguon nay vao repository, sau do Commit changes.
4. Render tu dong deploy lai neu da bat Auto-Deploy.
5. Khong xoa database hoac static/uploads neu muon giu du lieu cu.

DU LIEU VA LUU TRU - CAN DOC
Ung dung hien dung SQLite (manga.db) va luu anh trong static/uploads. O dia Render Free mac dinh khong ben vung; database, tai khoan, lich su, yeu thich va anh co the mat sau khi deploy/restart. De van hanh lau dai, can cau hinh Persistent Disk hoac chuyen database sang PostgreSQL va anh sang object storage. Goi Free khong ho tro Persistent Disk.

NOI DUNG
Chi dang tai truyen/anh ma ban co quyen su dung.
