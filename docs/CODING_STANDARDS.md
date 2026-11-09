# Coding Standards

Áp dụng cho mọi mã trong repo `cairn`. Mỗi quy tắc có ID `CS-n` để review và commit có thể trích dẫn. Quy tắc nào máy kiểm được thì **phải** do máy kiểm (cột "Kiểm bằng"); review của người chỉ dành cho phần máy không bắt được.

## 1. Nguyên tắc

| ID | Quy tắc | Kiểm bằng |
|---|---|---|
| CS-1 | **Lõi thuần, vỏ I/O.** Logic (parse, validate, render, tính drift, chọn handoff) là hàm thuần nhận dữ liệu, trả dữ liệu. Chỉ các module vỏ (`proc`, `gitio`, `gh`, `store`, `clipboard`, `cli`, `hook`) được chạm vào subprocess, filesystem, stdin/stdout, đồng hồ. | Review + test tĩnh import (CS-30) |
| CS-2 | **Một nguồn sự thật cho mỗi thứ.** Xem bảng §2. Thấy mình viết lại thứ đã có trong bảng → dùng lại, không viết bản thứ hai. | Review + `pylint duplicate-code` |
| CS-3 | **Không trừu tượng hoá trước.** Chỉ tách helper/lớp chung khi logic lặp lại lần thứ hai và dài > 3 dòng. Không base class, plugin registry, config framework khi chỉ có một cách dùng. | Review |
| CS-4 | **Đọc code là hiểu luồng.** Ưu tiên hàm ngắn có tên rõ hơn comment giải thích. Không metaprogramming, không decorator tự chế trừ `@dataclass`, `@pytest.*`. | Review |
| CS-5 | **Không mã chết.** Không code comment-out, không hàm/biến không dùng, không cờ "để sau dùng". | ruff `ERA`, `F401`, `F841`; `vulture` |

## 2. Một nguồn sự thật (CS-2)

| Thứ | Chỉ được nằm ở | Cấm |
|---|---|---|
| Gọi tiến trình ngoài | `proc.run()` | `import subprocess` ở module khác |
| Lệnh git | `gitio.py` (mỗi lệnh một hàm) | Ghép argv git ở nơi khác |
| Ghi ra stdout/stderr | `out.py`: `emit()` (stdout), `note()`, `warn()`, `detail()` (stderr) | `print()` ở module khác |
| Đường dẫn Store, tên file, ID | `store.py` | Tự ghép `"handoffs/" + …` |
| Thời gian hiện tại | `timeutil.now_utc()` | `datetime.now()` ở nơi khác |
| Văn bản cho agent (template, prompt, skill, preamble) | `assets/*.md` | Chuỗi nhiều dòng trong `.py` |
| Hằng số (giới hạn, timeout, tên section) | `constants.py` | Số "ma thuật" trong code |
| Ánh xạ lỗi → exit code | Thuộc tính `exit_code` trên lớp lỗi trong `errors.py` | `sys.exit(<số>)` ngoài `cli.main` |
| Định dạng frontmatter/section | `document.py` | Regex parse markdown ở nơi khác |

## 3. Kích thước và độ phức tạp

| ID | Giới hạn | Kiểm bằng |
|---|---|---|
| CS-10 | Hàm ≤ 40 câu lệnh; ≤ 12 nhánh; độ phức tạp McCabe ≤ 10 | ruff `PLR0915`, `PLR0912`, `C901` |
| CS-11 | ≤ 5 tham số; tham số thứ 3 trở đi là keyword-only (`*`) | ruff `PLR0913` + review |
| CS-12 | Không tham số boolean vị trí (`f(x, True)`) | ruff `FBT` |
| CS-13 | Module ≤ 300 dòng (không tính docstring/blank); vượt thì tách theo trách nhiệm | script `scripts/check_sizes.py` trong CI |
| CS-14 | Lồng ≤ 3 mức; dùng return sớm thay vì `else` sau `return` | ruff `RET505`, `SIM` + review |

## 4. Kiểu, tên, tài liệu

| ID | Quy tắc | Kiểm bằng |
|---|---|---|
| CS-20 | `mypy --strict` sạch. `Any` chỉ được ở biên JSON, và phải chuyển ngay sang `TypedDict`/dataclass | mypy |
| CS-21 | Dữ liệu là `@dataclass(frozen=True, slots=True)` (3.10+) hoặc `frozen=True` (3.9). Không dict "túi đồ" đi qua nhiều module | Review |
| CS-22 | Tên hàm là động từ (`collect_worktrees`), dữ liệu là danh từ (`WorktreeState`), exception có hậu tố `Error` (`NotFoundError`). Viết tắt chỉ được: `git`, `gh`, `id`, `cwd`, `sha`, `pr`, `json` | ruff `N` + review |
| CS-23 | Mọi hàm/lớp public có docstring một dòng nói **làm gì**; thêm đoạn chỉ khi có điều không hiển nhiên (ràng buộc, lý do) | ruff `D1`, `D2`, `D4` (google) |
| CS-24 | Comment giải thích **vì sao**, không lặp lại code làm gì | Review |
| CS-25 | `pathlib.Path` cho mọi đường dẫn | ruff `PTH` |
| CS-26 | Mọi văn bản mà agent hoặc người dùng CLI đọc là tiếng Anh; tài liệu spec là tiếng Việt | Review |

