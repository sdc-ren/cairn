# Requirements — cairn v1 (Agent Handoff)

| Thuộc tính | Giá trị |
|---|---|
| Trạng thái | Draft — chờ duyệt |
| Phiên bản spec | 1.9 |
| Ngày | 2026-11-09 |
| Tài liệu liên quan | [design.md](design.md) · [tasks.md](tasks.md) · [CODING_STANDARDS](../CODING_STANDARDS.md) |

**Tên gọi.** Lệnh và plugin tên `cairn` (đống đá người leo núi để lại chỉ đường cho người đến sau). Tên package PyPI là `agent-cairn` vì `cairn` đã có người dùng; tên import Python là `agent_cairn`.

## 1. Bối cảnh và bài toán

Khi phiên làm việc với AI agent bị gián đoạn — hết hạn mức tài khoản, đổi tài khoản, đổi agent, context bị compact, hay mở phiên mới hôm sau — agent mới **mất phần lý luận** của phiên trước: mục tiêu và tiêu chí "xong", quyết định đã chốt và lý do, hướng đã thử thất bại, bước tiếp theo, câu hỏi còn mở.

Dữ kiện git agent mới tự đọc được; **lý do thì chỉ agent cũ biết**. Vì vậy chỉ chụp dữ kiện git là giải sai bài toán; cái cần lưu là lý do.

## 2. Giải pháp tóm tắt

`cairn` quản lý **Handoff Document** — file markdown gồm:

1. **Phần agent viết** (Goal, Current state, Decisions, Tried, Next steps, …) — do agent đang chạy soạn trước khi dừng.
2. **Phần máy chụp** (Captured state) — CLI tự điền dữ kiện git/PR của mọi worktree.

Phiên mới nhận lại handoff kèm **Drift report** — những gì repo đã đổi kể từ lúc viết.

**Người dùng chỉ có một thao tác chủ động** (R16, R23):

| Khi | Người dùng làm | Bên dưới (tự động) |
|---|---|---|
| Sắp dừng | Gõ `/cairn:handoff` (hoặc nói "handoff", "sắp hết quota") | Agent soạn nội dung theo template → `cairn save` → tự sửa nếu bị từ chối → báo một dòng |
| Phiên mới | Không làm gì | Hook `SessionStart` chèn handoff đang mở + drift vào ngữ cảnh; agent tóm tắt và hỏi xác nhận |
| (dự phòng) | Gõ `/cairn:resume` | Như trên, theo yêu cầu |
| Ngữ cảnh sắp bị nén | Không làm gì | Hook `PreCompact` giữ lý luận trong bản tóm tắt; sau khi nén, agent nhắc một dòng nếu chưa có handoff gần đây (R23) |

**Bản MVP (M1) là plugin Claude Code tự chứa:** plugin mang theo mã CLI trong `bin/` và `src/`, skill và hook. Cài bằng hai lệnh `claude plugin …`, không cần pipx, không chạy lệnh cài đặt phụ. Kênh pipx/PyPI cho agent khác để M2.

## 3. Mục tiêu và phi mục tiêu

### Mục tiêu

- G1. Lưu handoff bằng **một** thao tác của người dùng.
- G2. Phiên mới nhận handoff với **không** thao tác nào (hook), hoặc một (`/cairn:resume`).
- G3. Handoff không mất trước khi hết vai trò: đọc/resume không xoá; chỉ xoá khi đã có bản mới hơn cùng branch hoặc đã hết hạn (R14).
- G4. Người dùng không bao giờ phải tự sửa file handoff hay cấu hình bằng tay.
- G5. Cài đặt MVP ≤ 2 lệnh, không cần quyền admin.
- G6. Mã nguồn tuân thủ [CODING_STANDARDS](../CODING_STANDARDS.md); không trùng lặp logic.

### Phi mục tiêu

- NG1. Không đọc/parse transcript hội thoại.
- NG2. Không đồng bộ qua mạng hay giữa các máy (v1). Đổi tài khoản trên **cùng máy** không cần đồng bộ vì Store là file cục bộ.
- NG3. Không lưu diff hay nội dung file nguồn.
- NG4. Không tự gọi LLM để tóm tắt.
- NG5. Không gom nhiều repo vào một handoff (v1).
- NG6. Không hỗ trợ Windows (v1).

## 4. Người dùng và kịch bản

| Persona | Mô tả |
|---|---|
| **Dev** | Người dùng Claude Code, có thể có nhiều tài khoản. |
| **Agent cũ** | Agent đang có đủ ngữ cảnh, sắp dừng. |
| **Agent mới** | Agent vừa khởi động, không có ngữ cảnh. |

- **S1 — Đổi tài khoản giữa chừng.** Dev gõ `/cairn:handoff` → agent lưu, báo `saved <id>` → Dev `/logout`, đăng nhập tài khoản khác, mở phiên mới → hook chèn handoff → agent tóm tắt mục tiêu và bước tiếp theo, chờ Dev xác nhận.
- **S2 — Hôm sau làm tiếp.** Dev đã commit tay sau handoff. Phiên mới nhận drift `3 new commits since handoff` nên không tin trạng thái cũ.
- **S3 — Nhiều worktree.** Mỗi worktree có handoff theo branch; hook chỉ chèn handoff của branch đang đứng.
- **S4 — Đổi sang agent khác (M2).** Dev chạy `cairn resume --copy` rồi paste, hoặc agent tự chạy theo `AGENTS.md`.

## 5. Thuật ngữ

