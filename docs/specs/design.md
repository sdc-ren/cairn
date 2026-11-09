# Design — cairn v1 (Agent Handoff)

| Thuộc tính | Giá trị |
|---|---|
| Requirements | [requirements.md](requirements.md) |
| Tasks | [tasks.md](tasks.md) |
| Chuẩn mã | [CODING_STANDARDS](../CODING_STANDARDS.md) |

Các chi tiết định dạng Claude Code (skill, plugin, marketplace, hook) đã đối chiếu với tài liệu chính thức tại code.claude.com ngày 2026-11-09: `docs/en/skills`, `docs/en/plugins/*`, `docs/en/hooks`.

## 1. Tổng quan

```
 Phiên cũ                                         Phiên mới (tài khoản/agent khác)
 ────────                                         ─────────────────────────────────
 Dev: /cairn:handoff                              Claude Code khởi động (startup|clear)
   │                                                │
   └─ skill handoff (template nằm sẵn trong skill)  └─ hook SessionStart (plugin)
        ├─ agent soạn Body từ hội thoại                  └─ cairn hook session-start
        └─ cairn save <<EOF … EOF                             ├─ handoff open của branch này?
             ├─ validate (R5.3) ─ mã 3 → agent sửa, thử lại ≤ 3   ├─ tính Drift
             ├─ quét secrets (R12)                                 ├─ in additionalContext (JSON)
             ├─ capture git/gh (R4)                                └─ status → resumed
             └─ ghi ~/.cairn/<dự-án>-<hash>/<id>.md   agent đọc preamble → tóm tắt → chờ xác nhận
```

Chia việc: **agent viết lý do; CLI ghi dữ kiện, kiểm tra, báo drift, tự dọn bản đã hết vai trò; plugin nối hai đầu mà người dùng không phải làm gì.**

## 2. Quyết định thiết kế

