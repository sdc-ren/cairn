# Tasks — cairn v1 (Agent Handoff)

| Thuộc tính | Giá trị |
|---|---|
| Requirements | [requirements.md](requirements.md) |
| Design | [design.md](design.md) |
| Chuẩn mã | [CODING_STANDARDS](../CODING_STANDARDS.md) |

## Cách dùng

- Làm **Milestone 0 trước**, dùng thử, sửa spec, rồi mới sang Milestone 1 (design D17).
- Làm theo thứ tự phụ thuộc (cuối file). Mỗi task có **Done khi** kiểm được; chưa đạt thì chưa sang task khác.
- TDD: viết test trước, gắn `@pytest.mark.req("Rn.m")` cho mọi tiêu chí trong `Refs`.
- Mỗi task = một PR (CS-51), tiêu đề chứa ID task, ví dụ `feat(store): B4 atomic store`.
- Mọi task M1 đều ngầm có điều kiện: `make lint test` xanh theo CODING_STANDARDS §9. Task M0 chỉ cần `ruff` + `pytest` xanh.
- Đánh dấu `- [x]` khi merge, ghi số PR cạnh task.

---

## Milestone 0 — bộ khung 0.0.1 (chạy được S1, dùng thử sớm)

Phạm vi: bảng "Phạm vi M0" ở requirements §6. Mục tiêu 1–2 ngày. Mã viết đúng layout design §3 và CS-2 ngay từ đầu để M1 chỉ mở rộng.

- [x] **K1. Khung repo tối thiểu**
  - Layout design §3, chỉ tạo module cần cho M0. `pyproject.toml` (`requires-python = ">=3.9"`, cấu hình `ruff` + `pytest`), `Makefile` (`test`, `lint`), `__version__ = "0.0.1"`.
  - `errors`, `constants`, `out`, `proc` bản tối giản; `cli.py` dispatch `save`, `hook session-start`, `version`.
  - **Done khi:** `python -m agent_cairn version` chạy; `make lint test` xanh; lệnh cần repo chạy ngoài repo → mã 5.
  - Refs: R1.7, R18.1, R18.4, R18.5

- [x] **K2. Lõi tối giản: `document`, `validate`, `secrets`, `store`**
  - `validate` chỉ các luật **lỗi** của R5.3; `store`: `root`, `ensure`, `new_id`, `write_new`, `newest`, `mark_resumed`.
  - **Done khi:** file do `render` ghi được `parse` lại; mỗi luật lỗi có một case vi phạm + một case qua, đúng định dạng R5.4; secret bị chặn, stderr không chứa giá trị; permission `0700`/`0600`; trùng ID có hậu tố; gọi từ worktree phụ vẫn trỏ Store của repo chính.
  - Refs: R1.1, R1.3–R1.6, R2.1, R2.2, R2.4, R2.7, R5.3, R5.4, R12.1, R12.2

- [x] **K3. Capture rút gọn + `save`**
  - `gitio` đủ cho: branch, head, `status -z`, 5 commit gần nhất; `capture` chỉ worktree hiện tại, không `gh`; `render.captured()` tối giản; `store.cleanup(replace_branch=…)` chỉ phần thay bản cũ.
  - **Done khi:** trên git repo tạm thật: `save` qua stdin in đúng `saved <id>`, file có Captured state, `status: open`; vi phạm → mã 3 và Store không có file mới; capture không ghi Store; lưu lần hai trên cùng branch → còn đúng một file, stderr có `removed <id> (replaced)`; branch khác không bị đụng.
  - Refs: R4.2, R4.9, R5.1, R5.6, R5.9, R12.4, R12.5, R14.1, R14.5

- [x] **K4. Drift rút gọn + resume brief + `hook session-start`**
  - `drift.classify` cho state same/ahead/diverged/missing; `render.resume(brief=True)` + `assets/preamble.md`; hook theo design §5.5 (chưa cần cắt 9 000 ký tự).
  - **Done khi:** repo thật: không đổi → đúng một dòng `no drift…`; +3 commit; reset rồi commit (diverged); head mất. Hook: có handoff open đúng branch → JSON hợp lệ chứa preamble, status → `resumed`; không có / quá hạn / branch khác → stdout rỗng; Store hỏng → mã 0; `CAIRN_HOOK=off`; không gọi `gh`.
  - Refs: R9.1–R9.3, R9.5, R10.1–R10.4, R10.8, R13.1, R13.3, R13.4, R13.6–R13.8