| Thuật ngữ | Định nghĩa |
|---|---|
| **Handoff** | Một Handoff Document đã lưu, định danh bằng Handoff ID. |
| **Handoff ID** | `YYYYMMDD-HHMMSS-<nhãn>` (UTC); nhãn là slug của Task, ngược lại của branch, ngược lại `workspace`. Ví dụ `20261109-083012-proj-268`. |
| **Branch slug** | Tên branch chữ thường, ký tự ngoài `[a-z0-9-]` đổi thành `-`, gộp `-` liên tiếp, tối đa 40 ký tự. Detached HEAD → `detached-<sha7>`. |
| **Cairn home** | `$CAIRN_HOME` hoặc `~/.cairn` — gốc chung của mọi Store trên máy. |
| **Dự án** | Trong git repo: thư mục gốc repo chính (thư mục cha của `git-common-dir`), dùng chung mọi worktree. Ngoài git (ví dụ workspace chứa nhiều repo): chính thư mục làm việc. |
| **Task** | Mã công việc agent điền khi nhận ra (ticket như `PROJ-268`, hoặc tên phiên); trường `task` trong frontmatter. |
| **Khoá handoff** | Task nếu có; ngược lại branch; ngoài git và không có task thì là chính Dự án. Mỗi Khoá giữ một handoff (R14.1). |
| **Workspace section** | Section `## Workspace` trong Body: mỗi dòng `- <nhãn>: <giá trị>`; nhãn `worktree` và `pipeline` được cairn chụp và kiểm drift (R4.10, R10.10). |
| **Store** | `<cairn-home>/<project-slug>-<hash8>/` — kho handoff của một Dự án. |
| **Body** | Phần agent viết. |
| **Captured state** | Phần CLI tự sinh lúc `save`. |
| **Frontmatter** | Metadata đầu file giữa hai dòng `---`, dạng `key: value` phẳng. |
| **Drift report** | So sánh trạng thái đã lưu với hiện tại khi resume. |
| **Status** | `open` (chưa resume) hoặc `resumed`. |
| **Plugin** | Thư mục gốc repo `cairn`, đồng thời là marketplace Claude Code chứa đúng một plugin. |
| **Asset** | File văn bản cho agent trong `src/agent_cairn/assets/` — nguồn duy nhất sinh ra skill, template, preamble. |

## 6. Quy ước

- **PHẢI / KHÔNG ĐƯỢC / NÊN / CÓ THỂ** theo RFC 2119. Tiêu chí dạng EARS.
- **M0** = bộ khung 0.0.x (chạy được đầu–cuối, dùng thử sớm), là **tập con của M1** liệt kê ở bảng dưới; **M1** = MVP 0.1 (tự dùng); **M2** = 0.2 (phát hành rộng); **M3** = sau này.
- Mức của requirement ghi ở tiêu đề; tiêu chí khác mức ghi riêng ở cuối dòng. Thuộc M0 hay không chỉ ghi ở bảng dưới, không ghi ở tiêu đề.
- Tiêu chí có `[manual]` cuối dòng chỉ kiểm được bằng tay trên Claude Code thật: bằng chứng ghi trong `verification.md` dưới tiêu đề chứa ID tiêu chí, thay cho test tự động (R20.2).

### Phạm vi M0 — bộ khung chạy được

Mục đích: có luồng S1 chạy thật trên máy sau 1–2 ngày để dùng thử và sửa spec bằng trải nghiệm thật, trước khi làm phần còn lại.

| Nhóm | Thuộc M0 | Để M1 |
|---|---|---|
| R1 Store | R1.1, R1.3–R1.10 | R1.2 |
| R2 Định dạng | R2.1–R2.5, R2.7, R2.8 | R2.6, R2.9 |
| R3 `template` | R3.1, R3.2 (Asset, nhúng vào skill; chưa cần lệnh `template`) | R3.3 |
| R4 Capture | R4.2 rút gọn: chỉ worktree hiện tại (branch, head, file thay đổi, 5 commit); R4.9; R4.10 | Còn lại (mọi worktree của repo, `gh`, lệnh `capture`) |
| R5 `save` | R5.1, R5.3 (chỉ các luật **lỗi**), R5.4, R5.5 (`--agent`, `--session`, `--task`), R5.6, R5.9 | Còn lại |
| R6 `list` | R6.1, R6.2, R6.3 (`--status`), R6.5, R6.6 | R6.3 (`--branch`, `--here`), R6.4 |
| R7, R8 `show` | R7.1 (Task hoặc ID đầy đủ), R7.2, R7.5, R8.1–R8.3 | R7.1 (tiền tố), R7.3, R7.4 |
| R9 `resume` | R9.1–R9.5 (hook và lệnh `resume [ref]`) | R9.6–R9.9 |
| R10 Drift | R10.1–R10.4, R10.8, R10.10 | Còn lại |
| R11 Plugin | R11.1–R11.6, R11.9 (`SKILL.md` viết tay) | R11.7, R11.8 (sinh từ Asset) |
| R12 Secrets | R12.1, R12.2, R12.4, R12.5 | R12.3 |
| R13 Hook | R13.1–R13.9 | — |
| R14 Tự dọn | R14.1, R14.5 (thay bản cũ khi `save`) | R14.2–R14.4, R14.6–R14.8 (R14.9 là M2) |
| R16 Một lệnh | R16.1–R16.3, R16.6–R16.8 | R16.4, R16.5 |
| R18 Nền tảng | R18.1, R18.4, R18.5 | Còn lại |
| R22 Ngôn ngữ | R22.1, R22.3 | R22.2, R22.4 |
| R24 Chất lượng | R24.3 (nhật ký dùng thật) | Còn lại |

