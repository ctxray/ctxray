# VHS tape file — run: vhs docs/demo.tape
# Docs: https://github.com/charmbracelet/vhs

Output docs/demo.gif
Set Shell "bash"
Set FontSize 14
Set Width 1000
Set Height 650
Set Padding 20
Set Theme "Dracula"
Set TypingSpeed 40ms

# activate venv so ctxray is on PATH (hidden from viewer)
Hide
Type "export PATH=/Users/chris/projects/ctxray/.venv/bin:$PATH"
Enter
Sleep 500ms
Type "cd /Users/chris/projects/ctxray"
Enter
Sleep 500ms
Type "clear"
Enter
Sleep 500ms
Show

# --- Scene 1: check a good prompt ---
Type "ctxray check 'Fix the JWT expiration bug in src/auth/middleware.ts. Error: TypeError: Cannot read exp of undefined at verifyToken:42. Do not modify refresh token tests.'"
Sleep 300ms
Enter
Sleep 3s

# --- Scene 2: rewrite a bad prompt ---
Type "ctxray rewrite 'I was wondering if you could maybe help me fix the auth bug'"
Sleep 300ms
Enter
Sleep 3s

# --- Scene 3: build from components ---
Type "ctxray build 'fix the JWT expiration bug' --file src/auth/middleware.ts --error 'TypeError: Cannot read exp' --constraint 'keep backward compat'"
Sleep 300ms
Enter
Sleep 3s

Sleep 2s
