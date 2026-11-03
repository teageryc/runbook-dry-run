"""Copy the dated publish procedure and declare its shell, leaving the original untouched."""

import sys

source, target = sys.argv[1], sys.argv[2]
with open(source, encoding="utf-8") as handle:
    lines = handle.read().splitlines(keepends=True)

out = []
inserted = 0
for line in lines:
    out.append(line)
    if line.startswith("Working directory:"):
        out.append("Shell: `Git Bash`\n")
        inserted += 1

assert inserted == 1, f"expected exactly one Working directory line, found {inserted}"
assert not any(l.startswith("Shell:") for l in lines), "the original already declares a shell"

with open(target, "w", encoding="utf-8", newline="") as handle:
    handle.writelines(out)
print(f"inserted {inserted} Shell: line into {target}")
