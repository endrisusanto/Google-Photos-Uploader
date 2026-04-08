import os
import mimetypes
import time
import json
import threading
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone, timedelta
from watchdog.observers.polling import PollingObserver as Observer
from watchdog.events import FileSystemEventHandler
from gpmc import Client

# Register missing mime types
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('video/3gpp', '.3gp')
mimetypes.add_type('video/3gpp', '.3gpp')
mimetypes.add_type('image/heic', '.heic')
mimetypes.add_type('video/x-ms-wmv', '.wmv')
mimetypes.add_type('video/quicktime', '.mov')
mimetypes.add_type('video/x-msvideo', '.avi')

DB_FILE = "/data/uploader.db"

# Database initialization
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, action TEXT, file TEXT, filesize TEXT, metadata TEXT)''')
    
    # Config table for persistent settings
    c.execute('''CREATE TABLE IF NOT EXISTS config
                 (key TEXT PRIMARY KEY, value TEXT)''')
    
    # Try to add columns if they don't exist in an already created table
    try:
        c.execute("ALTER TABLE logs ADD COLUMN filesize TEXT")
        c.execute("ALTER TABLE logs ADD COLUMN metadata TEXT")
    except sqlite3.OperationalError:
        pass # Columns already exist

    c.execute('''CREATE TABLE IF NOT EXISTS stats
                 (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_config(key, default=""):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = c.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return os.environ.get(key.upper(), default)

def set_config(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# Load initial config
WATCHED_FOLDER = os.environ.get("WATCHED_FOLDER", "/data")
AUTH_DATA = get_config("auth_data", "")

# Global state for monitoring
stats = {
    "total_uploads": 0,
    "session_uploads": 0,
    "total_seen": 0,
    "last_event_time": None,
    "upload_speed": "0 KB/s",
    "events": []
}

def load_initial_stats():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM logs WHERE action LIKE '%Terunggah%'")
        stats["total_uploads"] = c.fetchone()[0]
        
        # Load last 100 events to memory
        c.execute("SELECT time, action, file, filesize, metadata FROM logs ORDER BY id DESC LIMIT 100")
        for row in c.fetchall():
            stats["events"].append({
                "time": row[0], "action": row[1], "file": row[2], "filesize": row[3], "metadata": row[4]
            })
        conn.close()
    except Exception as e:
        print(f"Gagal memuat statistik awal: {e}")

load_initial_stats()

def add_event(action, file_path, filesize="", metadata=""):
    now = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S")

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO logs (time, action, file, filesize, metadata) VALUES (?, ?, ?, ?, ?)", 
              (now, action, file_path, filesize, metadata))
    conn.commit()
    conn.close()

    # Memory state for quick update
    event = {"time": now, "action": action, "file": file_path, "filesize": filesize, "metadata": metadata}
    stats["events"].insert(0, event)
    stats["events"] = stats["events"][:100]
    stats["last_event_time"] = now
    
    if "Terunggah" in action:
        stats["total_uploads"] += 1
        stats["session_uploads"] += 1

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            try:
                with open('index.html', 'rb') as f:
                    self.wfile.write(f.read())
            except FileNotFoundError:
                self.wfile.write(b"index.html not found")
        elif self.path == '/api/logs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
        elif self.path == '/api/config':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            config_data = {
                "auth_data": AUTH_DATA
            }
            self.wfile.write(json.dumps(config_data).encode())
        elif self.path.startswith('/media/'):
            try:
                file_path = self.path[1:] # remove leading /
                if os.path.exists(file_path):
                    self.send_response(200)
                    mime_type, _ = mimetypes.guess_type(file_path)
                    self.send_header('Content-type', mime_type or 'application/octet-stream')
                    self.end_headers()
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404)
            except Exception:
                self.send_error(500)
        elif self.path == '/favicon.ico':
            if os.path.exists('media/Google-Photos-Logo.png'):
                self.send_response(301)
                self.send_header('Location', '/media/Google-Photos-Logo.png')
                self.end_headers()
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/restart':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "restarting"}).encode())
            print("Restart diperintahkan melalui dashboard. Keluar...")
            def delayed_exit():
                time.sleep(1)
                os._exit(0)
            threading.Thread(target=delayed_exit).start()
            
        elif self.path == '/api/config':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            if 'auth_data' in data:
                set_config('auth_data', data['auth_data'])
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "message": "Konfigurasi disimpan. Silakan restart."}).encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        return # Disable console logging for HTTP requests

