# VHS recording script for reprompt v1.6 demo GIF
#
# Prerequisites:
#   brew install vhs     (or go install github.com/charmbracelet/vhs@latest)
#   pip install reprompt-cli
#
# Recording:
#   reprompt demo        (generates sample data)
#   vhs docs/launch/demo.tape
#
# Output: docs/launch/demo.gif

Output docs/launch/demo.gif

Set FontSize 15
Set Width 1100
Set Height 750
Set Theme "Catppuccin Mocha"
Set Padding 20
Set TypingSpeed 50ms
Set Shell "zsh"

# --- Scene 1: Dashboard (the first thing users see) ---
Type "reprompt"
Enter
Sleep 5s

# --- Scene 2: Score a prompt ---
Type 'reprompt score "Fix the auth bug in src/login.ts where JWT expires"'
Enter
Sleep 4s

# --- Scene 3: Agent analysis (v1.6 flagship) ---
Type "reprompt agent --last 3"
Enter
Sleep 5s

# --- Scene 4: Privacy deep scan (v1.6 flagship) ---
Type "reprompt privacy --deep"
Enter
Sleep 5s

# --- Scene 5: Distill a conversation ---
Type "reprompt distill --last 1 --summary"
Enter
Sleep 5s

# --- Scene 6: Compress a prompt ---
Type 'reprompt compress "请帮我看一下这个代码，就是那个 login 的那个文件，好像有点问题"'
Enter
Sleep 4s

# Hold final frame
Sleep 3s