| # | Quyết định | Phương án đã loại | Lý do |
|---|---|---|---|
| D1 | Agent tự viết Body; CLI không gọi LLM | Parse transcript | Chỉ agent đang chạy có lý luận; transcript phụ thuộc từng agent. |
| D2 | Mỗi handoff một file markdown | SQLite | Người và agent đọc trực tiếp được, không migration, đủ nhanh ≤ 500 file. |
| D3 | Store phẳng ở `~/.cairn/<dự-án>-<hash8>/<id>.md`; Dự án là repo chính, hoặc chính thư mục khi ngoài git | `<git-common-dir>/cairn/`; thêm cấp `projects/`, `handoffs/`; thư mục con theo agent | Một chỗ xem mọi handoff, sống sót khi clone lại, chạy được ở workspace không phải git chứa nhiều repo. Không có cấp trung gian vì chưa có gì cùng cấp (CS-3); hash tránh lẫn hai thư mục trùng tên. Agent là trường trong file vì phiên mới không biết agent cũ. Đánh đổi: đổi tên/di chuyển thư mục thì handoff cũ không đi theo. |
| D4 | Resume chỉ đổi status; mỗi branch giữ một handoff, bản `resumed` hết hạn sau 7 ngày (R14) | Xoá ngay khi resume; giữ mãi + `prune` tay | Xoá ngay thì mất khi phiên mới hỏng/hết quota/mở nhầm ngay sau khi nhận. Giữ mãi thì Store phình và người dùng phải dọn. Bản mới cùng branch do agent đang có ngữ cảnh viết nên thay thế bản cũ an toàn. |
| D5 | Validate cứng 3 section | Chấp nhận mọi body | Ép agent viết đủ khi còn ngữ cảnh; vi phạm có định dạng máy đọc để agent tự sửa (R5.4). |
| D6 | Secrets mặc định chặn | Chỉ cảnh báo | File sống lâu và đi sang tài khoản/agent khác. |
| D7 | Drift là thành phần bắt buộc của resume | In lại snapshot | Agent mới biết thông tin nào đã cũ. |
| D8 | **MVP = plugin tự chứa CLI** (`bin/cairn` + `src/`) | MVP = pipx + `init` | Plugin `bin/` được Claude Code đưa vào PATH của Bash tool; hook khai báo trong plugin. Một lần cài là đủ, không chạm `settings.json` (bỏ hẳn phần gộp JSON dễ vỡ). pipx để M2 cho agent khác. |
| D9 | Không build step | Gộp thành một file khi build | Launcher chạy thẳng `src/`; mã chạy chính là mã được test. |
| D10 | Skill/template/preamble là **Asset**, file plugin được sinh và kiểm `--check` | Viết tay trong `skills/` | Một nguồn sự thật (CODING_STANDARDS CS-2); `cairn prompt`, `init` (M2) dùng lại đúng Asset đó. |
| D11 | Hook trả JSON `additionalContext`, không gọi mạng, luôn exit 0 | stdout thô; gọi gh | JSON là dạng chuẩn; hook chạy mỗi lần mở phiên, không được làm chậm/hỏng phiên. |
| D12 | Chèn handoff chỉ ở `startup\|clear` | Mọi nguồn | Phiên `resume`/`compact` vẫn còn ngữ cảnh; chèn lại gây trùng. Nguồn `compact` chỉ nhận lời nhắc ngắn (D16). |
| D13 | Template nhúng sẵn trong skill | Agent gọi `cairn template` trước | Bớt một lượt gọi tool — R16.1 "một lượt". |
| D14 | Văn bản cho agent bằng tiếng Anh; description skill có cụm kích hoạt tiếng Việt | Toàn tiếng Việt | Agent bất kỳ đọc tốt nhất bằng tiếng Anh; người dùng nói tiếng Việt vẫn kích hoạt được skill. |
| D15 | Tên lệnh `cairn`, package `agent-cairn`, import `agent_cairn` | — | Ngắn, gợi hình ảnh để lại dấu cho người đến sau; `cairn` trên PyPI đã có người dùng nên package là `agent-cairn`. |
| D16 | Nhắc qua `PreCompact` (chỉ dẫn tóm tắt) + `SessionStart` nguồn `compact` (nhắc một dòng) | Chặn compaction đến khi có handoff; tự lưu handoff | Không có hook cho quota/ngưỡng ngữ cảnh. Chặn auto-compact có thể làm kẹt phiên; tự lưu thì Body thiếu lý luận và người dùng mất quyền quyết định. |
| D17 | Làm bộ khung M0 trước, M1 mở rộng chính các module đó | Làm tuần tự A→F | Rủi ro lớn nhất là trải nghiệm (hook, skill có chạy như mong đợi không), không phải độ đúng của từng module; kiểm sớm để sửa spec rẻ. |
| D18 | Đo chất lượng bằng rubric regex + nhật ký tay | LLM chấm điểm | Tất định, chạy offline, không tốn quota; nhật ký tay ghi được thứ máy không đo (agent có hỏi lại không). |
| D19 | Khoá handoff = Task → branch → Dự án; hook chọn theo Dự án, ưu tiên cùng branch | Khoá theo branch; khoá theo session id | Mỗi phiên có thể là một worktree/branch mới, nên khoá branch làm hook không bao giờ khớp; session id mới mỗi phiên. Task (ticket) là thứ người dùng dùng để gọi tên công việc và ổn định qua các phiên. |
| D20 | Workspace section có nhãn `worktree`/`pipeline` được cairn chụp và kiểm drift; nhãn khác giữ nguyên văn | Tự dò mọi git repo trong workspace; gắn cứng quy ước `.pipeline/` | Agent biết tài nguyên nào thuộc task; dò cả workspace thì lẫn task khác và chậm. Nhãn chung nên dự án khác dùng quy ước khác vẫn được. |
| D21 | Không thêm skill `list`; `/cairn:resume` không kèm task tự hiện bảng `cairn list --status open` để chọn | Skill `/cairn:list` riêng | Xem danh sách gần như luôn đi kèm chọn một task để làm tiếp; giữ 2 lệnh phải nhớ và không tốn thêm context mỗi phiên (~60 token cho một skill). |

## 3. Cấu trúc repo

Thư mục gốc vừa là repo Python, vừa là plugin, vừa là marketplace.