# Initialize client lazily
client = None
def get_client():
    global client
    if client is None:
        if not AUTH_DATA:
            raise ValueError("AUTH_DATA belum dikonfigurasi. Silakan masuk ke Dashboard -> Pengaturan.")
        client = Client(auth_data=AUTH_DATA)
    return client

class PhotoHandler(FileSystemEventHandler):
    def process_file(self, file_path, is_initial=False):
        if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.webp', '.mp4', '.3gp', '.3gpp', '.wmv', '.mov', '.avi', '.gif')):
            # Untuk file awal, jangan tambah seen karena sudah dihitung di awal
            if not is_initial:
                stats["total_seen"] += 1
                
            print(f"Memproses file: {file_path}")
            
            file_size_str = ""
            file_type = file_path.split('.')[-1].upper()
            try:
                size_bytes = os.path.getsize(file_path)
                if size_bytes < 1024 * 1024:
                    file_size_str = f"{size_bytes/1024:.1f} KB"
                else:
                    file_size_str = f"{size_bytes/(1024*1024):.1f} MB"
            except OSError:
                pass

            add_event("Memproses", file_path, file_size_str, file_type)

            try:
                # Measure Time
                start_time = time.time()
                file_size = os.path.getsize(file_path)
                
                # Unggah file
                c = get_client()
                output = c.upload(target=file_path, show_progress=True)
                
                # Calculate Speed
                duration = max(time.time() - start_time, 0.1)
                speed_kbps = (file_size / 1024) / duration
                if speed_kbps > 1024:
                    stats["upload_speed"] = f"{speed_kbps/1024:.1f} MB/s"
                else:
                    stats["upload_speed"] = f"{speed_kbps:.1f} KB/s"

                print(f"Terunggah: {output} ({stats['upload_speed']})")
                add_event("Terunggah", file_path, file_size_str, file_type)

                # Berusaha menghapus dengan 3 percobaan
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        os.remove(file_path)
                        print(f"File dihapus: {file_path}")
                        add_event("Dihapus", file_path, file_size_str, file_type)
                        break
                    except PermissionError:
                        if attempt < max_retries - 1:
                            time.sleep(0.5 * (attempt + 1))
                            continue
                        raise
                        
            except Exception as e:
                print(f"Terjadi kesalahan: {e}")
                add_event(f"Gagal: {str(e)[:50]}...", file_path, file_size_str, file_type)

    def on_created(self, event):
        if not event.is_directory:
            # Beri jeda sebentar untuk memastikan file sudah tertulis sempurna
            time.sleep(1)
            self.process_file(event.src_path, is_initial=False)

def start_server():
    server = HTTPServer(('0.0.0.0', 8080), DashboardHandler)
    print("Dashboard tersedia di port 8080")
    server.serve_forever()

if __name__ == "__main__":
    # Start web server thread
    web_thread = threading.Thread(target=start_server, daemon=True)
    web_thread.start()

    # Pre-check AUTH_DATA
    if not AUTH_DATA:
        print("PERINGATAN: AUTH_DATA belum diset. Dashboard tetap aktif di port 8080 untuk konfigurasi.")
        # Kita tetap jalankan loop utama agar container tidak exit
        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            sys.exit(0)

    event_handler = PhotoHandler()
    
    # Hitung total file keseluruhan di awal agar x di (38/x) akurat
    print(f"Memindai total file di {WATCHED_FOLDER}...")
    initial_files = []
    if os.path.exists(WATCHED_FOLDER):
        for root, dirs, files in os.walk(WATCHED_FOLDER):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.heic', '.webp', '.mp4', '.3gp', '.3gpp', '.wmv', '.mov', '.avi', '.gif')):
                    initial_files.append(os.path.join(root, file))
    
    stats["total_seen"] = len(initial_files)
    print(f"Ditemukan {stats['total_seen']} file yang akan diproses.")

    observer = Observer()
    if os.path.exists(WATCHED_FOLDER):
        try:
            observer.schedule(event_handler, WATCHED_FOLDER, recursive=True)
            observer.start()
            print(f"Pemantauan dimulai di {WATCHED_FOLDER}...")
        except Exception as e:
            print(f"Gagal memulai observer: {e}")
    else:
        print(f"Peringatan: Folder {WATCHED_FOLDER} tidak ditemukan.")

    # Proses file yang sudah ada
    for file_path in initial_files:
        event_handler.process_file(file_path, is_initial=True)

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