- [x] **K5. Plugin khung + kiểm trên Claude Code thật** — luồng lưu → hook → tóm tắt đã kiểm thật; bước 2, 3, 6 của checklist kiểm dần trong K6
  - `plugin.json`, `marketplace.json`, `bin/cairn` (design §7.1–7.2), `hooks/hooks.json` chỉ entry `startup|clear`, `skills/handoff/SKILL.md` và `skills/resume/SKILL.md` **viết tay** bằng tiếng Anh, nhúng template. Ở M0 `SKILL.md` là nguồn duy nhất của template; P2 chuyển về Asset và sinh lại.
  - Kiểm trên bản Claude Code đang cài và ghi vào `verification.md`: `bin/` có trong PATH của Bash tool; cú pháp `allowed-tools`; `$ARGUMENTS`; hook dạng exec `command` + `args` được gọi. Sai chỗ nào thì sửa design §7 ngay.
  - **Done khi:** cài local bằng hai lệnh `claude plugin …`; `/cairn:handoff` lưu trong một lượt, trả lời ≤ 2 dòng; mở phiên mới thì hook chèn handoff và agent tóm tắt; không gõ lệnh terminal nào sau khi cài.
  - Refs: R2.8, R3.1, R3.2, R11.1–R11.6, R11.9, R13.2, R16.1–R16.3, R16.6, R16.7, R22.1, R22.3

- [x] **K7. Store chung ngoài repo + `cairn show`**
  - Store chuyển từ `<git-common-dir>/cairn/` sang `~/.cairn/projects/<dự-án>-<hash8>/` kèm `project.json` (design D3); `save --session`; skill handoff truyền `${CLAUDE_SESSION_ID}`.
  - `cairn show [--path]` in handoff mới nhất của branch (rơi về mới nhất của Dự án kèm cảnh báo); skill resume dùng lệnh này thay cho tự dò file.
  - **Done khi:** mọi worktree của một repo cùng một Store; hai repo trùng tên khác Store; quyền `0700` từ Cairn home trở xuống; `project.json` đúng; `show` in nguyên văn, `--path` in đường dẫn, không đổi status.
  - Refs: R1.1–R1.3, R1.8, R2.3, R5.5, R7.2, R8.1–R8.3

- [x] **K8. Workspace nhiều repo, khoá task, Workspace section**
  - Store phẳng `~/.cairn/<dự-án>-<hash8>/<id>.md` (`.project.json`, `.lock` ẩn); Dự án ngoài git là chính thư mục (R1.9); `--dir` cho mọi lệnh Store.
  - `save --task`: ID và Khoá handoff theo task; hook chọn theo Dự án (ưu tiên cùng branch), liệt kê handoff mở khác; lệnh `resume [ref]`, `show [ref]`.
  - Section `## Workspace`: chụp `worktree`/`pipeline` lúc save, drift từng mục lúc resume (design D19, D20).
  - **Done khi:** test xanh; demo trên một workspace thật chứa nhiều repo (không phải git): lưu PROJ-268, hook chèn đúng với 6 worktree và 4 pipeline.
  - Refs: R1.4, R1.7, R1.9, R1.10, R2.5, R4.10, R7.1, R7.5, R9.1–R9.5, R10.10, R13.3, R13.9, R14.1

- [x] **K9. `cairn list` + resume chọn từ danh sách**
  - `cairn list [--status] [--limit N|--all] [--dir]`: bảng ID, task, status, tuổi, title; skill resume không kèm task thì liệt kê và hỏi chọn (design D21).
  - **Done khi:** test bảng, lọc, giới hạn, Store rỗng xanh; skill qua `claude plugin validate --strict`.
  - Refs: R6.1, R6.2, R6.3, R6.5, R6.6, R16.8

- [ ] **K6. Dùng thử M0 và chỉnh spec**
  - Tạo `verification.md` với bảng nhật ký R24.3; dùng thật ≥ 3 ngày, ≥ 5 dòng nhật ký.
  - Liệt kê điều cần đổi (template, luật validate, preamble, hook phiền…); sửa requirements/design/tasks, tăng phiên bản spec.
  - **Done khi:** DoD M0 (requirements §9) đạt; spec đã cập nhật được duyệt.
  - Refs: R24.3

