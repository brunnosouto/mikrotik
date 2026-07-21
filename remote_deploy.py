import urllib.request
import json
import subprocess
import os

API_TOKEN = "e7af53806d16424ad9036117c309bae723d4a3be"
USER = "brunnosouto"
DOMAIN = "brunnosouto.pythonanywhere.com"

def deploy_to_pythonanywhere():
    print("1. Pushing latest code changes to GitHub...")
    cwd = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(["git", "add", "."], cwd=cwd, check=False)
    subprocess.run(["git", "commit", "-m", "Auto-deploy to PythonAnywhere via API"], cwd=cwd, check=False)
    subprocess.run(["git", "push", "origin", "main"], cwd=cwd, check=False)

    print(f"2. Triggering remote reload on PythonAnywhere for {DOMAIN} via API...")
    url = f"https://www.pythonanywhere.com/api/v0/user/{USER}/webapps/{DOMAIN}/reload/"
    req = urllib.request.Request(url, method='POST')
    req.add_header('Authorization', f'Token {API_TOKEN}')

    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.getcode()
            body = resp.read().decode('utf-8')
            print(f"PythonAnywhere API Status: {status} Response: {body}")
            print("🎉 SUCCESS: Remote deploy completed! PythonAnywhere is updated live!")
            return True
    except Exception as e:
        print("Deploy Error:", e)
        return False

if __name__ == '__main__':
    deploy_to_pythonanywhere()
