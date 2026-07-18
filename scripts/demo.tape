# famly-cli demo.  Render with:  scripts/render_demo.sh   (needs: vhs, SF Mono)
# The render helper starts scripts/demo_server.py first, so every command runs
# against entirely fake data. Rendered at 1800px (2x) and embedded in the README
# at width=900 for a crisp 2:1 retina mapping.

Output scripts/demo.gif
Output scripts/demo.mp4

Set Shell "bash"
Set FontFamily "SF Mono"
Set FontSize 30
Set Width 1800
Set Height 1300
Set Padding 20
Set Margin 56
Set MarginFill "#591ab2"
Set BorderRadius 10
Set WindowBar Colorful
Set Framerate 24
Set TypingSpeed 55ms

# --- hidden setup: point the CLI at the already-running fake backend ---
Hide
Type "cd $(git rev-parse --show-toplevel 2>/dev/null || pwd)" Enter
Type "export PS1='$ '" Enter
Type "export PATH=$PWD/.venv/bin:$PATH" Enter
Type "export FAMLY_BASE_URL=https://localhost:8765 SSL_CERT_FILE=$PWD/scripts/.demo/cert.pem FAMLY_ACCESS_TOKEN=demo" Enter
Type "rm -rf famly-demo famly-archive" Enter
Type "clear" Enter
Show

# --- the demo ---
Type "# famly-cli: archive your child's Famly data (this demo is fake)"
Sleep 700ms
Enter
Sleep 1200ms

Type "famly whoami"
Enter
Sleep 2500ms

Type "famly children"
Enter
Sleep 3500ms

Type "# download every full-resolution photo and build a gallery"
Enter
Type "famly photos --incremental --gallery --out famly-demo"
Enter
Sleep 4s

Type "# or archive everything as JSON: feed, messages, notes, events"
Enter
Type "famly export --out famly-archive"
Enter
Sleep 4s

# --- hidden teardown ---
Hide
Type "rm -rf famly-demo famly-archive" Enter
Show
