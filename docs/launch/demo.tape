# VHS recording script for reprompt demo GIF
#
# Before recording:
#   uv run python scripts/generate_demo_data.py --output /tmp/reprompt-demo
#   rm -f /tmp/reprompt-demo.db
#   vhs docs/launch/demo.tape
#
# Output: docs/launch/demo.gif

Output docs/launch/demo.gif

Set FontSize 16
Set Width 1000
Set Height 700
Set Theme "Catppuccin Mocha"
Set Padding 24
Set TypingSpeed 55ms
Set Shell "zsh"

# --- Setup: silently set env var (not shown, just runs) ---
Sleep 300ms
Hide
Type "export REPROMPT_DB_PATH=/tmp/reprompt-demo.db"
Enter
Sleep 500ms
Show

# --- Scene 1: Scan sessions ---
Sleep 300ms
Type "reprompt scan --path /tmp/reprompt-demo"
Enter
Sleep 9s

# --- Scene 2: Rich report ---
Type "reprompt report"
Enter
Sleep 10s

# --- Scene 3: Prompt library ---
Type "reprompt library"
Enter
Sleep 7s

# --- Scene 4: Search ---
Type 'reprompt search "unit test"'
Enter
Sleep 6s

# --- Scene 5: Trends ---
Type "reprompt trends"
Enter
Sleep 8s

# Hold final frame
Sleep 4s