```
cairn/
├── .claude-plugin/
│   ├── plugin.json              manifest plugin (sinh version từ __version__)
│   └── marketplace.json         một plugin, "source": "./"
├── bin/
│   └── cairn                    launcher sh (§7.2)
├── skills/                      ⟵ SINH bởi scripts/gen_plugin.py, không sửa tay
│   ├── handoff/SKILL.md
│   └── resume/SKILL.md
├── hooks/
│   └── hooks.json               SessionStart, PreCompact → bin/cairn hook <event>
├── src/agent_cairn/
│   ├── __init__.py              __version__
│   ├── __main__.py              python -m agent_cairn
│   ├── cli.py                   argparse, đọc input, dispatch, ánh xạ lỗi → exit code
│   ├── commands.py              phần thân từng lệnh (save, resume, …); cli chỉ gọi vào
│   ├── errors.py                CairnError + lớp con mang exit_code
│   ├── constants.py             giới hạn, timeout, tên section, rule-id
│   ├── out.py                   emit / note / warn / detail — nơi duy nhất ghi stdout/stderr
│   ├── proc.py                  run() — nơi duy nhất gọi subprocess
│   ├── timeutil.py              now_utc (inject được), iso, age, parse_duration
│   ├── gitio.py                 mỗi lệnh git một hàm (§8)
│   ├── gh.py                    PR mở
│   ├── capture.py               WorktreeState, RepoState, collect()
│   ├── document.py              Handoff, parse/render
│   ├── validate.py              luật Body → list[Violation]
│   ├── secrets.py               scan / redact
│   ├── store.py                 đường dẫn, ID, đọc/ghi atomic, khoá, cleanup (R14)
│   ├── resolve.py               chọn handoff
│   ├── drift.py                 compute()
│   ├── render.py                captured md, resume, bảng list
│   ├── assets.py                đọc Asset + thay biến {{…}}
│   ├── doctor.py
│   ├── hook.py
│   └── assets/
│       ├── template.md
│       ├── skill_handoff.md     thân skill (không frontmatter)
│       ├── skill_resume.md
│       ├── skills.json          frontmatter của từng skill
│       ├── preamble.md          khối mở đầu của resume
│       ├── precompact.md        chỉ dẫn tóm tắt cho PreCompact (R23.2)
│       └── nudge.md             lời nhắc sau compaction (R23.5)
├── scripts/
│   ├── gen_plugin.py            sinh skills/*, kiểm version plugin.json; --check
│   ├── req_coverage.py          tiêu chí M1 chưa có test
│   ├── check_sizes.py           giới hạn dòng mỗi module (CS-13)
│   ├── eval_setup.sh            dựng repo mẫu cho kịch bản chuẩn (R24.1)
│   └── eval_check.py            chấm handoff theo rubric (R24.2)
├── tests/ …                     (§10)
├── docs/                        spec + CODING_STANDARDS; docs/specs/eval/ (scenario.md, rubric.json)
├── pyproject.toml · Makefile · README.md · CHANGELOG.md · LICENSE · CONTRIBUTING.md
```

M2 thêm: `clipboard.py`, `integrations.py` (`init`, AGENTS.md).

Hướng phụ thuộc (không vòng; kiểm bằng `test_imports.py`):

```
cli, hook ─► store, capture, drift, render, validate, secrets, resolve, doctor, assets, out
capture ─► gitio, gh ─► proc
drift ─► gitio
store ─► document, timeutil
render ─► document, capture(types), drift(types), assets
mọi module ─► errors, constants
```

Lõi thuần (không I/O): `document`, `validate`, `secrets`, `resolve`, `render`, phần tính toán của `drift` (nhận dữ liệu git đã lấy). Vỏ I/O: `proc`, `gitio`, `gh`, `store`, `out`, `cli`, `hook`.

## 4. Mô hình dữ liệu

### 4.1. File handoff — ví dụ

````markdown
---
id: 20261109-083012-feat-login
schema: 1
created_at: 2026-11-09T08:30:12Z
title: "Login form: wire OAuth callback"
status: open
repo: shop-web
worktree: /Users/dev/code/shop-web-login
branch: feat/login
head: 9f2c1e0a7b3d4c5e6f708192a3b4c5d6e7f80912
agent: claude-code
cairn_version: 0.1.0
session_id: 4f1c2a9e-0b7d-4e55-9a51-2d8c3f6e7a10
---
# Login form: wire OAuth callback

## Goal
Users can sign in with Google. Done = callback stores session and redirects to /dashboard; `login.spec.ts` passes.

## Current state
Callback route exchanges the code. Session cookie is NOT set yet.

## Decisions
- `iron-session` instead of JWT in localStorage — team security guideline.

## Tried / didn't work
- `next-auth` adapter: conflicts with custom user table; abandoned.

## Next steps
- [ ] Set session cookie in `app/api/auth/callback/route.ts`
- [ ] Redirect to /dashboard; handle `?error=`
- [ ] Run `pnpm test:e2e login`

## Open questions
- Cookie lifetime 7d or 30d? (ask user)

## Key files
- app/api/auth/callback/route.ts
- lib/session.ts

<!-- cairn:captured -->
## Captured state (auto-generated — do not edit)
<!-- cairn:captured-json {"schema":1,"current":{…WorktreeState…}} -->

Captured at 2026-11-09T08:30:12Z by cairn 0.1.0

### Worktree (current): /Users/dev/code/shop-web-login
- Branch: feat/login → origin/feat/login (ahead 2, behind 0)
- HEAD: 9f2c1e0 feat(auth): exchange oauth code
- PR: #142 "Login with Google" (draft) https://github.com/acme/shop-web/pull/142
- Stashes: 0
- Uncommitted (2):
  - ` M` app/api/auth/callback/route.ts
  - `??` lib/session.ts
- Recent commits:
  - 9f2c1e0 feat(auth): exchange oauth code
  - 41ab3d2 feat(auth): add callback route

### Other worktrees
| Branch | Path | Uncommitted | PR |
|---|---|---|---|
| main | /Users/dev/code/shop-web | 0 | — |
| fix/cart-total | /Users/dev/code/shop-web-cart | 3 | #139 |
````

### 4.2. Luật parse/render

