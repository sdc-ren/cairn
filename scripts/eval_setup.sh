#!/bin/sh
# Create the sample "shop" repository used by docs/specs/eval/scenario.md (R24.1).
set -eu
target=${1:?usage: eval_setup.sh DIR}
mkdir -p "$target"
cd "$target"
git init -q -b main
cat > cart.py <<'PY'
def total(items):
    return sum(item.price for item in items)
PY
git add cart.py
git -c user.name=eval -c user.email=eval@example.invalid commit -q -m "add cart total"
echo "sample repo ready in $target"