---

## Milestone 1 — MVP 0.1 (plugin tự chứa, tự dùng)

Các task dưới đây **mở rộng** module đã có từ M0, không viết lại. Phần nào đã làm ở K1–K5 thì task tương ứng chỉ bổ sung phần còn thiếu; Done khi giữ nguyên.

### A. Nền móng

- [ ] **A1. Hoàn thiện repo** (mở rộng K1)
  - Đủ layout design §3. `pyproject.toml`: `requires-python = ">=3.9"`, extras `dev = [pytest, pytest-cov, ruff, mypy, pylint, vulture]`, cấu hình công cụ đúng CODING_STANDARDS §9. `__version__ = "0.1.0.dev0"`. `LICENSE` MIT, `README.md` (EN) khung, `CHANGELOG.md`, `CONTRIBUTING.md` trỏ tới CODING_STANDARDS.
  - `Makefile`: `test`, `lint`, `fmt`, `cov`, `reqcov`, `gen`.
  - `scripts/check_sizes.py` (CS-13).
  - **Done khi:** `pip install -e '.[dev]'` ok; `python -m agent_cairn` in usage tạm; `make lint test` xanh với một test smoke.
  - Refs: R18.5, R18.7, R20.1

- [ ] **A2. CI**
  - `.github/workflows/ci.yml`: `macos-latest`, `ubuntu-latest` × Python `3.9`, `3.13`; chạy `make lint`, `pytest --cov=agent_cairn --cov-branch --cov-fail-under=85`, `python scripts/req_coverage.py --level M1 --allow-missing` (bỏ cờ ở F1), `python scripts/gen_plugin.py --check` (từ P2).
  - **Done khi:** CI xanh trên PR đầu tiên.
  - Refs: R18.2, R20.4, R20.5

- [ ] **A3. Module nền: `errors`, `constants`, `out`, `proc`, `timeutil`**
  - Theo design §9 và bảng CS-2. `proc.run(args, *, cwd, timeout, stdin=None) -> Result`; thiếu executable hoặc timeout → `CairnError` (thông điệp có tên lệnh, không có dữ liệu người dùng). `out.emit/warn/fail` theo R17.7–R17.8. `timeutil.now_utc` inject được.
  - **Done khi:** test unit xanh; quy ước thông điệp và màu được kiểm.
  - Refs: R17.7, R17.8, R17.9, R18.4

- [ ] **A4. Fixture và test tĩnh**
  - `conftest.py`: `git_repo`, `commit()`, `add_worktree()`, `bare_remote()`, `fake_gh()`, `frozen_clock`, factory `make_handoff()`/`make_worktree_state()`, fixture autouse cô lập env (design §10).
  - `tests/test_imports.py`: chỉ stdlib; đồ thị phụ thuộc đúng design §3; chỉ `proc` import `subprocess`; chỉ `out` gọi `print`; không `shell=True`.
  - **Done khi:** test mẫu dùng mọi fixture chạy được; test tĩnh xanh.
  - Refs: R18.1, R18.4, R20.3

### B. Lõi dữ liệu (thuần)

- [ ] **B1. `document.py`**
  - `Handoff`; `parse(text, path)`; `render(h, captured_md)`; luật design §4.2; khối `captured-json`.
  - **Done khi:** round-trip byte-for-byte với golden `handoff_full.md` (= ví dụ design §4.1); title có `:`/`"`; khoá lạ giữ nguyên; thiếu khối JSON → `captured=None`; file hỏng → lỗi có tên file.
  - Refs: R2.1–R2.9

- [ ] **B2. `validate.py`**
  - `validate(body) -> list[Violation(level, line, rule, message)]`; rule-id ở `constants.py` (design §5.1).
  - **Done khi:** mỗi luật R5.3 có một case vi phạm + một case qua; định dạng `line N: rule: message` được kiểm; comment HTML + `TODO` coi là rỗng.
  - Refs: R5.3, R5.4, R2.4, R2.5

- [ ] **B3. `secrets.py`**
  - Pattern design §6.2; `scan`, `redact`.
  - **Done khi:** mỗi pattern có mẫu dương + mẫu âm gần giống; placeholder không bị bắt; `Finding` không chứa giá trị; `redact` giữ phần còn lại của dòng.
  - Refs: R12.1–R12.3