**Frontmatter** — giữa dòng 1 `---` và `---` kế tiếp; mỗi dòng `key: value`, phẳng. `repo` = tên thư mục chứa `git-common-dir` (ví dụ `/code/shop-web/.git` → `shop-web`); `worktree` = `git rev-parse --show-toplevel`.
- Render: chuỗi mà trình đọc YAML có thể hiểu sai → `json.dumps` (rỗng; khoảng trắng đầu/cuối; bắt đầu bằng `"'[{&*!|>%@` hoặc backtick; chứa `: `, ` #` hoặc xuống dòng); `title` luôn JSON-quoted; còn lại viết trần (ví dụ `created_at: 2026-11-09T08:30:12Z`); số nguyên viết trần. Thứ tự khoá cố định theo R2.2, rồi `resumed_at`, `resume_count`, rồi khoá lạ.
- Parse: giá trị bắt đầu bằng `"` → `json.loads`; `schema`, `resume_count` → `int`; khoá lạ giữ nguyên thứ tự.

**Body** — giữa frontmatter và `<!-- cairn:captured -->`, bỏ dòng trắng thừa hai đầu. Section = dòng bắt đầu bằng `## ` tới section kế tiếp; so tên sau `strip()` + casefold; `Tried / didn't work` chấp nhận biến thể `Tried`, `Didn't work`. Title = dòng `# ` đầu tiên.

**Captured** — phần sau phân cách, giữ nguyên văn. Dữ liệu máy cho drift lấy từ frontmatter (`worktree`, `branch`, `head`) và khối `cairn:captured-json` (WorktreeState của worktree hiện tại, §4.3).

```python
@dataclass(frozen=True)
class Handoff:
    meta: Mapping[str, str | int]      # frontmatter, giữ thứ tự
    body: str                          # đã strip
    captured_md: str                   # đã strip
    path: Path | None = field(default=None, compare=False)   # có khi đọc từ Store
```

M0 chưa cần khối `cairn:captured-json`: drift M0 (R10.1–R10.4) chỉ dùng `worktree`, `branch`, `head` trong frontmatter. Task B1/E1 thêm trường `captured: WorktreeState | None` khi drift so tập file (R10.5).

### 4.3. `capture --json`

```json
{
  "schema": 1,
  "captured_at": "2026-11-09T08:30:12Z",
  "repo": "shop-web",
  "common_dir": "/Users/dev/code/shop-web/.git",
  "prs_status": "ok",
  "prs_error": null,
  "worktrees": [{
    "path": "/Users/dev/code/shop-web-login",
    "current": true,
    "branch": "feat/login",
    "detached": false,
    "head": "9f2c1e0a7b3d…",
    "head_subject": "feat(auth): exchange oauth code",
    "upstream": "origin/feat/login",
    "ahead": 2, "behind": 0,
    "stashes": 0,
    "changes": [{"xy": " M", "path": "app/api/auth/callback/route.ts"}],
    "changes_total": 2,
    "recent_commits": [{"sha": "9f2c1e0", "subject": "feat(auth): exchange oauth code"}],
    "prs": [{"number": 142, "title": "Login with Google", "url": "…", "draft": true}],
    "errors": {}
  }]
}
```

Ở frontmatter, detached HEAD ghi `branch: ""` và ID dùng nhãn `detached-<sha7>`; `cleanup` bỏ qua branch rỗng nên handoff detached không bị thay (R14.1). `upstream`, `ahead`, `behind` là `null` khi không có upstream; `stashes` là `null` cho worktree không phải current; `branch` là `null` khi detached.

### 4.4. `resume --json`

```json
{
  "handoff": {"meta": {}, "body": "…", "path": "…"},
  "drift": {
    "worktree_exists": true,
    "branch_changed": null,
    "head": {"state": "ahead", "new_commits": [], "new_commits_total": 3, "merge_base": null},
    "files": {"still_modified": [], "newly_modified": [], "now_clean": []},
    "lines": [{"level": "warn", "text": "3 new commits since handoff"}]
  }
}
```

`head.state ∈ {same, ahead, diverged, missing}`; `branch_changed` là `{"from","to"}` hoặc `null`.

## 5. Luồng xử lý

### 5.1. `save`

```
body = read_input(args)                     # --file | stdin; TTY không input → UsageError
body = apply_title(normalize(body), args.title)
findings = secrets.scan(body)
if findings and args.redact: body, n = secrets.redact(body); warn(n)
violations = validate(body) + as_violations(findings if not args.redact else [])
if any(v.level == "error"): raise InvalidHandoffError(violations)      # mã 3, mỗi dòng "line n: rule: msg"
warn(each warning)
repo = capture.collect(cwd, use_gh=not args.no_gh)
text = document.render(Handoff(meta=build_meta(repo.current, …), body, captured=repo.current),
                       captured_md=render.captured(repo))
if args.dry_run: emit(text); return
with store.lock():
    hid = store.write_new(text, created_at, branch)
    store.cleanup(replace_branch=branch, keep=hid)   # R14.1–R14.4
emit(f"saved {hid}")
```