Ngoài bảng trên (R15, R17, R19–R21, R23) không thuộc M0. Ở M0 chỉ chạy `ruff` + `pytest`; bộ kiểm đầy đủ của CODING_STANDARDS §9 bật từ M1. Mã M0 vẫn phải theo layout và quy tắc một nguồn (CS-2) để M1 mở rộng chứ không viết lại.

---

## 7. Yêu cầu chức năng

### R1. Store `[M1]`

1. cairn PHẢI dùng Store `<cairn-home>/<project-slug>-<hash8>/`: Dự án theo định nghĩa ở §5 (`git rev-parse --path-format=absolute --git-common-dir` nếu trong git); `project-slug` là tên thư mục Dự án theo luật Branch slug; `hash8` là 8 ký tự hex đầu của SHA-256 đường dẫn tuyệt đối Dự án. Mọi worktree của một repo dùng chung một Store.
2. KHI biến `CAIRN_STORE` được đặt, THÌ cairn PHẢI dùng giá trị đó làm Store; KHI `CAIRN_HOME` được đặt, THÌ dùng nó thay cho `~/.cairn`.
3. KHI Store chưa có và lệnh cần ghi, THÌ cairn PHẢI tạo Store (và Cairn home nếu chưa có) với permission `0700`.
4. Mỗi handoff PHẢI là file `<store>/<id>.md`, permission `0600`; file quản lý (`.project.json`, `.lock`) là file ẩn để `ls` chỉ thấy handoff.
5. Ghi file PHẢI atomic (file tạm cùng thư mục + `os.replace`).
6. KHI trùng ID, THÌ cairn PHẢI thêm hậu tố `-2`, `-3`, … thay vì ghi đè.
7. KHI `capture` chạy ngoài git repo, THÌ cairn PHẢI báo `not a git repository` và thoát mã 5. Mọi lệnh khác chạy được ngoài git (R1.9).
8. KHI Store được tạo, THÌ cairn PHẢI ghi `<store>/.project.json` dạng `{"path": "<đường dẫn Dự án>"}` để người đọc biết thư mục thuộc dự án nào.
9. Thư mục không phải git repo PHẢI dùng được: Dự án là chính thư mục đó, handoff có `branch`/`head` rỗng, Captured state ghi `not a git repository`, drift chỉ gồm các mục của Workspace section (R10.10).
10. Các lệnh làm việc với Store PHẢI nhận `--dir <path>` để chỉ định thư mục làm việc thay cho cwd tiến trình (skill truyền `${CLAUDE_PROJECT_DIR}` vì cwd của Bash tool có thể đã đổi).

### R2. Định dạng Handoff Document `[M1]`

1. File PHẢI gồm theo thứ tự: Frontmatter, Body, Captured state.
2. Frontmatter PHẢI có: `id`, `schema` (=`1`), `created_at` (ISO 8601 UTC, hậu tố `Z`), `title`, `status`, `repo`, `worktree`, `branch`, `head` (SHA đầy đủ), `agent` (mặc định `unknown`), `cairn_version`.
3. Frontmatter CÓ THỂ có `task`, `session_id` (phiên đã viết handoff), `resumed_at`, `resume_count`.
4. Body PHẢI bắt đầu bằng `# <title>` và chứa section bắt buộc: `## Goal`, `## Current state`, `## Next steps`.
5. Body NÊN chứa: `## Decisions`, `## Tried / didn't work`, `## Open questions`, `## Key files`, `## Workspace`.
6. Section khác PHẢI được giữ nguyên.
7. Captured state PHẢI nằm sau dòng `<!-- cairn:captured -->`, bắt đầu bằng `## Captured state (auto-generated — do not edit)`.
8. Nội dung template, tên section, Captured state PHẢI bằng tiếng Anh (R22).
9. `parse(render(h)) == h` cho mọi handoff do cairn ghi (round-trip).

### R3. Lệnh `template` `[M1]`

1. `cairn template` PHẢI in Body mẫu: title placeholder, 3 section bắt buộc, 4 section khuyến nghị, mỗi section một comment HTML hướng dẫn.
2. Template PHẢI đánh dấu rõ section bắt buộc.
3. Template để nguyên PHẢI bị `save` từ chối; template được điền nội dung PHẢI qua kiểm tra.

### R4. Lệnh `capture` `[M1]`

1. PHẢI liệt kê mọi worktree từ `git worktree list --porcelain`, bỏ worktree `prunable`.
2. Mỗi worktree PHẢI có: path, branch (hoặc detached + sha7), `head`, upstream + ahead/behind (nếu có), file thay đổi kèm mã porcelain, số stash (chỉ worktree hiện tại), 5 commit gần nhất.
3. Danh sách file PHẢI giới hạn 50 mục, phần dư ghi `… and N more`.
4. KHI có `gh` và không có `--no-gh`, THÌ PHẢI lấy PR mở (`gh pr list --state open --json number,title,url,headRefName,isDraft --limit 100`, timeout 5 giây) và gắn vào worktree trùng `headRefName`.
5. KHI `gh` không có, lỗi hoặc quá hạn, THÌ PHẢI tiếp tục, ghi `PRs: unavailable (<lý do>)`, cảnh báo ra stderr, mã thoát 0.
6. Worktree hiện tại PHẢI đánh dấu `(current)` và đứng đầu.
7. `--json` PHẢI in theo schema design §4.3.
8. Lỗi git ở một worktree PHẢI được ghi `error: <ngắn gọn>` cho trường đó, các worktree khác vẫn xử lý.
9. `capture` KHÔNG ĐƯỢC ghi vào Store.
10. KHI Body có Workspace section, THÌ `save` PHẢI chụp với mỗi dòng `worktree: <path>` (tương đối theo Dự án hoặc tuyệt đối): có tồn tại không, branch, `head`, số file chưa commit; với mỗi dòng `pipeline: <path>`: có tồn tại không. Kết quả nằm trong Captured state và khối máy đọc `cairn:captured-json`. Dòng nhãn khác giữ nguyên văn, không kiểm.

