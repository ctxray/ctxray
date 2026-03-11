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

# --- Setup: set env var fast, then clear ---
Set TypingSpeed 0ms
Type "export REPROMPT_DB_PATH=/tmp/reprompt-demo.db"
Enter
Set TypingSpeed 55ms

# --- Scene 1: Scan sessions ---
Type "reprompt scan --path /tmp/reprompt-demo"
Enter
Sleep 7s

# --- Scene 2: Rich report ---
Type "reprompt report"
Enter
Sleep 8s

# --- Scene 3: Prompt library ---
Type "reprompt library"
Enter
Sleep 5s

# --- Scene 4: Search ---
Type 'reprompt search "unit test"'
Enter
Sleep 5s

# --- Scene 5: Trends ---
Type "reprompt trends"
Enter
Sleep 6s

# Hold final frame
Sleep 3s