Rule-id (dùng trong R5.4, định nghĩa trong `constants.py`): `missing-title`, `missing-section`, `empty-section`, `next-steps-no-items`, `body-too-long`, `reserved-marker`, `secret-<pattern>`, `missing-recommended` (warn), `body-long` (warn).

### 5.2. `resume`

```
h = resolve(ref, any_branch)
d = drift.compute(h)                      # không gọi gh
out = render.resume(h, d, brief=args.brief)   # hoặc JSON
if not args.peek:
    with store.lock(): store.mark_resumed(h); store.cleanup(keep=h.id)
emit(out)
```

`mark_resumed` đọc lại file trong khoá, chỉ thay frontmatter, ghi atomic.

`store.cleanup(*, replace_branch=None, keep)` — một hàm duy nhất cho R14: xoá handoff khác `keep` có `branch == replace_branch` (lý do `replaced`), rồi xoá bản hết hạn theo `CAIRN_KEEP_RESUMED`/`CAIRN_KEEP_OPEN` (lý do `expired`); chỉ đọc frontmatter; mỗi file xoá gọi `out.warn("removed <id> (<lý do>)")`; file không parse được thì bỏ qua, không xoá. Quyết định xoá là hàm thuần `expired(meta, now, keep_resumed, keep_open) -> bool` để test không cần file.

### 5.3. Preamble (`assets/preamble.md`)

```text
=== cairn handoff {{id}} ===
You are continuing work that a previous agent session handed off
(agent: {{agent}}, saved {{created_at}}, branch {{branch}}). Before changing anything:
1. Read this whole handoff.
2. Check "Drift since handoff": the repository may have changed since it was written.
3. Tell the user, in the language they are using: the goal, what is done, open questions,
   and the exact next step you propose.
4. If any drift line starts with "warn", wait for the user to confirm before editing code.

{{body}}

## Drift since handoff
{{drift}}               ← mỗi dòng "- <info|warn>: <text>"
{{captured}}            ← rỗng khi brief
=== end cairn handoff ===
```

`assets.fill(name, **values)` thay `{{key}}`; thiếu giá trị → `KeyError` (lỗi lập trình, test bắt được). Dòng `already resumed …` (R9.8) thêm ở M1 cùng lệnh `resume`.

### 5.4. Thuật toán drift

```
wt, saved, b = meta.worktree, meta.head, meta.branch
if not exists(wt):
    warn("worktree <wt> no longer exists")
    target = tip(b) if branch_exists(b) else None
    if target is None: return
else:
    target = head(wt)
    if current_branch(wt) != b: warn(branch_changed)
state = missing  if not commit_exists(saved)
        same     if saved == target
        ahead    if is_ancestor(saved, target)     → new_commits = log(saved..target, 10), total = count
        diverged otherwise                         → merge_base(saved, target) | None
files (khi wt tồn tại và h.captured có): old = paths(h.captured.changes); new = paths(status(wt))
    still = old ∩ new; newly = new − old; clean = old − new
level: ahead(total ≥ 1), diverged, missing, branch_changed, worktree mất → warn; files → info
không có gì → "no drift: nothing changed since the handoff"
```

Phần lấy dữ liệu git (`exists`, `head`, `log`, …) ở `gitio`; phần quyết định (`state`, `level`, tập file) là hàm thuần `drift.classify(facts) -> Drift` để test không cần repo. `merge-base` chỉ được gọi khi lịch sử đã rẽ nhánh. Worktree không còn → `state = unknown` kèm một dòng `warn` (M0); R10.7 (tính theo tip branch) bổ sung ở E1. Các hàm git của drift nhận `timeout` để hook dùng 2 giây (R18.4).

### 5.5. `hook session-start`

```
if env CAIRN_HOOK == "off": return 0
try:
    event = json.loads(stdin) if not stdin.isatty() else {}
    cwd = event.get("cwd") or os.getcwd()        # stdin hỏng/không phải object → cwd tiến trình
    b = current_branch(cwd)                      # ngoài repo hoặc detached → không làm gì
    h = newest(status="open", branch=b)
    if h is None or now - h.created_at > CAIRN_HOOK_MAX_AGE: return 0
    text = truncate(render.resume(h, drift.compute(h, git_timeout=2), brief=True), 9000)
    with store.lock():                             # cùng khoá với resume (§5.2)
        store.mark_resumed(h); store.cleanup(keep=h.id)
    emit(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                            "additionalContext": text}}))
except Exception as e:            # được phép duy nhất ở đây và cli.main (CS-28)
    warn(f"hook: {e}")
return 0
```