### R5. Lệnh `save` `[M1]`

1. PHẢI đọc Body từ `--file <path>`, hoặc stdin khi `--file -` hay khi stdin không phải TTY.
2. KHI không có input (stdin là TTY, không `--file`), THÌ PHẢI báo lỗi usage, gợi ý `cairn template`, thoát mã 2.
3. PHẢI kiểm tra Body; vi phạm **lỗi** → không lưu, in mọi vi phạm (kèm số dòng nếu có) ra stderr, thoát mã 3:
   - (lỗi) Thiếu `# <title>` hoặc title rỗng/placeholder.
   - (lỗi) Thiếu section bắt buộc.
   - (lỗi) Section bắt buộc rỗng — sau khi bỏ comment HTML và khoảng trắng không còn gì, hoặc chỉ còn `TODO`/`TBD`/`...`.
   - (lỗi) `## Next steps` không có list item nào (`- `, `* `, `1. `, `- [ ]`).
   - (lỗi) Body > 12 000 ký tự.
   - (lỗi) Body chứa dòng `<!-- cairn:captured -->`.
   - (cảnh báo) Thiếu section khuyến nghị; Body > 6 000 ký tự.
4. Mỗi vi phạm PHẢI là một dòng dạng `line <n>: <rule-id>: <message>` (bỏ `line <n>:` khi không xác định) để agent sửa được mà không cần đoán.
5. `--title` ghi đè title; `--agent` ghi `agent`, mặc định lấy `CAIRN_AGENT`, rồi `unknown`; `--session` ghi `session_id`; `--task` ghi `task`.
6. PHẢI quét secrets (R12) trước khi lưu.
7. Captured state PHẢI đầy đủ (R4.2) cho worktree hiện tại và một dòng tóm tắt cho mỗi worktree khác.
8. `--no-gh` bỏ truy vấn PR; `--dry-run` in file sẽ ghi ra stdout và không ghi Store.
9. Thành công: in đúng một dòng `saved <id>` ra stdout, cảnh báo ra stderr, mã 0, `status: open`.

### R6. Lệnh `list` `[M1]`

1. PHẢI liệt kê handoff của Dự án, mới nhất trước, mỗi dòng: ID, Task (không có thì branch, không có nữa thì `-`), status, tuổi (`2h ago`), title (cắt 60 ký tự + `…`).
2. Mặc định 20 dòng; `--limit N`; `--all`.
3. `--branch <b>` lọc branch; `--here` lọc branch hiện tại; `--status open|resumed`.
4. `--json` in mảng frontmatter.
5. Store rỗng → in `no handoffs yet` và mã 0.
6. File không parse được → bỏ qua, cảnh báo kèm tên file, vẫn liệt kê phần còn lại.

### R7. Chọn handoff `[M1]`

Áp dụng cho `show`, `resume`, `rm`.

1. `<ref>` là Task (không phân biệt hoa thường, khớp chính xác) hoặc ID đầy đủ hoặc tiền tố ID duy nhất ≥ 4 ký tự.
2. Không có `<ref>` → handoff mới nhất của branch hiện tại; nếu không có thì mới nhất của Dự án kèm cảnh báo `no handoff for branch <b>; using latest in project`.
3. `--any-branch` bỏ ưu tiên branch.
4. Tiền tố khớp nhiều → in các ID khớp ra stderr, mã 4.
5. Không tìm thấy → `handoff not found: <ref>`, mã 4.

### R8. Lệnh `show` `[M1]`

1. In nguyên văn file handoff.
2. KHÔNG ĐƯỢC đổi nội dung hay status.
3. `--path` chỉ in đường dẫn tuyệt đối.

### R9. Lệnh `resume` `[M1]`

1. PHẢI in theo thứ tự: preamble cho agent (design §5.3), Body, Drift report, Captured state đã lưu, dòng kết.
2. Preamble PHẢI yêu cầu agent: đọc hết; kiểm Drift; tóm tắt cho người dùng mục tiêu, việc đã xong, bước tiếp theo; chờ xác nhận trước khi sửa code nếu Drift có `warn`.
3. Không có `--peek` → cập nhật `status: resumed`, `resumed_at`, `resume_count += 1`; Body và Captured state giữ nguyên byte-for-byte.
4. `--peek` không cập nhật gì.
5. `resume` KHÔNG ĐƯỢC xoá handoff đang được resume; việc xoá chỉ theo R14.
6. `--brief` bỏ Captured state đầy đủ.
7. `--json` in `{handoff, drift}` theo design §4.4.
8. Handoff đã `resumed` vẫn resume được, preamble thêm `already resumed <n> time(s), last <time>`.
9. `--copy` sao chép output vào clipboard (`pbcopy`; Linux: `wl-copy`/`xclip`); không có công cụ → cảnh báo, vẫn in stdout, mã 0. `[M2]`

