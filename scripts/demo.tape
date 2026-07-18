# famly-cli demo. Render with:  vhs scripts/demo.tape
# Everything runs against scripts/demo_server.py, so the data is entirely fake.

Output scripts/demo.gif

Set Shell bash
Set FontSize 16
Set Width 1080
Set Height 760
Set Padding 24

# --- hidden setup: start the fake backend, no real account involved ---
Hide
Type "cd $(git rev-parse --show-toplevel 2>/dev/null || pwd)" Enter
Type "export PS1='$ '" Enter
Type "export PATH=$PWD/.venv/bin:$PATH" Enter
Type "export FAMLY_BASE_URL=https://localhost:8765 SSL_CERT_FILE=$PWD/scripts/.demo/cert.pem FAMLY_ACCESS_TOKEN=demo" Enter
Type "rm -rf famly-demo famly-archive" Enter
Type "pkill -f demo_server.py 2>/dev/null; sleep 0.4" Enter
Type "python3 scripts/demo_server.py >/tmp/famly-demo.log 2>&1 &" Enter
Type "sleep 2" Enter
Sleep 2500ms
Type "clear" Enter
Show

# --- the demo ---
Type "# famly-cli archives your child's Famly photos and data (this demo is 100% fake)"
Sleep 800ms
Enter
Sleep 1s

Type "famly whoami"
Enter
Sleep 2s

Type "famly children"
Enter
Sleep 3s

Type "# download every full-resolution photo, all sources, and build a gallery"
Enter
Type "famly photos --incremental --gallery --out famly-demo"
Enter
Sleep 4s

Type "# or archive everything: photos plus feed, messages, notes, and events as JSON"
Enter
Type "famly export --out famly-archive"
Enter
Sleep 4s

# --- hidden teardown ---
Hide
Type "kill %1 2>/dev/null; rm -rf famly-demo famly-archive" Enter
Show