- [ ] **B4. `store.py`**
  - `root(cwd)`, `ensure()`, `new_id()` + slug + hậu tố trùng, `write_new()` (O_EXCL, 0600, atomic), `iter_meta()` chỉ đọc frontmatter, `read()`, `mark_resumed()`, `lock()` (`fcntl.flock`).
  - Thêm `cleanup` đầy đủ (design §5.2): hết hạn `resumed`/`open`, hàm thuần `expired()`.
  - **Done khi:** permission thực tế đúng; trùng ID không ghi đè; file hỏng bị bỏ qua có cảnh báo và không bị xoá; `mark_resumed` giữ Body/Captured byte-for-byte; gọi từ worktree phụ vẫn trỏ về Store của main repo; `expired()` có test bảng cho biên 7d/30d và biến môi trường; detached không bị thay thế.
  - Refs: R1.1–R1.6, R6.6, R9.3, R14.2, R14.3, R14.8

- [ ] **B5. `resolve.py`**
  - **Done khi:** đủ 5 tiêu chí R7 có test.
  - Refs: R7.1–R7.5

### C. Git và capture

- [ ] **C1. `gitio.py`**
  - Hàm theo bảng design §8; kiểm git ≥ 2.31.
  - **Done khi:** test repo thật: tên file có dấu cách/Unicode, rename, untracked, detached, có/không upstream.
  - Refs: R4.2, R18.3

- [ ] **C2. `gh.py`**
  - **Done khi:** `fake_gh` cho đủ 5 kịch bản (ok, exit 1, timeout, JSON hỏng, không có gh).
  - Refs: R4.4, R4.5

- [ ] **C3. `capture.py`**
  - `collect(cwd, *, use_gh, git_timeout)`; `to_json()` theo design §4.3.
  - **Done khi:** repo 3 worktree (một detached, một có PR giả, một prunable) cho kết quả đúng; cắt 50 file + `changes_total`; lỗi từng worktree vào `errors`.
  - Refs: R4.1–R4.8

- [ ] **C4. `render.captured()`**
  - **Done khi:** golden `captured_basic.md`, `captured_no_gh.md`, `captured_errors.md` xanh; worktree có thay đổi chứa chuỗi giống secret không làm lộ nội dung file.
  - Refs: R2.7, R5.7, R12.4, R12.5

### D. Lệnh

- [ ] **D1. `cli.py` khung**
  - argparse theo R17.1 (lệnh M1); usage/help/version; ánh xạ lỗi; `KeyboardInterrupt`, `BrokenPipeError`, `CAIRN_DEBUG`.
  - **Done khi:** test mã thoát: không đối số (0), `-h` (0), lệnh lạ (2), lỗi giả lập (1, một dòng, không traceback), lệnh cần repo ngoài repo (5), `version`/`template` chạy ngoài repo.
  - Refs: R17.1–R17.6, R1.7

- [ ] **D2. `template` + `assets/template.md`**
  - **Done khi:** template nguyên trạng bị `validate` từ chối; bản điền mẫu qua; chạy ngoài repo.
  - Refs: R3.1–R3.3, R22.1

- [ ] **D3. `capture`**
  - **Done khi:** in dạng đọc và `--json`; `--no-gh`; Store không được tạo sau lệnh.
  - Refs: R4.6, R4.7, R4.9

- [ ] **D4. `save`**
  - Theo design §5.1.
  - **Done khi:** TTY không input → 2; thiếu section → 3, liệt kê đủ vi phạm đúng định dạng; secret → 3, stderr không có giá trị; `--redact` lưu được; `--dry-run` không tạo file và không xoá gì; lưu xong thì bản cũ cùng branch bị xoá, bản hết hạn bị dọn; thành công → in đúng `saved <id>`, file parse lại được, `status: open`.
  - Refs: R5.1–R5.9, R12.2, R12.3, R14.1, R14.4–R14.6

- [ ] **D5. `list`**
  - **Done khi:** test 25 handoff (2 branch, 2 status) cho mọi cờ; Store rỗng.
  - Refs: R6.1–R6.6

- [ ] **D6. `show`**
  - **Done khi:** in nguyên văn; `--path`; nội dung/mtime không đổi.
  - Refs: R8.1–R8.3

- [ ] **D7. `doctor`**
  - **Done khi:** test môi trường thiếu gh, ngoài repo, version plugin lệch; mã thoát đúng.
  - Refs: R15.1, R15.2