### R10. Drift report `[M1]`

1. So `head` đã lưu với `HEAD` hiện tại của worktree trong handoff.
2. `head` cũ là tổ tiên → ghi số commit mới, liệt kê tối đa 10.
3. Không còn là tổ tiên → `warn: history diverged since handoff` + merge-base nếu có.
4. `head` cũ không còn tồn tại → `warn: saved head <sha7> no longer exists`.
5. So tập file chưa commit: vẫn sửa / mới sửa / đã sạch.
6. Branch của worktree đã đổi → `warn: worktree is now on <b2> (handoff was on <b1>)`.
7. Worktree không còn → cảnh báo, tính drift theo tip branch đã lưu nếu còn.
8. Không có gì đổi → đúng một dòng `no drift: nothing changed since the handoff`.
9. Mỗi dòng có mức `info` hoặc `warn`; `resume` vẫn thoát mã 0 khi có `warn`.
10. Với mỗi mục `worktree` đã chụp (R4.10): không còn → `warn: worktree <p> no longer exists`; còn thì so như R10.2–R10.4 và R10.6 nhưng mỗi dòng có tiền tố `worktree <p>:`, không đổi gì thì không in. Với mỗi `pipeline`: không còn → `warn: pipeline <p> no longer exists`. Ngoài git, phần drift của Dự án được bỏ qua.

### R11. Plugin Claude Code `[M1]`

**User story:** Là Dev, tôi muốn cài một lần là có đủ lệnh, skill và hook, không phải cài thêm CLI hay sửa cấu hình.

1. Thư mục gốc repo PHẢI vừa là plugin vừa là marketplace: `.claude-plugin/plugin.json` (tên `cairn`) và `.claude-plugin/marketplace.json` (tên `sdc-ren`, theo chủ sở hữu, để lệnh cài đọc là `cairn@sdc-ren`) có đúng một plugin `cairn` với `"source": "./"`.
2. Cài đặt PHẢI chỉ cần: `claude plugin marketplace add <owner>/cairn` rồi `claude plugin install cairn@sdc-ren` (hoặc tương đương `/plugin …` trong phiên). Cài từ thư mục local (`claude plugin marketplace add ./cairn`) PHẢI hoạt động để tự dùng trước khi publish. `[manual]`
3. Plugin PHẢI có `bin/cairn` — launcher POSIX `sh` chạy `python3` trên mã trong `src/` của chính plugin; không cần pipx hay mạng. Claude Code đưa `bin/` vào PATH của Bash tool nên skill gọi được `cairn` trực tiếp.
4. KHI không tìm thấy `python3` ≥ 3.9, THÌ launcher PHẢI in `cairn: python3 >= 3.9 is required` ra stderr và thoát mã 1.
5. Plugin PHẢI có skill `handoff` (`skills/handoff/SKILL.md`, gọi là `/cairn:handoff`) và `resume` (`/cairn:resume`), cho phép cả người dùng gọi và model tự kích hoạt.
6. Plugin PHẢI đăng ký hook `SessionStart` (R13) trong `hooks/hooks.json`, gọi `${CLAUDE_PLUGIN_ROOT}/bin/cairn hook session-start` ở dạng exec (không qua shell). Hook của R23 khai báo cùng file, cùng dạng.
7. File `SKILL.md` và template trong skill PHẢI được **sinh** từ Asset bằng `scripts/gen_plugin.py`; CI PHẢI chạy `gen_plugin.py --check` và fail nếu file đã commit lệch với Asset.
8. `plugin.json` `version` PHẢI bằng `agent_cairn.__version__` (kiểm trong `--check`).
9. Plugin KHÔNG ĐƯỢC ghi vào `settings.json` hay bất kỳ cấu hình nào của người dùng.

### R12. Quét secrets `[M1]`

1. Quét Body theo bộ pattern design §6.2.
2. Phát hiện → mặc định từ chối lưu, in số dòng + tên pattern (KHÔNG in giá trị), mã 3.
3. `--redact` thay giá trị bằng `[REDACTED:<pattern>]` rồi lưu, cảnh báo số chỗ thay.
4. KHÔNG ĐƯỢC đưa diff, nội dung file, env, output `gh auth` vào handoff.
5. Captured state chỉ chứa: đường dẫn, branch, SHA, commit subject, mã trạng thái file, PR number/title/url/draft.

### R13. Hook `SessionStart` `[M1]`

**User story:** Là Dev, tôi muốn phiên mới tự nhận handoff đang mở mà không phải gõ gì.

1. `cairn hook session-start` PHẢI đọc JSON từ stdin, dùng trường `cwd` nếu có, ngược lại cwd tiến trình.
2. Hook PHẢI đăng ký với matcher `startup|clear` (không chạy khi resume/compact phiên cũ — phiên đó vẫn còn ngữ cảnh).
3. KHI Dự án có handoff `status: open` tuổi ≤ `CAIRN_HOOK_MAX_AGE` (mặc định `7d`), THÌ PHẢI chọn bản cùng branch hiện tại nếu có, ngược lại bản mới nhất (mỗi phiên có thể là một worktree/branch mới nên không đòi khớp branch), in JSON `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": <resume --brief>}}` ra stdout và cập nhật status như R9.3.
4. Ngược lại PHẢI không in gì ra stdout.
5. `additionalContext` PHẢI ≤ 9 000 ký tự (giới hạn của Claude Code là 10 000); dài hơn thì cắt và thêm `[truncated — run: cairn show <id>]`.
6. KHÔNG ĐƯỢC gọi `gh` hay lệnh mạng.
7. PHẢI luôn thoát mã 0, hoàn thành ≤ 2 giây với repo ≤ 10 worktree; lỗi chỉ ra stderr.
8. `CAIRN_HOOK=off` tắt hook.
9. KHI Dự án còn handoff `open` khác trong hạn, THÌ preamble PHẢI liệt kê chúng (Task hoặc ID, title) và cách đổi: `/cairn:resume <task>`; các bản đó giữ `open`.