## 5. Lỗi

| ID | Quy tắc | Kiểm bằng |
|---|---|---|
| CS-27 | Lỗi đã lường trước → raise lớp con của `CairnError`. Không trả `None`/`False` để báo lỗi | Review |
| CS-28 | Cấm `except:` trần và `except Exception` — trừ đúng hai chỗ: `cli.main()` và `hook.session_start()` | ruff `E722`, `BLE001` (per-file-ignore 2 file) |
| CS-29 | Không nuốt lỗi im lặng: mọi `except` phải raise lại, chuyển kiểu, hoặc ghi vào trường `errors` có chủ đích | ruff `S110`, `SIM105` + review |

## 6. Phụ thuộc và bảo mật

| ID | Quy tắc | Kiểm bằng |
|---|---|---|
| CS-30 | `src/` chỉ import stdlib và chính package; không import vòng; hướng phụ thuộc theo design §3 | test `test_imports.py` (dựng đồ thị import bằng `ast`) |
| CS-31 | Không `shell=True`; mọi `proc.run` có `timeout` | ruff `S602`, `S604` + test tĩnh |
| CS-32 | Không log/in giá trị người dùng có thể là secret (nội dung body, output gh) trong thông điệp lỗi | Review + test secrets |

## 7. Test

| ID | Quy tắc | Kiểm bằng |
|---|---|---|
| CS-40 | Mỗi test kiểm **một** hành vi, tên dạng `test_<đơn vị>_<tình huống>_<kết quả>` | Review |
| CS-41 | Cấu trúc Arrange / Act / Assert, ngăn bằng dòng trống | Review |
| CS-42 | Gắn `@pytest.mark.req("Rn.m")` cho test kiểm tiêu chí requirement | `scripts/req_coverage.py` |
| CS-43 | Không mock git — dùng repo tạm thật qua fixture. Chỉ giả `gh` và clipboard bằng script trên `PATH` | Review |
| CS-44 | Không `time.sleep`, không mạng, không đọc `$HOME` thật; đồng hồ được inject | Fixture tự động cô lập env (autouse) |
| CS-45 | Dữ liệu dùng chung qua fixture/factory trong `conftest.py`, không copy-paste khối setup | `pylint duplicate-code` chạy cả trên `tests/` |
| CS-46 | Output dài so bằng golden file, không assert chuỗi dài inline | Review |
| CS-47 | Coverage dòng ≥ 85%, nhánh ≥ 75% | `pytest-cov` trong CI |

## 8. Git và review

| ID | Quy tắc |
|---|---|
| CS-50 | Commit theo Conventional Commits: `feat(store): atomic write`, `fix(drift): …`, `test:`, `docs:`, `refactor:`, `chore:`. |
| CS-51 | Mỗi PR làm đúng một task trong `tasks.md`, ghi ID task trong tiêu đề, diff ≤ 400 dòng (không tính golden/test data). |
| CS-52 | PR đổi hành vi phải cập nhật requirement/design trước hoặc trong cùng PR. |
| CS-53 | Checklist review: (1) có vi phạm bảng §2 không, (2) có hàm nào cần tách không, (3) test có kiểm hành vi chứ không kiểm chi tiết cài đặt không, (4) thông điệp lỗi có hướng dẫn người dùng làm gì tiếp không. |

## 9. Cấu hình công cụ

`pyproject.toml` (trích):

```toml
[tool.ruff]
line-length = 100
target-version = "py39"
extend-exclude = ["docs"]     # khối code trong spec là minh hoạ, không phải mã chạy

[tool.ruff.lint]
select = ["E", "W", "F", "I", "N", "D", "UP", "B", "SIM", "C4", "C90", "PL", "RUF",
          "T20", "PTH", "ERA", "RET", "ARG", "FBT", "BLE", "S", "TRY"]
ignore = ["D203", "D213", "TRY003"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5
max-branches = 12
max-statements = 40

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.lint.per-file-ignores]
"src/agent_cairn/proc.py" = ["S603", "S607"]      # nơi duy nhất gọi subprocess
"src/agent_cairn/out.py" = ["T201"]               # nơi duy nhất print
"src/agent_cairn/cli.py" = ["BLE001"]
"src/agent_cairn/hook.py" = ["BLE001"]
"tests/**" = ["D", "S101", "S603", "S607", "PLR2004", "ARG001"]   # test được gọi git/python trực tiếp

[tool.mypy]
strict = true
python_version = "3.9"

[tool.pylint.similarities]
min-similarity-lines = 6
ignore-comments = true
ignore-docstrings = true
ignore-imports = true
```

Lệnh trong CI (`make lint`):

```bash
ruff check . && ruff format --check . && mypy src
pylint --disable=all --enable=duplicate-code src tests
vulture src --min-confidence 80
python scripts/check_sizes.py --max-module-lines 300
```

`pylint` và `vulture` chỉ là dev dependency, không ảnh hưởng ràng buộc stdlib-only lúc chạy.