### 5.6. `hook pre-compact` và `hook post-compact` (R23)

```
pre_compact():                      # PreCompact, matcher manual|auto
    if env CAIRN_NUDGE == "off": return 0
    emit(assets.load("precompact.md"))   # stdout = chỉ dẫn cho bản tóm tắt
    return 0                             # không bao giờ chặn

post_compact():                     # SessionStart, matcher compact
    if env CAIRN_NUDGE == "off": return 0
    try:
        cwd = event.cwd or os.getcwd()
        if store.newest(branch=current_branch(cwd), max_age=CAIRN_NUDGE_WINDOW): return 0
        emit(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                "additionalContext": assets.load("nudge.md")}}))
    except Exception as e: warn(f"hook: {e}")
    return 0
```

`hook.py` dùng chung một hàm đọc event + bắt lỗi cho cả ba subcommand (CS-2); ba hàm trên chỉ khác phần thân. `pre-compact` không cần git nên không thể chậm hay lỗi do repo.

`precompact.md` (rút gọn): *"When summarizing, preserve verbatim: the goal and done-criteria, each decision with its reason, approaches that failed and why, the ordered next steps, open questions, key files. Do not compress these into generic statements."*

`nudge.md`: *"Context was just compacted and no cairn handoff was saved recently for this branch. In one short line, in the user's language, tell the user they can run /cairn:handoff to save one. Do not save it yourself unless they agree."*

### 5.7. Chấm chất lượng (R24)

`rubric.json`: `{"threshold": 7, "facts": [{"name": "goal", "patterns": ["(?i)oauth callback"]}, …]}`. `eval_check.py` đọc handoff (chỉ phần Body, cắt ở `<!-- cairn:captured -->`), một sự kiện đạt khi có ít nhất một pattern khớp; in `k/n` và tên sự kiện thiếu; mã 1 khi `k < threshold`. Script chỉ dùng stdlib, không import `agent_cairn` để không phụ thuộc mã đang được đo.

## 6. Bảo mật

### 6.1. Nguyên tắc

- Không lưu diff, nội dung file, env, token. Captured chỉ chứa metadata ở R12.5.
- Tạo thư mục `0700`; tạo file bằng `os.open(path, O_WRONLY|O_CREAT|O_EXCL, 0o600)` để không lệ thuộc umask.
- Không `shell=True`; tên branch/đường dẫn luôn là phần tử argv riêng; truyền ref cho git sau `--` khi có thể.
- Launcher chạy Python với `-E -s` để không bị `PYTHONPATH`/site-packages của người dùng chen vào.
- Hook và skill không ghi vào cấu hình người dùng.

### 6.2. Pattern secrets

| Tên | Regex (tóm tắt) |
|---|---|
| `private-key` | `-----BEGIN [A-Z ]*PRIVATE KEY-----` |
| `aws-access-key` | `\b(AKIA\|ASIA)[0-9A-Z]{16}\b` |
| `github-token` | `\bgh[pousr]_[A-Za-z0-9]{36,}\b`, `\bgithub_pat_[A-Za-z0-9_]{60,}\b` |
| `slack-token` | `\bxox[abprs]-[A-Za-z0-9-]{10,}\b` |
| `openai-key` | `\bsk-(proj-)?[A-Za-z0-9_-]{20,}\b` |
| `anthropic-key` | `\bsk-ant-[A-Za-z0-9_-]{20,}\b` |
| `jwt` | `\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b` |
| `assignment` | `(?i)\b(password\|passwd\|secret\|token\|api[_-]?key\|access[_-]?key)\b\s*[:=]\s*["']?([^\s"']{8,})` |

`assignment` bỏ qua placeholder: `<...>`, `${...}`, `***`, `xxx…`, `changeme`, `example`. `anthropic-key` được kiểm trước `openai-key`. `Finding(line, pattern)` không giữ giá trị.

## 7. Plugin Claude Code

### 7.1. Manifest

`.claude-plugin/plugin.json`:

```json
{
  "name": "cairn",
  "version": "0.1.0",
  "description": "Hand off work between Claude Code sessions, accounts and agents without re-explaining.",
  "author": { "name": "<owner>" },
  "license": "MIT",
  "repository": "https://github.com/<owner>/cairn"
}
```

`.claude-plugin/marketplace.json`:

```json
{
  "name": "cairn",
  "owner": { "name": "<owner>" },
  "plugins": [
    { "name": "cairn", "source": "./", "description": "Agent handoff: save and resume session context." }
  ]
}
```

Cài đặt:

```bash
claude plugin marketplace add ./cairn        # MVP, từ thư mục local
claude plugin install cairn@cairn
```

Sau khi publish: `claude plugin marketplace add <owner>/cairn`.

### 7.2. Launcher `bin/cairn`

