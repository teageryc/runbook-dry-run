"""Release gate for v0.4 (Yan's pick on the third review): random runbooks built from
the edges the reviews found, each compared with CommonMark by oracle.py.

    python -I -X utf8 docs/plans/evidence/2026-11-10-v0.4/fuzz/fuzz_gate.py <documents per pool and seed> <seed> [<seed> ...]

Exit 0 only if no document executes a line CommonMark shows as code without the
checker refusing it. Each dangerous document is shrunk to a minimal one and printed.
Also prints how many documents were refused: refusing is safe, but it is the cost.

Adapted on 2026-11-10 from the third code review's fuzz.py; development only.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oracle import analyse, oracle_deviates  # noqa: E402

HEAD = "# Runbook: x\n\nWorking directory: `.`\n\n## Step 1 - a\nOn failure: stop.\n\n"
POOLS = {
    "lists": ["```", "~~~", "````", "- ```", "1. ```", "10. ```", "-  ```", "* ~~~",
              "  ```", "   ```", "    ```", "  code", "   code", "    code", "code",
              "- item", "1. item", "2. item", "", "", "", "Para text", "## Step 2 - b",
              "-    ```", "1.    ```"],
    "html": ["```", "~~~", "- ```", "1. ```", "  ```", "   ```", "  code", "code",
             "- item", "1. item", "", "", "", "Para", "<!--", "-->", "<!-- x -->",
             "  <!--", "   <!--", "  -->", "<pre>", "</pre>", "  <pre>", "- <!--",
             "<?php", "?>", "<!X", ">", "  <!X", "<![CDATA[", "]]>"],
    "tabs": ["```", "- ```", "1. ```", "  ```", "\t```", " \t```", "-\t```", "1.\t```",
             "\tcode", "  code", "", "", "Para", "- item", "　", "\xa0", "  \t```",
             "\t- ```", "~~~", " ```"],
}


def make(rng, pool, size):
    lines, label = [], 0
    for _ in range(size):
        if rng.random() < 0.22:
            label += 1
            lines.append(f"Run: `echo L{label}`")
        else:
            lines.append(rng.choice(pool))
    return lines


def dangerous(lines):
    text = HEAD + "\n".join(lines) + "\n"
    if oracle_deviates(text):
        return False
    danger, refused = analyse(text)
    return bool(danger) and not refused


def shrink(lines):
    changed = True
    while changed:
        changed = False
        for i in range(len(lines)):
            trial = lines[:i] + lines[i + 1:]
            if dangerous(trial):
                lines, changed = trial, True
                break
    return lines


def main():
    count, seeds = int(sys.argv[1]), [int(s) for s in sys.argv[2:]] or [1]
    found, total, refused_count, deviates = {}, 0, 0, 0
    for name, pool in POOLS.items():
        for seed in seeds:
            rng = random.Random(f"{name}-{seed}")
            for _ in range(count):
                lines = make(rng, pool, rng.randint(4, 14))
                total += 1
                text = HEAD + "\n".join(lines) + "\n"
                if oracle_deviates(text):
                    deviates += 1
                    continue
                danger, refused = analyse(text)
                refused_count += refused
                if danger and not refused:
                    key = (name, tuple(shrink(lines)))
                    found[key] = found.get(key, 0) + 1
    print(f"documents: {total} ({len(POOLS)} pools x {len(seeds)} seeds x {count}); "
          f"skipped, oracle not the spec: {deviates}; refused: {refused_count}; "
          f"dangerous and not refused, distinct minimal: {len(found)}")
    for (name, key), hits in sorted(found.items(), key=lambda kv: (len(kv[0][1]), -kv[1]))[:25]:
        print(f"  [{name}] x{hits}: {chr(10).join(key)!r}")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