### R14. Vòng đời và tự dọn `[M1]`

**User story:** Là Dev, tôi muốn Store tự gọn — mỗi branch chỉ còn handoff mới nhất, bản đã dùng tự biến mất sau một thời gian — mà không phải dọn tay, nhưng vẫn cứu được nếu phiên mới hỏng ngay sau khi nhận.

1. Sau khi `save` ghi thành công, cairn PHẢI xoá mọi handoff khác có cùng Khoá handoff (bất kể status). Handoff ở detached HEAD không có Task thì không bị thay thế, chỉ hết hạn theo R14.2–R14.3.
2. Handoff `resumed` có `resumed_at` cũ hơn `CAIRN_KEEP_RESUMED` (mặc định `7d`) PHẢI bị xoá.
3. Handoff `open` có `created_at` cũ hơn `CAIRN_KEEP_OPEN` (mặc định `30d`) PHẢI bị xoá.
4. Dọn theo R14.2–R14.3 PHẢI chạy ở mọi lệnh ghi Store (`save`, `resume` không `--peek`, `hook session-start`), trong cùng khoá ghi; lệnh chỉ đọc (`list`, `show`, `capture`, `resume --peek`) và `hook pre-compact`/`post-compact` KHÔNG ĐƯỢC xoá.
5. Mỗi handoff bị xoá PHẢI in một dòng `cairn: removed <id> (<replaced|expired>)` ra stderr; trong hook chỉ ghi stderr, stdout giữ đúng R13.3–R13.4.
6. `save --dry-run` KHÔNG ĐƯỢC xoá gì.
7. Handoff vừa được resume KHÔNG ĐƯỢC bị xoá trong chính lệnh đó.
8. Ngoài R14.1–R14.3 và R14.9, không cơ chế nào được xoá handoff.
9. `cairn rm <ref>…` xoá tay sau khi hỏi `delete N handoff(s)? [y/N]`; `--yes` bỏ hỏi; stdin không phải TTY và không `--yes` → từ chối, mã 2. `[M2]`

### R15. Lệnh `doctor` `[M1]`

1. In mỗi mục một dòng `ok`/`warn`/`fail`: Python, `git` ≥ 2.31, trong repo, Store ghi được, `gh` có và đã đăng nhập (chỉ lấy mã thoát `gh auth status`), plugin root và phiên bản khớp `__version__`, (M2) clipboard và cài đặt pipx.
2. Mã 0 khi không có `fail`, ngược lại 1.

### R16. Trải nghiệm một lệnh `[M1]`

**User story:** Là Dev, tôi chỉ muốn gõ một lệnh để lưu và không làm gì để khôi phục; mọi bước bên dưới phải tự chạy.

1. KHI người dùng gọi `/cairn:handoff [title]`, THÌ skill PHẢI hướng dẫn agent hoàn tất trong một lượt: soạn Body từ hội thoại theo template có sẵn trong skill (không bắt agent chạy `template`), gọi `cairn save` một lần qua heredoc.
2. KHI `save` trả mã 3, THÌ skill PHẢI hướng dẫn agent sửa đúng các vi phạm được báo và thử lại, tối đa 3 lần; quá 3 lần thì báo người dùng nguyên văn vi phạm còn lại.
3. KHI lưu thành công, THÌ agent PHẢI trả lời người dùng tối đa 2 dòng: ID đã lưu và bước tiếp theo đầu tiên.
4. Skill `handoff` PHẢI tự kích hoạt khi người dùng nói ý định dừng/đổi phiên, bằng tiếng Anh hoặc tiếng Việt (ví dụ "handoff", "save context", "sắp hết quota", "lưu ngữ cảnh", "đổi tài khoản"). `[manual]`
5. Skill `resume` PHẢI tự kích hoạt khi người dùng muốn tiếp tục việc trước hoặc hỏi việc nào đang dở ("continue where we left off", "tiếp tục việc hôm qua", "làm tiếp", "còn task nào đang dở"). `[manual]`
6. Khi hook đã chèn handoff, agent PHẢI có đủ chỉ dẫn trong preamble để tự tóm tắt mà không cần gọi skill `resume`.
7. Người dùng KHÔNG ĐƯỢC phải chạy lệnh nào trong terminal trong luồng S1 sau khi đã cài plugin. `[manual]`
8. KHI `/cairn:resume` không kèm task và hook chưa chèn handoff, THÌ skill PHẢI chạy `cairn list --status open`: không có → báo và cho xem 5 bản gần nhất; đúng một → resume luôn; nhiều → hiện bảng và hỏi người dùng chọn, không tự chọn. Chỉ hỏi danh sách thì hiện bảng và dừng (design D21).

---

## 8. Yêu cầu phi chức năng

### R17. Quy ước CLI `[M1]`

