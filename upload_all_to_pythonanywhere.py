import urllib.request
import os
import json

token = 'e7af53806d16424ad9036117c309bae723d4a3be'
user = 'brunnosouto'
domain = 'brunnosouto.pythonanywhere.com'

files_to_upload = [
    ('app.py', '/home/brunnosouto/mikrotik/app.py'),
    ('db.py', '/home/brunnosouto/mikrotik/db.py'),
    ('services/sla_service.py', '/home/brunnosouto/mikrotik/services/sla_service.py'),
    ('static/css/style.css', '/home/brunnosouto/mikrotik/static/css/style.css'),
    ('static/js/app.js', '/home/brunnosouto/mikrotik/static/js/app.js'),
    ('static/js/charts.js', '/home/brunnosouto/mikrotik/static/js/charts.js'),
    ('templates/index.html', '/home/brunnosouto/mikrotik/templates/index.html'),
]

def upload_file(local_path, remote_path):
    print(f"Uploading {local_path} -> {remote_path}...")
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
        with urllib.request.urlopen(req) as resp:
            print(f"Uploaded {local_path} successfully ({resp.getcode()})")
            return True
    except Exception as e:
        print(f"Failed to upload {local_path}: {e}")
        return False

# 1. Upload all files
for local, remote in files_to_upload:
    upload_file(local, remote)

# 2. Reload Webapp
print("Triggering webapp reload via API...")
url_reload = f'https://www.pythonanywhere.com/api/v0/user/{user}/webapps/{domain}/reload/'
req_reload = urllib.request.Request(url_reload, method='POST')
req_reload.add_header('Authorization', f'Token {token}')

try:
    with urllib.request.urlopen(req_reload) as resp:
        print(f"Webapp reloaded successfully! ({resp.getcode()})")
except Exception as e:
    print(f"Reload failed: {e}")
