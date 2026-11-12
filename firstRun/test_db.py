import socket
import sys
import mysql.connector
from backend.config import DB_CONFIG

host = DB_CONFIG["host"]
port = DB_CONFIG.get("port", 3306)
user = DB_CONFIG["user"]
database = DB_CONFIG["database"]

print("=" * 60)
print(f"[*] ĐANG KIỂM TRA KẾT NỐI TỚI SERVER DATABASE: {host}:{port}")
print("=" * 60)

# BƯỚC 1: Kiểm tra thông mạng ở tầng TCP (Ping socket tới port 3306)
print("\n[1] Kiểm tra cổng mạng (TCP Socket)...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)  # Chờ tối đa 5 giây
    res = sock.connect_ex((host, port))
    sock.close()
    if res == 0:
        print(f" -> THÀNH CÔNG: Port {port} trên máy chủ {host} đang MỞ và nhận kết nối.")
    else:
        print(f" -> THẤT BẠI: Không thể mở kết nối tới {host}:{port} (Error code: {res}).")
        print(" -> Nguyên nhân: Máy chủ đang tắt, sai IP, hoặc cổng 3306 bị tường lửa chặn.")
        sys.exit(1)
except socket.timeout:
    print(f" -> HẾT THỜI GIAN CHỜ (Timeout): Không phản hồi sau 5 giây.")
    print(" -> Nguyên nhân: Tường lửa (Firewall/UFW) trên VPS đang chặn kết nối ngoài.")
    sys.exit(1)
except Exception as e:
    print(f" -> LỖI MẠNG: {e}")
    sys.exit(1)

# BƯỚC 2: Kiểm tra xác thực tài khoản MySQL (User/Password/Database)
print("\n[2] Kiểm tra quyền truy cập MySQL (User/Pass/DB)...")
try:
    conn = mysql.connector.connect(
        connection_timeout=5,
        **DB_CONFIG
    )
    if conn.is_connected():
        print(f" -> THÀNH CÔNG: Đã đăng nhập vào MySQL bằng tài khoản '{user}'.")
        print(f" -> Database hiện tại: '{database}'")
        
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES;")
        tables = [t[0] for t in cursor.fetchall()]
        print(f" -> Các bảng hiện có trong CSDL: {tables}")
        
        cursor.close()
        conn.close()
        print("\n" + "=" * 60)
        print("[KẾT LUẬN] Kết nối Database hoàn toàn bình thường và sẵn sàng sử dụng!")
        print("=" * 60)
except mysql.connector.Error as err:
    print(f" -> LỖI ĐĂNG NHẬP MYSQL: {err}")
    if err.errno == 1045:
        print(" -> Nguyên nhân: Sai tên đăng nhập (user) hoặc mật khẩu (password).")
    elif err.errno == 1049:
        print(f" -> Nguyên nhân: Không tìm thấy database tên '{database}'.")
    else:
        print(f" -> Mã lỗi: {err.errno}")
except Exception as e:
    print(f" -> LỖI BẤT THƯỜNG: {e}")