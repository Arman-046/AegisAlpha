import sys

with open('dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
in_body = False

for i, line in enumerate(lines):
    # Remove the global obs initialization
    if line.strip() == 'obs = load_observability()':
        continue
        
    if '# 1. WHAT IS AEGISALPHA DOING RIGHT NOW?' in line:
        in_body = True
        new_lines.append('@st.fragment(run_every="2s")\n')
        new_lines.append('def render_dashboard_body():\n')
        new_lines.append('    obs = load_observability()\n\n')
        
    if in_body:
        # Indent by 4 spaces, but handle empty lines properly
        if line.strip() == '':
            new_lines.append('\n')
        else:
            new_lines.append('    ' + line)
    else:
        new_lines.append(line)

new_lines.append('\nrender_dashboard_body()\n')

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Refactored successfully")
