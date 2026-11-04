"""Which tests assert a finding code, and do those also assert the step it lands on?"""

import ast
import re
import sys

CODE = re.compile(r"^[A-Z][A-Z_]{4,}$")
tree = ast.parse(open(sys.argv[1], encoding="utf-8").read())
total = with_code = with_code_and_step = 0
missing = []
for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
    for fn in [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]:
        total += 1
        source = ast.unparse(fn)
        codes = [
            c.value for c in ast.walk(fn)
            if isinstance(c, ast.Constant) and isinstance(c.value, str) and CODE.match(c.value)
        ]
        # A test that never handles findings (one reading the FINDING_CODES table,
        # say) names a code without expecting a finding; it is not counted.
        if not codes or not re.search(r"\bfindings\b", source):
            continue
        with_code += 1
        if "codes_at(" in source or ".step)" in source or "].step" in source:
            with_code_and_step += 1
        else:
            missing.append(f"{cls.name}.{fn.name}")
print(f"tests={total} asserting_a_code={with_code} also_asserting_step={with_code_and_step}")
for name in missing:
    print("  code without step:", name)
sys.exit(1 if missing else 0)
