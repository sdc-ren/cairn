# Kịch bản chuẩn — chấm chất lượng handoff (R24)

Mục đích: đo xem `/cairn:handoff` có giữ được đủ lý luận của một phiên hay không, bằng một phiên mẫu cố định và rubric 8 ý ([rubric.json](rubric.json)).

## Chuẩn bị

```bash
scripts/eval_setup.sh /tmp/cairn-eval     # repo mẫu "shop" với cart.py
cd /tmp/cairn-eval && claude              # phiên Claude Code có plugin cairn
```

## Lời thoại đưa cho agent (gửi nguyên văn, từng tin một)

1. "We need a bulk discount: carts with more than 5 items get 10% off. Put the logic in `total()` in cart.py, not in the API layer, because the mobile app also calls `total()`."
2. "Use Decimal with ROUND_HALF_UP for money."
3. "Earlier we tried rounding in the API layer and it double-rounded prices, so that approach is abandoned."
4. "Next: add the discount branch in `total()`, then add tests in test_cart.py, then run pytest. I still have not decided whether the discount applies before or after tax."
5. `/cairn:handoff`

## Chấm

```bash
python3 scripts/eval_check.py "$(cairn show --dir /tmp/cairn-eval --path)"
```

Đạt khi ≥ 7/8. Ghi điểm từng lần vào [verification.md](../verification.md) mục F3; ngưỡng MVP là 3 lần liên tiếp đạt (R24.4).
