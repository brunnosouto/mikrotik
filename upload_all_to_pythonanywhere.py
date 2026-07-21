import urllib.request
import os

token = 'e7af53806d16424ad9036117c309bae723d4a3be'
user = 'brunnosouto'
domain = 'brunnosouto.pythonanywhere.com'

files_to_upload = [
    ('db.py', '/home/brunnosouto/mikrotik/db.py'),
    ('app.py', '/home/brunnosouto/mikrotik/app.py'),
    ('services/sla_service.py', '/home/brunnosouto/mikrotik/services/sla_service.py'),
    ('static/js/app.js', '/home/brunnosouto/mikrotik/static/js/app.js'),
    ('test_endpoints.py', '/home/brunnosouto/mikrotik/test_endpoints.py'),
]

def upload_file(local_path, remote_path):
    print(f"Uploading {local_path}...")
    with open(local_path, 'rb') as f:
        file_bytes = f.read()

    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    header = (
        '--' + boundary + '\r\n' +
        'Content-Disposition: form-data; name="content"; filename="' + os.path.basename(local_path) + '"\r\n' +
        'Content-Type: application/octet-stream\r\n\r\n'
    ).encode('utf-8')
    footer = ('\r\n--' + boundary + '--\r\n').encode('utf-8')

    body = header + file_bytes + footer
    url = f'https://www.pythonanywhere.com/api/v0/user/{user}/files/path{remote_path}'
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Authorization', f'Token {token}')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"Uploaded {local_path} ({resp.getcode()})")
            return True
    except Exception as e:
        print(f"Upload error {local_path}: {e}")
        return False

for local, remote in files_to_upload:
    upload_file(local, remote)

print("Reloading webapp...")
url_reload = f'https://www.pythonanywhere.com/api/v0/user/{user}/webapps/{domain}/reload/'
req_reload = urllib.request.Request(url_reload, method='POST')
req_reload.add_header('Authorization', f'Token {token}')

try:
    with urllib.request.urlopen(req_reload, timeout=5) as resp:
        print(f"Reload status: {resp.getcode()}")
except Exception as e:
    print(f"Reload error: {e}")