```sh
#!/bin/sh
# cairn launcher: runs the bundled package with the system python3 (stdlib only).
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
py=${CAIRN_PYTHON:-python3}
if command -v "$py" >/dev/null 2>&1 \
   && "$py" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  exec "$py" -E -s -c \
    'import sys; sys.path.insert(0, sys.argv.pop(1)); from agent_cairn.cli import main; raise SystemExit(main())' \
    "$root/src" "$@"
fi
echo "cairn: python3 >= 3.9 is required" >&2
exit 1
```

### 7.3. Hook `hooks/hooks.json`

```json
{
  "description": "cairn: inject the open handoff at session start; keep reasoning through compaction",
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|clear",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/cairn",
            "args": ["hook", "session-start"], "timeout": 10 }
        ]
      },
      {
        "matcher": "compact",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/cairn",
            "args": ["hook", "post-compact"], "timeout": 10 }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "manual|auto",
        "hooks": [
          { "type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/cairn",
            "args": ["hook", "pre-compact"], "timeout": 10 }
        ]
      }
    ]
  }
}
```

M0 chỉ có entry `startup|clear`; hai entry còn lại thêm ở task E5.

Dạng exec (`command` + `args`) theo khuyến nghị của tài liệu hooks khi đường dẫn chứa placeholder. Task K5 xác nhận trên bản Claude Code đang cài trước khi chốt.

### 7.4. Skill — sinh từ Asset

`assets/skills.json` chứa frontmatter; `gen_plugin.py` ghép `frontmatter + "<!-- generated by scripts/gen_plugin.py from src/agent_cairn/assets — do not edit -->" + thân skill` (thay `{{template}}` bằng `template.md`).

`skills/handoff/SKILL.md` (kết quả sinh):

````markdown
---
name: handoff
description: >-
  Save a handoff of the current task so a new session (another account, agent, or tomorrow)
  can continue without the user re-explaining. Use when the user wants to stop, switch
  account, is running out of usage/quota, or says "handoff", "save context", "wrap up for
  the next session", "bàn giao", "lưu ngữ cảnh", "sắp hết quota", "đổi tài khoản".
argument-hint: "[title]"
allowed-tools: Bash(cairn save *)
---
<!-- generated by scripts/gen_plugin.py from src/agent_cairn/assets — do not edit -->
Write a handoff for the work in THIS conversation and save it with `cairn save`, in one go.

Rules:
- Write the handoff in English. Reply to the user in the language they are using.
- Be concrete: file paths, commands, error messages, decisions and WHY. Record approaches that
  failed so they are not retried. `Next steps` is an ordered checklist the next agent can start
  on immediately.
- Never include secrets, tokens, or large code blocks — reference file paths instead.
- If an `ARGUMENTS:` line follows these instructions, use its text as the title.

Steps:
1. Fill the template below from this conversation.
2. Run exactly:
   cairn save --dir "${CLAUDE_PROJECT_DIR}" --agent claude-code --session ${CLAUDE_SESSION_ID} --task <id> <<'CAIRN_EOF'
   <filled template>
   CAIRN_EOF
3. Exit code 3 means the handoff was rejected; each stderr line is `line N: rule: message`.
   Fix every reported line and run step 2 again. Stop after 3 attempts and show the user the
   remaining messages verbatim.
4. On success, reply in at most 2 lines: the saved id and the first next step.

Template:
```markdown
{{template}}
```
````

`skills/resume/SKILL.md`:

```markdown
---
name: resume
description: >-
  Continue work from the latest cairn handoff for this repository. Use when the user wants to
  pick up previous work: "resume", "continue where we left off", "what was I doing",
  "tiếp tục việc hôm qua", "làm tiếp", "đọc handoff".
argument-hint: "[handoff-id]"
allowed-tools: Bash(cairn resume *) Bash(cairn list *)
---
<!-- generated … -->
If a "cairn handoff" block is already in your context (injected at session start), use it and
do not run the command again. Otherwise run `cairn resume`, adding the id from an `ARGUMENTS:`
line if one follows.

Then follow the preamble in the output exactly. If it reports no handoff, run `cairn list`,
show the user the result, and ask which one to use.
```

Theo tài liệu skills: `allowed-tools` là danh sách cách nhau bằng dấu cách, mẫu `Bash(<lệnh> *)`; khi người dùng truyền đối số mà thân skill không có placeholder, Claude Code nối dòng `ARGUMENTS: <value>` — skill dựa vào dòng đó thay vì `$ARGUMENTS` (tài liệu không nói rõ `$ARGUMENTS` thành gì khi không có đối số). Việc `Bash(cairn save *)` có khớp lệnh heredoc hay không cần kiểm tay ([verification.md](verification.md) mục K5).

Ở M0 chưa có lệnh `cairn resume` (task E3), nên `skills/resume/SKILL.md` viết tay hướng dẫn agent chạy `cairn show` (R8, handoff mới nhất của branch) và tự so `head` bằng `git log`; P2 thay bằng bản sinh từ Asset ở trên.

