import json
import os
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(__file__), 'sku_erp.sqlite')
HTML_PATH = Path(__file__).resolve().with_name('erp.html')
HOST = '0.0.0.0'  # listen on all network interfaces so LAN computers can connect (not just this machine)
PORT = 8000


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS app_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    row = conn.execute('SELECT payload FROM app_state WHERE id = 1').fetchone()
    if not row:
        default_payload = {
            'users': [
                {
                    'id': 'admin_default',
                    'username': 'admin',
                    'password': 'admin123',
                    'name': 'Super Admin',
                    'role': 'superadmin',
                    'permissions': {}
                }
            ]
        }
        conn.execute(
            'INSERT INTO app_state (id, payload, updated_at) VALUES (1, ?, ?)',
            (json.dumps(default_payload), datetime.utcnow().isoformat())
        )
        conn.commit()
    conn.close()


def load_state():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT payload FROM app_state WHERE id = 1').fetchone()
    conn.close()
    if not row:
        return {}
    return json.loads(row[0])


def save_state(payload):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'UPDATE app_state SET payload = ?, updated_at = ? WHERE id = 1',
        (json.dumps(payload), datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


class ERPHandler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status, html):
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ('/', '/health'):
            if parsed.path == '/':
                if HTML_PATH.exists():
                    self._send_html(200, HTML_PATH.read_text(encoding='utf-8'))
                    return
            self._send_json(200, {'status': 'ok', 'database': DB_PATH, 'endpoint': '/api/db'})
        elif parsed.path == '/api/db':
            self._send_json(200, load_state())
        else:
            self._send_json(404, {'error': 'not found'})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/db':
            self._send_json(404, {'error': 'not found'})
            return
        length = int(self.headers.get('Content-Length', '0'))
        payload = self.rfile.read(length).decode('utf-8')
        try:
            data = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            self._send_json(400, {'error': 'invalid json'})
            return
        save_state(data)
        self._send_json(200, {'status': 'saved'})

    def log_message(self, format, *args):
        return


def get_lan_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = socket.gethostbyname(socket.gethostname())
    finally:
        s.close()
    return ip


if __name__ == '__main__':
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), ERPHandler)
    lan_ip = get_lan_ip()
    print('=' * 60)
    print(' ERP database server is running')
    print('=' * 60)
    print(f' On THIS computer:         http://localhost:{PORT}/')
    print(f' On OTHER LAN computers:   http://{lan_ip}:{PORT}/')
    print('=' * 60)
    print(' Share the second link with any computer on the same')
    print(' Wi-Fi / network to let them use the ERP too.')
    print(' Keep this window open — closing it stops the server.')
    print('=' * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down ERP database server...')
        server.shutdown()
