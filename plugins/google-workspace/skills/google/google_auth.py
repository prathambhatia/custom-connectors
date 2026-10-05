#!/usr/bin/env python3
"""Google OAuth helper. Usage: google_auth.py login | token. Secrets live in macOS Keychain only."""
import http.server, json, secrets, subprocess, sys, threading, urllib.parse, urllib.request, webbrowser, getpass, os

SCOPES = " ".join([
    "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/presentations",
    "https://mail.google.com/", "https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/tasks"])
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
ACCT = os.environ.get("USER") or getpass.getuser()

def kc_get(svc):
    r = subprocess.run(["security", "find-generic-password", "-s", svc, "-w"], capture_output=True, text=True)
    if r.returncode: sys.exit(f"Keychain item {svc} not found")
    return r.stdout.strip()

def kc_set(svc, val):
    subprocess.run(["security", "add-generic-password", "-a", ACCT, "-s", svc, "-w", val, "-U"], check=True)

def post(data):
    req = urllib.request.Request(TOKEN, urllib.parse.urlencode(data).encode())
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        sys.exit(f"token endpoint error {e.code}: {json.loads(e.read() or b'{}').get('error', '')}")

def login():
    cid, csec = kc_get("google-oauth-client-id"), kc_get("google-oauth-client-secret")
    state, box = secrets.token_urlsafe(16), {}
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" in q or "error" in q:
                box.update({k: v[0] for k, v in q.items()})
                self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
                self.wfile.write(b"Done. You can close this tab.")
            else:
                self.send_response(404); self.end_headers()
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = AUTH + "?" + urllib.parse.urlencode({"client_id": cid, "redirect_uri": redirect, "response_type": "code",
        "scope": SCOPES, "access_type": "offline", "prompt": "consent", "state": state})
    print("Consent URL (also opening in browser):\n" + url, flush=True)
    webbrowser.open(url)
    srv.timeout = 1
    import time; end = time.time() + 600
    while not box and time.time() < end: srv.handle_request()
    if not box: sys.exit("timed out waiting for consent")
    if box.get("state") != state or "code" not in box: sys.exit(f"login failed: {box.get('error', 'state mismatch')}")
    tok = post({"code": box["code"], "client_id": cid, "client_secret": csec, "redirect_uri": redirect, "grant_type": "authorization_code"})
    if "refresh_token" not in tok: sys.exit("no refresh_token returned")
    kc_set("google-refresh-token-personal", tok["refresh_token"])
    print("Refresh token saved to Keychain (google-refresh-token-personal).")

def token():
    tok = post({"client_id": kc_get("google-oauth-client-id"), "client_secret": kc_get("google-oauth-client-secret"),
                "refresh_token": kc_get("google-refresh-token-personal"), "grant_type": "refresh_token"})
    print(tok["access_token"])

if __name__ == "__main__":
    {"login": login, "token": token}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