## 8. Lệnh git

| Mục đích | Lệnh |
|---|---|
| Common dir | `git rev-parse --path-format=absolute --git-common-dir` |
| Worktree hiện tại | `git rev-parse --show-toplevel` |
| Worktree | `git worktree list --porcelain` |
| HEAD + subject | `git -C <p> log -1 --format=%H%x00%s` |
| Branch | `git -C <p> symbolic-ref -q --short HEAD` |
| Upstream | `git -C <p> rev-parse --abbrev-ref --symbolic-full-name @{u}` |
| Ahead/behind | `git -C <p> rev-list --left-right --count @{u}...HEAD` |
| Thay đổi | `git -C <p> status --porcelain=v1 -z --untracked-files=normal` |
| Stash | `git -C <p> stash list --format=%H` |
| Commit gần đây | `git -C <p> log -5 --format=%h%x00%s` |
| Commit tồn tại | `git cat-file -e <sha>^{commit}` |
| Tổ tiên | `git merge-base --is-ancestor <a> <b>` |
| Commit mới | `git log --format=%h%x00%s -10 <a>..<b>` + `git rev-list --count <a>..<b>` |
| Merge-base | `git merge-base <a> <b>` |
| Tip branch | `git rev-parse --verify -q refs/heads/<b>` |

`status -z`: bản ghi tách bằng `\0`; với `R`/`C` bản ghi kế là đường dẫn cũ — bỏ qua. Decode UTF-8 `errors="replace"`.

## 9. Xử lý lỗi

```python
class CairnError(Exception):        exit_code = 1
class UsageError(CairnError):       exit_code = 2
class InvalidHandoffError(CairnError):  exit_code = 3   # mang list[Violation]
class NotFoundError(CairnError):        exit_code = 4   # gồm cả mơ hồ
class NotAGitRepoError(CairnError):     exit_code = 5
```

`cli.main()` bắt `CairnError` → `out.note(msg)`, rồi in từng dòng `err.details` nguyên văn bằng `out.detail()` (dùng cho vi phạm R5.4) → trả `exit_code`. `KeyboardInterrupt` → 130. `BrokenPipeError` → 0 im lặng. Exception khác → R17.6. Lỗi git từng worktree trong `capture` ghi vào `errors`, không raise.

## 10. Chiến lược test

| Lớp | Cách làm |
|---|---|
| Lõi thuần | `document`, `validate`, `secrets`, `resolve`, `drift.classify`, `render` — dữ liệu dựng bằng factory trong `conftest.py`; output dài so golden (`tests/golden/`, cập nhật bằng `UPDATE_GOLDEN=1`). |
| Git thật | Fixture `git_repo`, `commit()`, `add_worktree()`, bare remote cho upstream. |
| `gh` giả | Fixture `fake_gh`: script trên `PATH` tạm — trả JSON / exit 1 / quá timeout / JSON hỏng / không có. |
| CLI | `main(argv)` + `capsys`; nhóm nhỏ chạy `bin/cairn` qua subprocess để kiểm launcher, mã thoát, không traceback. |
| Hook | Đưa JSON vào stdin; kiểm stdout rỗng / JSON hợp lệ; mã 0 khi Store hỏng, ngoài repo, Python lỗi giả lập. |
| Plugin | `gen_plugin.py --check` sạch; `plugin.json` hợp lệ JSON, version khớp; `hooks.json` có wrapper `hooks`; mỗi `SKILL.md` có frontmatter hợp lệ, description ≤ 1 000 ký tự, chứa cụm kích hoạt tiếng Việt. |
| Hook nén ngữ cảnh | `pre-compact`: stdout = Asset, mã 0 kể cả ngoài repo; `post-compact`: có handoff trong cửa sổ → rỗng, không có → JSON ≤ 600 ký tự; `CAIRN_NUDGE=off`. |
| Chất lượng | `eval_check.py` trên handoff mẫu đạt/không đạt; regex rubric không khớp chuỗi trong comment template. |
| Tĩnh | `test_imports.py` (stdlib-only, đồ thị phụ thuộc §3, chỉ `proc` import subprocess, chỉ `out` gọi print). |
| Truy vết | `@pytest.mark.req("Rn.m")` + `scripts/req_coverage.py`. |

Fixture autouse cô lập: `CAIRN_STORE`, `CAIRN_HOME`, `HOME`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_CONFIG_NOSYSTEM=1`, `NO_COLOR=1`, đồng hồ cố định.

## 11. Hướng mở rộng

- M2: pipx/PyPI, `init`, AGENTS.md, `prompt`, `rm`, `--copy`.
- M3: export/import giữa các máy; handoff nhiều repo; integration Kiro/Codex riêng.