### E. Resume, drift, hook

- [ ] **E1. `drift.py`**
  - `classify(facts)` thuần + `compute(h, *, git_timeout)` lấy facts từ `gitio`.
  - **Done khi:** `classify` có test bảng cho mọi state/level; `compute` trên repo thật: không đổi; +3 commit; +12 commit (cắt 10, total 12); reset rồi commit (diverged); head mất sau `gc --prune=now`; đổi branch; worktree bị xoá; tập file still/newly/clean.
  - Refs: R10.1–R10.9

- [ ] **E2. `render.resume()` + `assets/preamble.md`**
  - **Done khi:** golden `resume_full.txt`, `resume_brief.txt`, `resume_already.txt`; JSON đúng design §4.4.
  - Refs: R9.1, R9.2, R9.6, R9.7, R9.8, R22.1

- [ ] **E3. Lệnh `resume`**
  - **Done khi:** đổi `status`/`resumed_at`/`resume_count`; `--peek` không đổi và không xoá gì; handoff đang resume không bị xoá kể cả khi đã quá hạn; bản khác hết hạn bị dọn; resume lần 2 có cảnh báo; stdout chỉ có output.
  - Refs: R9.3–R9.5, R9.8, R14.4, R14.7

- [ ] **E4. `hook session-start`**
  - Theo design §5.5.
  - **Done khi:** không handoff → stdout rỗng; handoff open đúng branch → JSON hợp lệ, `additionalContext` chứa preamble, status đổi; handoff cũ hơn max-age hoặc branch khác → rỗng; Store hỏng/ngoài repo → mã 0, stdout rỗng; cắt 9 000 ký tự; không gọi `gh` (fake_gh ghi log, assert không được gọi); < 2 giây với 10 worktree; `CAIRN_HOOK=off`.
  - Hook cũng dọn bản hết hạn (R14.4); dòng `removed …` chỉ ra stderr, stdout vẫn đúng JSON.
  - Refs: R13.1, R13.3–R13.8, R14.4, R14.5

- [ ] **E5. `hook pre-compact` + `hook post-compact`**
  - Theo design §5.6; Asset `precompact.md`, `nudge.md`; thêm hai entry vào `hooks.json` (design §7.3).
  - Kiểm trên Claude Code thật: chạy `/compact` trong phiên có plugin; xác nhận bản tóm tắt giữ các mục ở R23.2 và agent nhắc đúng một dòng; ghi vào `verification.md`. Không chạy được → áp dụng R23.8.
  - **Done khi:** test design §10 (hàng "Hook nén ngữ cảnh") xanh; bằng chứng thật đã ghi.
  - Refs: R23.1–R23.8

### P. Plugin

- [ ] **P1. Manifest, marketplace, launcher** (hoàn thiện K5)
  - `.claude-plugin/plugin.json`, `marketplace.json`, `bin/cairn` theo design §7.1–7.2 (chmod 755).
  - **Done khi:** test chạy `bin/cairn version` qua subprocess; `CAIRN_PYTHON` trỏ tới binary giả báo 3.8 → thông điệp R11.4, mã 1; `PYTHONPATH` rác của người dùng không ảnh hưởng.
  - Refs: R11.1, R11.3, R11.4, R18.7

- [ ] **P2. Asset skill + `gen_plugin.py`**
  - Chuyển nội dung `SKILL.md` viết tay ở K5 về Asset; từ đây `skills/` là file sinh.
  - `assets/skills.json`, `skill_handoff.md`, `skill_resume.md` theo design §7.4; `scripts/gen_plugin.py` sinh `skills/*/SKILL.md`, đồng bộ `plugin.json.version`; `--check` báo lệch và mã 1.
  - **Done khi:** `--check` sạch; test plugin (design §10) xanh; description ≤ 1 000 ký tự, chứa cụm kích hoạt EN + VI.
  - Refs: R11.5, R11.7, R11.8, R16.1–R16.5, R22.2, R22.3

- [ ] **P3. `hooks/hooks.json`**
  - Theo design §7.3, dùng kết quả kiểm dạng exec ở K5 (nếu dạng exec không chạy thì dùng dạng chuỗi `"\"${CLAUDE_PLUGIN_ROOT}/bin/cairn\" hook session-start"`).
  - **Done khi:** test cấu trúc JSON xanh cho mọi entry, kể cả entry của E5.
  - Refs: R11.6, R11.9, R13.2

