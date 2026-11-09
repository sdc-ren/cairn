# Spec — cairn v1 (Agent Handoff)

**Một câu:** agent sắp dừng tự viết lý do (mục tiêu, quyết định, việc đã thử, bước tiếp theo), CLI gắn dữ kiện git và kiểm tra cấu trúc; phiên mới tự nhận lại kèm báo cáo những gì đã đổi kể từ đó.

Trải nghiệm người dùng: [requirements §2](requirements.md#2-giải-pháp-tóm-tắt). Phạm vi từng mốc: [requirements §6](requirements.md#6-quy-ước).

## Tài liệu

| File | Trả lời câu hỏi |
|---|---|
| [requirements.md](requirements.md) | Làm **gì**, cho **ai**, thế nào là **đúng**: tiêu chí EARS, ID `Rn.m`, mức M0/M1/M2. |
| [design.md](design.md) | Làm **thế nào** và **vì sao**: quyết định D-n, cấu trúc repo/plugin, định dạng file, luồng, bảo mật, test. |
| [tasks.md](tasks.md) | Làm **theo thứ tự nào**: task K (M0), A–F, P (M1), G (M2); mỗi task có Done khi + Refs. |
| `verification.md` | Bằng chứng kiểm trên Claude Code thật và nhật ký dùng thật (tạo ở task K6). |
| `eval/` | Kịch bản chuẩn và rubric chấm handoff (tạo ở task F3). |
| [../CODING_STANDARDS.md](../CODING_STANDARDS.md) | Chuẩn mã CS-n và công cụ kiểm tự động. |

## Quy tắc

1. **Thứ tự:** requirements → design → tasks; viết và duyệt theo thứ tự đó.
2. **Requirement là nguồn sự thật.** Code hoặc design lệch requirement thì sửa requirement trước (kèm lý do), rồi mới sửa code.
3. **Truy vết hai chiều.** Mỗi task ghi `Refs: Rn.m`; mỗi test gắn `@pytest.mark.req("Rn.m")`; tiêu chí `[manual]` có bằng chứng trong `verification.md`; CI chặn khi tiêu chí M1 thiếu cả hai.
4. **Mỗi thông tin ghi một chỗ.** Tài liệu khác chỉ link tới, không chép lại.
5. **Trạng thái và phiên bản** ghi ở bảng đầu `requirements.md`: `Draft` → `Approved` → `Implemented`. Spec cũ không giữ trong `docs/`; lịch sử nằm trong git.
