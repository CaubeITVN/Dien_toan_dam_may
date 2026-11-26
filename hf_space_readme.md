---
title: Tra cuu & Hoi dap Tai lieu Luu tru So hoa (Cloud-Native RAG)
emoji: ☁️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Hệ thống Lưu trữ Số hóa, Tra cứu Lai và Hỏi đáp RAG (Cloud-Native)

Ứng dụng Web Cloud-Native tách biệt tầng tính toán phi trạng thái (Docker Container trên Hugging Face Spaces) khỏi tầng lưu trữ đối tượng bền vững (Hugging Face Private Dataset) và tầng suy luận mô hình ngôn ngữ đám mây (OpenRouter API).

## Biến môi trường & Bí mật (Space Secrets)
- `HF_STORAGE_REPO`: Tên kho Hugging Face Dataset riêng tư lưu trữ trạng thái Phông–Hồ sơ, PDF tải lên, cache OCR và kho PDF gốc.
- `HF_TOKEN`: Token truy cập (Read/Write) tới `HF_STORAGE_REPO`.
- `OPENROUTER_API_KEY`: Khóa API OpenRouter để trả lời RAG.
- `OPENROUTER_MODEL`: Mô hình mặc định (ví dụ `google/gemini-2.0-flash-001`).
- `APP_ADMIN_PASSWORD`: Mật khẩu quản trị cho tài khoản `admin`.
- `APP_SECRET_KEY`: Khóa ký token phiên đăng nhập phi trạng thái `HMAC-SHA256`.
