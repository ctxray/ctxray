# VHS recording script for reprompt v1.6 demo GIF
#
# Prerequisites:
#   brew install vhs
#   pip install reprompt-cli
#
# Recording:
#   REPROMPT_DB_PATH=/tmp/reprompt-demo.db reprompt demo
#   vhs docs/launch/demo.tape
#
# Output: docs/launch/demo.gif

Output docs/launch/demo.gif

Set FontSize 15
Set Width 1100
Set Height 600
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 50ms
Set Shell "zsh"

# --- Setup: point to demo DB ---
Set TypingSpeed 0ms
Type "export REPROMPT_DB_PATH=/tmp/reprompt-demo.db"
Enter
Sleep 500ms
Type "clear"
Enter
Sleep 500ms
Set TypingSpeed 50ms

# --- Scene 1: Dashboard ---
Type "reprompt"
Enter
Sleep 4s

# --- Scene 2: Score a prompt ---
Type 'reprompt score "Fix the auth bug in login.ts where JWT token expires"'
Enter
Sleep 3s

# --- Scene 3: Compress a prompt ---
Type 'reprompt compress "请帮我看一下这个代码，就是那个 login 的那个文件，好像有点问题"'
Enter
Sleep 3s

# --- Scene 4: Privacy check ---
Type "reprompt privacy"
Enter
Sleep 3s

# --- Scene 5: Lint with score threshold ---
Type "reprompt lint --score-threshold 40"
Enter
Sleep 3s

# Hold final frame
Sleep 2s
