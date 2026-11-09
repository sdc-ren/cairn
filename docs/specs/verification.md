# Verification — cairn

Bằng chứng kiểm trên máy thật cho các tiêu chí không tự động hoá được (`[manual]`) và nhật ký dùng thật (R24.3). Mỗi mục ghi ngày, phiên bản Claude Code, kết quả.

## K5 — plugin trên Claude Code

Môi trường: macOS 14 (Darwin 23.6), Claude Code 2.1.296, Python hệ thống 3.9.6.

### Đã kiểm tự động (2026-11-09)

| Kiểm | Kết quả |
|---|---|
| `claude plugin validate --strict .` (marketplace + plugin) | Passed |
| `claude plugin validate --strict skills` | Passed |
| Tài liệu plugins-reference: `bin/` nằm trên `PATH` của Bash tool khi plugin bật | Xác nhận trong tài liệu |
| Tài liệu hooks: dạng exec `command` + `args`, `${CLAUDE_PLUGIN_ROOT}` được thay trong cả hai | Xác nhận trong tài liệu |
| Tài liệu skills: `allowed-tools` dạng `Bash(cairn save *)`; có đối số mà body không dùng placeholder thì Claude Code nối `ARGUMENTS: <value>` | Xác nhận trong tài liệu; skill dùng cách này thay cho `$ARGUMENTS` |
| `bin/cairn` chạy package, bỏ qua `PYTHONPATH` người dùng, báo lỗi khi Python < 3.9 | `tests/test_plugin.py` |
| Template trong skill để nguyên → `save` từ chối, mã 3 | Chạy tay qua `bin/cairn` |
| Hook qua `bin/cairn` với JSON giống Claude Code, Store rỗng → stdout rỗng, mã 0 | Chạy tay |

Không chạy được `claude -p` để thử tự động: tổ chức đã tắt quyền dùng subscription cho Claude Code CLI (`Your organization has disabled Claude subscription access for Claude Code`). Các mục dưới cần người dùng chạy trong phiên Claude Code thật.

### Cần kiểm tay

Cài (một lần, từ thư mục repo):

```bash
claude plugin marketplace add /path/to/cairn
claude plugin install cairn@sdc-ren
```

Rồi mở một phiên Claude Code mới trong thư mục làm việc (git repo hoặc workspace chứa nhiều repo). Handoff lưu ở `~/.cairn/<dự-án>-<hash>/<id>.md`; nhờ agent chạy `cairn show --path` để thấy file đang được chọn.

| # | Bước | Mong đợi | Kết quả |
|---|---|---|---|
| 1 | Trao đổi vài câu về một việc, rồi gõ `/cairn:handoff` | Agent chạy `cairn save` **không hỏi quyền** (allowed-tools khớp lệnh heredoc), trả lời ≤ 2 dòng có ID | 2026-11-09, Claude Code 2.1.296, workspace nhiều repo (không phải git): lưu `20261109-100105-proj-274` vào `~/.cairn/my-workspace-1a2b3c4d/` với `task: PROJ-274`, `session_id`, Workspace 3 worktree + 1 pipeline được chụp đúng (branch, HEAD, số file chưa commit). Không hỏi quyền: `allowed-tools: Bash(cairn save *)` khớp cả lệnh có heredoc (người dùng xác nhận). |
| 2 | Gõ `/cairn:handoff Tên thử` | Title của handoff là "Tên thử" (dòng `ARGUMENTS:`) | |
| 3 | Nói "sắp hết quota, lưu ngữ cảnh giúp tôi" (không gõ lệnh) | Skill handoff tự kích hoạt (R16.4) | |
| 4 | `/clear` hoặc mở phiên mới cùng repo, gõ "chào" | Agent tóm tắt mục tiêu, việc đã xong, bước tiếp theo từ handoff, chờ xác nhận (hook `startup\|clear` chạy, R16.6) | 2026-11-09: phiên mới ở workspace đó, gõ "Tiếp tục PROJ-274"; hook dạng exec chạy: PROJ-274 chuyển `resumed` lúc 10:08:43Z (`resume_count: 1`), PROJ-268 giữ `open` (R13.9). Người dùng xác nhận agent tóm tắt đúng PROJ-274 và nhắc PROJ-268 đang mở (R16.6). |
| 5 | Mở phiên mới lần nữa | Không chèn lại (handoff đã `resumed`) | |
| 6 | Nói "làm tiếp việc hôm qua" | Skill resume tự kích hoạt, đọc file handoff mới nhất của branch (R16.5) | |
| 7 | Toàn bộ 1–6 | Không phải gõ lệnh nào trong terminal sau khi cài (R16.7) | |