1. `cairn <command> [options] [args]`; lệnh M1: `template`, `capture`, `save`, `list`, `show`, `resume`, `doctor`, `hook` (`session-start`, `pre-compact`, `post-compact`), `version`; M2 thêm `rm`, `init`, `prompt`.
2. `cairn`, `-h`, `--help` in usage ra stdout, mã 0; `cairn <cmd> -h` in help lệnh.
3. `cairn version` / `--version` in `cairn <version>`, mã 0.
4. Dữ liệu ra stdout; cảnh báo/lỗi ra stderr.
5. Mã thoát: `0` ok · `1` lỗi chung · `2` sai cú pháp · `3` handoff không hợp lệ · `4` không tìm thấy/mơ hồ · `5` không phải git repo.
6. Không traceback cho lỗi đã lường trước; lỗi khác in `internal error: <type>: <msg>` và gợi ý `CAIRN_DEBUG=1`.
7. Thông điệp dạng `cairn: <msg>` và `cairn: warning: <msg>`.
8. Màu ANSI chỉ khi TTY và không có `NO_COLOR`.
9. Thời gian lưu là UTC.

### R18. Nền tảng và đóng gói

1. Runtime chỉ dùng Python stdlib, Python ≥ 3.9 (khớp `python3` có sẵn trên macOS qua Xcode CLT). `[M1]`
2. Chạy trên macOS 13+ và Linux. `[M1]`
3. Phụ thuộc ngoài: `git` ≥ 2.31 (bắt buộc), `gh` (tuỳ chọn). `[M1]`
4. Subprocess dùng danh sách đối số, không `shell=True`, có timeout (git 10 giây, gh 5 giây, trong hook git 2 giây). `[M1]`
5. Layout `src/agent_cairn/`, chạy được bằng `python3 -m agent_cairn` khi `src/` ở `PYTHONPATH`. `[M1]`
6. `pyproject.toml` khai báo package `agent-cairn`, entry point `cairn = agent_cairn.cli:main`; cài được bằng `pipx install agent-cairn` và `uv tool install agent-cairn`. `[M2]`
7. Không build step: mã trong plugin chính là mã trong `src/`. `[M1]`
8. Launcher `bin/cairn` PHẢI chạy đúng khi được gọi qua symlink (npm `node_modules/.bin`, link trên `PATH`). `[M2]`
9. Repo PHẢI có `package.json` (gói `agent-cairn`, `bin: cairn → bin/cairn`, version đồng bộ từ `__version__` qua `gen_plugin.py`) để chạy `npx github:sdc-ren/cairn …` không cần publish; đăng npm registry là tuỳ chọn khi phát hành. `[M2]`

### R19. Hiệu năng `[M1]`

1. `template`, `list`, `show`, `version` ≤ 300 ms với Store ≤ 500 handoff.
2. `capture`, `save`, `resume` (không tính `gh`) ≤ 1,5 giây với ≤ 10 worktree.

### R20. Chất lượng mã `[M1]`

1. Mã PHẢI tuân thủ [CODING_STANDARDS](../CODING_STANDARDS.md); mọi kiểm tra tự động trong §9 của tài liệu đó chạy trong CI và PHẢI xanh.
2. Mọi tiêu chí M1 PHẢI có test gắn `@pytest.mark.req("Rn.m")`, trừ tiêu chí `[manual]` phải có mục tương ứng trong `verification.md`; `scripts/req_coverage.py` kiểm cả hai và chặn CI khi thiếu.
3. Test lệnh `capture`, `save`, `resume`, drift, hook chạy trên git repo tạm thật.
4. Coverage dòng ≥ 85%, nhánh ≥ 75%.
5. CI chạy macOS + Ubuntu × Python 3.9 và 3.13.

### R21. Kênh cho agent khác `[M2]`

1. `cairn init` cài skill `cairn-handoff`, `cairn-resume` (tên có tiền tố để không trùng skill khác khi không có namespace của plugin) vào `.claude/skills/` của Dự án hoặc `~/.claude/skills/` (`--global`) cho người không dùng plugin; file có marker `<!-- managed-by: cairn v<version> -->`; không ghi đè file thiếu marker trừ khi `--force` (sao lưu `.bak`); `--dry-run` chỉ in việc sẽ làm.
2. `cairn init --agent agents-md` thêm/cập nhật khối giữa `<!-- cairn:begin -->` và `<!-- cairn:end -->` trong `AGENTS.md`.
3. `cairn prompt handoff|resume` in chỉ dẫn để paste vào agent bất kỳ: chính thân skill, với phần chỉ Claude Code hiểu (`${CLAUDE_PROJECT_DIR}`, `${CLAUDE_SESSION_ID}`, dòng `ARGUMENTS:`) được thay bằng cách nói chung.
4. `cairn init --uninstall` gỡ mọi thứ có marker.
5. Mọi văn bản ở R21.1–R21.3 PHẢI sinh từ cùng Asset với plugin (R11.7).
6. Publish PyPI `agent-cairn` qua workflow `release.yml` (Trusted Publishing, chạy khi gắn tag `v*`). `[manual]`

### R22. Ngôn ngữ `[M1]`

1. Mọi văn bản agent đọc — skill (`description`, nội dung), template, preamble, Captured state, Drift, thông điệp CLI — PHẢI bằng tiếng Anh.
2. `description` của skill PHẢI đặt use case chính lên đầu, nêu khi nào dùng, và liệt kê cụm kích hoạt tiếng Việt lẫn tiếng Anh (R16.4–R16.5); tổng `description` + `when_to_use` ≤ 1 000 ký tự (giới hạn hiển thị của Claude Code là 1 536).
3. Skill PHẢI yêu cầu agent **viết handoff bằng tiếng Anh** nhưng **trả lời người dùng bằng ngôn ngữ người dùng đang dùng**.
4. Tài liệu spec, CODING_STANDARDS bằng tiếng Việt; README phát hành bằng tiếng Anh. `[manual]`

