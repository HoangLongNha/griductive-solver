## Mô tả

<!-- Nêu vấn đề cần giải quyết và hành vi sau thay đổi. Với lỗi, mô tả cách tái hiện và kết quả mong đợi. -->

## Task / Issue liên quan

<!-- Ví dụ: Closes #123 hoặc mã task trong docs/TASKS.md. -->

## Thay đổi chính

- 

## Kiểm tra

<!-- Ghi lệnh đã chạy và kết quả. Nếu chưa kiểm tra, ghi rõ lý do. -->

```bash
python -m pytest -q
```

<!-- Thêm các bước kiểm tra thủ công hoặc ảnh chụp nếu thay đổi giao diện. -->

## Checklist

- [ ] Đã kiểm tra các trường hợp liên quan đến thay đổi.
- [ ] Đã cập nhật tài liệu nếu API, schema hoặc hành vi thay đổi.
- [ ] Thay đổi tuân theo `docs/CONTRACTS.md`; đã nêu rõ nếu cần sửa contract.
- [ ] Nếu thay đổi solver: không dùng brute-force oracle trong code production.
- [ ] Nếu thay đổi GameEngine/agent: public snapshot không chứa thông tin bí mật.

## Lưu ý cho người review

<!-- Nêu rủi ro, giới hạn còn lại hoặc phần cần xem kỹ. Xóa mục này nếu không có. -->