Nếu bước 1 bị hỏi quyền: ghi lại nguyên văn lệnh agent chạy; cần đổi `allowed-tools` (design §7.4). Nếu bước 4 không có gì: chạy `claude --debug` và tìm `SessionStart`; nếu hook dạng exec không chạy, đổi sang dạng chuỗi (design §7.3).

## M1 — việc cần kiểm tay

| Tiêu chí / task | Cách kiểm | Kết quả |
|---|---|---|
| R22.4 ngôn ngữ tài liệu | Spec và CODING_STANDARDS viết tiếng Việt; README, CHANGELOG, CONTRIBUTING, SECURITY tiếng Anh. | Đạt, 2026-11-09 |
| R11.2 cài từ GitHub (P4) | Trên máy chưa cài: `claude plugin marketplace add sdc-ren/cairn`, `claude plugin install cairn@sdc-ren`, mở phiên mới. | Chờ |
| R23.8 hook nén ngữ cảnh (E5) | Trong phiên có plugin, chạy `/compact`: bản tóm tắt giữ mục tiêu, quyết định, việc thất bại, bước tiếp theo; nếu chưa có handoff trong 2 giờ, người dùng thấy một dòng nhắc. | Đạt, 2026-11-09: `PreCompact` chạy dạng exec, chỉ dẫn được dùng cho bản tóm tắt (handoff viết sau khi nén đạt 8/8, `/tmp/cairn-eval`). Lời nhắc qua `additionalContext` không hiện vì chỉ tới agent ở lượt sau; chuyển sang `systemMessage` và thử lại ở `/tmp/cairn-eval2`: dòng nhắc hiện ngay sau `/compact`. Hook không chặn compaction nên R23 giữ ở M1. |
| R24.4 chất lượng (F3, F2) | Chạy kịch bản [eval/scenario.md](eval/scenario.md) 3 lần, mỗi lần ≥ 7/8; nhật ký dưới ≥ 10 lần resume, ≥ 80% bước đầu đúng, trung bình ≤ 1 lần giải thích lại. | Chờ |
| P4 S1/S2/S3 | S1 hai tài khoản; S2 commit tay sau handoff rồi resume (drift báo commit mới); S3 hai worktree. | Chờ |

## M2 — việc cần kiểm tay

| Tiêu chí / task | Cách kiểm | Kết quả |
|---|---|---|
| R21.6 publish PyPI (G1) | Trên pypi.org thêm Trusted Publisher: repo `sdc-ren/cairn`, workflow `release.yml`, environment `pypi`; rồi `git tag v0.2.0 && git push --tags`; sau đó `pipx install cairn-handoff` trên máy khác. | Chờ |
| G9 S4 agent khác | Trong Codex/Cursor/…: `cairn init --agent agents-md` hoặc dán `cairn prompt handoff`, lưu handoff, rồi resume ở agent khác. | Chờ |

## F3 — kịch bản chuẩn

| Lần | Ngày | Điều kiện | Điểm | Ghi chú |
|---|---|---|---|---|
| 1 | 2026-11-09 | Sau `/compact` trong cùng phiên, repo `/tmp/cairn-eval` | 8/8 | Handoff `20261109-133719-main`; giữ đủ mục tiêu, lý do đặt logic trong `total()`, ROUND_HALF_UP, double-round đã bỏ, các bước tiếp theo, câu hỏi về thuế. |

## Nhật ký dùng thật (R24.3)

| Ngày | ID | Nguồn (hook/skill) | Số lần giải thích lại | Bước đầu đúng (Y/N) | Thiếu thông tin gì | Hook gây phiền? |
|---|---|---|---|---|---|---|
| 2026-11-09 | 20261109-100105-proj-274 | hook | 0 | Y | — | Không |