### R23. Nhắc lưu trước khi mất ngữ cảnh `[M1]`

**User story:** Là Dev, tôi hay quên gõ `/cairn:handoff` trước khi ngữ cảnh bị nén; tôi muốn được giữ lại phần lý luận và được nhắc đúng lúc.

Bối cảnh: Claude Code không có hook cho "sắp hết quota" hay "ngữ cảnh vượt ngưỡng"; điểm can thiệp gần nhất là compaction (`PreCompact`, `SessionStart` nguồn `compact`). Hết quota đột ngột chỉ được che bằng R16.4 (người dùng nói ý định).

1. Plugin PHẢI đăng ký hook `PreCompact` (matcher `manual|auto`) gọi `cairn hook pre-compact`.
2. `cairn hook pre-compact` PHẢI in ra stdout chỉ dẫn bằng tiếng Anh cho bản tóm tắt compaction (Claude Code dùng stdout của `PreCompact` làm chỉ dẫn tóm tắt): giữ nguyên mục tiêu, quyết định kèm lý do, hướng đã thử thất bại kèm lý do, bước tiếp theo, câu hỏi mở, file chính. Nội dung lấy từ Asset `precompact.md`.
3. `hook pre-compact` KHÔNG ĐƯỢC chặn compaction (không exit 2, không `decision: block`).
4. Plugin PHẢI đăng ký `SessionStart` matcher `compact` gọi `cairn hook post-compact`.
5. KHI Dự án không có handoff nào tạo trong khoảng `CAIRN_NUDGE_WINDOW` (mặc định `2h`), THÌ `hook post-compact` PHẢI in JSON `{"systemMessage": …}` một dòng ≤ 200 ký tự (Asset `nudge.md`) nhắc người dùng có thể gõ `/cairn:handoff`; ngược lại không in gì. Dùng `systemMessage` vì nó hiện ngay cho người dùng, còn `additionalContext` chỉ tới tay agent ở lượt trả lời kế tiếp (kiểm thật 2026-11-09).
6. Lời nhắc chỉ dành cho người dùng; cairn KHÔNG ĐƯỢC khiến agent tự lưu handoff.
7. `CAIRN_NUDGE=off` tắt cả hai hook. R13.6, R13.7 áp dụng cho cả hai.
8. KHI kiểm thực tế (task E5) cho thấy Claude Code không gọi hook của plugin ở hai sự kiện này, THÌ R23 chuyển sang M2, ghi lý do vào `verification.md`. `[manual]`

### R24. Đo chất lượng handoff `[M1]`

**User story:** Là Dev, tôi muốn biết handoff có thật sự giúp phiên mới làm tiếp đúng việc, không chỉ "cảm thấy ổn".

1. Repo PHẢI có kịch bản chuẩn `docs/specs/eval/scenario.md`: một phiên mẫu (repo mẫu dựng bằng `scripts/eval_setup.sh`, kèm lời thoại cần đưa cho agent), và rubric `eval/rubric.json` gồm ≥ 8 sự kiện bắt buộc: mục tiêu, 2 quyết định kèm lý do, 1 hướng thất bại kèm lý do, 3 bước tiếp theo, 1 câu hỏi mở; mỗi sự kiện có một hoặc nhiều regex.
2. `scripts/eval_check.py <handoff-file>` PHẢI in điểm `k/n` và tên các sự kiện thiếu; mã 1 khi `k` dưới ngưỡng (mặc định 7/8).
3. `verification.md` PHẢI có nhật ký dùng thật, mỗi lần resume một dòng: ngày, ID, nguồn (`hook`/`skill`), số lần người dùng phải giải thích lại, bước đầu tiên agent đề xuất có đúng không (`Y`/`N`), thông tin bị thiếu, hook có gây phiền không. `[manual]`
4. Ngưỡng đạt MVP: kịch bản chuẩn đạt ≥ 7/8 trong 3 lần chạy liên tiếp; nhật ký ≥ 10 lần resume với ≥ 80% bước đầu đúng và trung bình ≤ 1 lần giải thích lại. `[manual]`

## 9. Definition of Done

### M0 — bộ khung 0.0.1

- Tiêu chí M0 có test xanh khi chạy `pytest` trên máy (chưa cần CI).
- Cài plugin từ thư mục local; chạy được S1 trên máy thật, không gõ lệnh terminal nào sau khi cài.
- Dùng thật ≥ 3 ngày, nhật ký R24.3 có ≥ 5 dòng; điều chỉnh spec theo những gì học được **trước khi** bắt đầu phần M1 còn lại.

### M1 — MVP 0.1

- Mọi tiêu chí M1 có test xanh trên CI.
- Cài plugin từ thư mục local trên máy thật; chạy S1 với hai tài khoản Claude Code và S2, S3; ghi bằng chứng vào `docs/specs/verification.md`.
- Đạt ngưỡng R24.4.
- Dùng thật ít nhất 5 ngày làm việc; ghi lại các lần handoff bị thiếu ý hoặc hook gây phiền để quyết định phạm vi 0.2.

## 10. Câu hỏi mở

Không còn câu hỏi chặn. Các quyết định đã chốt nằm ở [design.md §2](design.md#2-quyết-định-thiết-kế).