- [ ] **P4. Cài local và chạy thử end-to-end**
  - `claude plugin marketplace add ./cairn` → `claude plugin install cairn@cairn` trên máy thật.
  - Chạy S1 (hai tài khoản), S2 (commit tay sau handoff), S3 (hai worktree); kiểm R16.7: không gõ lệnh terminal nào sau khi cài.
  - **Done khi:** bằng chứng (lệnh, output rút gọn, ảnh nếu cần) ghi trong `docs/specs/verification.md`; mọi lỗi phát hiện được sửa trong task tương ứng.
  - Refs: R11.2, R16.6, R16.7, R19.1, R19.2

### F. Hoàn tất MVP

- [ ] **F1. Truy vết requirement**
  - `scripts/req_coverage.py`: lấy mọi `Rn.m` mức M1 từ `requirements.md` (mức requirement ở tiêu đề, ghi đè bởi `[M2]` cuối dòng tiêu chí), quét marker `req` trong `tests/`; tiêu chí `[manual]` thì tìm ID trong tiêu đề của `verification.md`; in tiêu chí thiếu, mã 1 nếu thiếu. Bỏ `--allow-missing` khỏi CI.
  - **Done khi:** CI xanh không cờ.
  - Refs: R20.2

- [ ] **F3. Kịch bản chuẩn và chấm điểm**
  - `docs/specs/eval/scenario.md`, `eval/rubric.json`, `scripts/eval_setup.sh`, `scripts/eval_check.py` theo design §5.7.
  - Chạy kịch bản 3 lần liên tiếp bằng `/cairn:handoff` rồi chấm; ghi điểm từng lần vào `verification.md`.
  - **Done khi:** test `eval_check.py` (đạt/không đạt, bỏ qua comment template) xanh; 3 lần liên tiếp ≥ 7/8.
  - Refs: R24.1, R24.2, R24.4

- [ ] **F2. Dùng thật và phát hành 0.1.0**
  - README (EN) Quickstart ≤ 5 dòng lệnh; tự dùng ≥ 5 ngày làm việc, ghi nhật ký vấn đề vào `verification.md`; tag `v0.1.0`, CHANGELOG.
  - **Done khi:** Definition of Done M1 (requirements §9) đạt, gồm ngưỡng nhật ký R24.4.
  - Refs: R22.4, R24.3, R24.4, requirements §9

---

## Milestone 2 — 0.2 (phát hành rộng, agent khác)

- [ ] **G1. Đóng gói PyPI** — `[project.scripts] cairn = "agent_cairn.cli:main"`, publish `agent-cairn`, test `pipx install` và `uv tool install` trong CI. Refs: R18.6, R21.6
- [ ] **G2. `cairn init`** — cài skill (sinh từ cùng Asset) vào `.claude/skills/` hoặc `~/.claude/skills/`; marker, `--force` + `.bak`, `--dry-run`. Refs: R21.1, R21.5
- [ ] **G3. `init --agent agents-md`** — khối có marker trong `AGENTS.md`. Refs: R21.2
- [ ] **G4. `cairn prompt handoff|resume`.** Refs: R21.3, R21.5
- [ ] **G5. `init --uninstall`.** Refs: R21.4
- [ ] **G6. `rm`.** Refs: R14.9
- [ ] **G7. `resume --copy` + `clipboard.py`.** Refs: R9.9
- [ ] **G8. `doctor` mở rộng** — clipboard, cài đặt pipx. Refs: R15.1
- [ ] **G9. Phát hành 0.2.0** — kiểm S4 với một agent không phải Claude; publish marketplace công khai.

## Thứ tự phụ thuộc

```
K1 → K2 → K3 → K4 → K5 → K7 → K8 → K9 → K6   (M0, tuần tự)
K6 → A1                                (M1 chỉ bắt đầu sau khi chỉnh spec)
A1 → A2
A1 → A3 → A4
A4 → B1 → B2, B3, B4 → B5           (song song được với C)
A4 → C1 → C2 → C3 → C4
B*, C4 → D1 → D2, D3, D4, D5, D6, D7
C1, B4 → E1 → E2 → E3 → E4 → E5
D2, E4 → P1 → P2 → P3 → P4
E5, P3 → P4
P4 → F1, F3 → F2
F2 → G1 … G9
```
