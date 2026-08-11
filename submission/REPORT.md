# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100 (xem `submission/evidence/checkpoint2_validators.txt`)
- Tổng số traces: ≥14 traces trên Langfuse (10 từ `load_test.py --concurrency 5`, 2 so sánh baseline/candidate, 1 sau khi đổi label production, 1 sau khi rollback)
- Số PII leak còn lại: 0 (email, số điện thoại VN, số thẻ đều được redact — kiểm chứng bằng `scripts/validate_logs.py` dùng `app.pii.PII_PATTERNS`)
- Link/đường dẫn dashboard: chạy local bằng `streamlit run scripts/dashboard.py` → http://localhost:8502 (đọc trực tiếp `data/logs.jsonl` theo contract `config/dashboard.yaml`)

## 3. Logging và tracing

- Evidence correlation ID: mỗi request có header `x-request-id` dạng `req-<8-hex>` (sinh trong `app/middleware.py`) và field `correlation_id` tương ứng trong `data/logs.jsonl`
- Evidence PII redaction: `submission/evidence/checkpoint2_validators.txt` — 0 leak trên 82 log record; ví dụ `payload.message_preview` chứa `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`
- Evidence trace waterfall: https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/193ba6669f2eeca2ae1426476be5e12d
- Giải thích một span đáng chú ý: generation span của `LabAgent.run` ghi metadata `prompt_name=day13-chat`, `prompt_label`, `prompt_version`, `prompt_source`, cùng usage/cost — dùng để đối chiếu prompt nào tạo ra câu trả lời nào

## 4. Prompt versioning

- Prompt name: `day13-chat`
- Version/label baseline: v1 — labels `baseline`, `production` (ban đầu)
- Version/label candidate: v2 — label `candidate` (thêm chỉ dẫn "trả lời tối đa 2 câu ngắn")
- Trace ID của mỗi version:
  - baseline/v1: `193ba6669f2eeca2ae1426476be5e12d` — https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/193ba6669f2eeca2ae1426476be5e12d
  - candidate/v2: `ca8f55cde03e50ece4e9b7d9f77f9b88` — https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/ca8f55cde03e50ece4e9b7d9f77f9b88
- Bằng chứng đổi label hoặc rollback:
  - Đổi `production` → v2: trace `a561838091f5001179fa102378ec1ae7` — https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/a561838091f5001179fa102378ec1ae7
  - Rollback `production` → v1: trace `19d9a211e2ddaf488c9ed0e231a0d09b` — https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/19d9a211e2ddaf488c9ed0e231a0d09b

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: HỢP LỆ — 6/6 panel đúng contract (xem `submission/evidence/checkpoint2_validators.txt`)
- Evidence dashboard: `submission/evidence/checkpoint2_dashboard.png` (chụp lúc chạy `streamlit run scripts/dashboard.py`, có đủ 6 panel + badge SLO PASS/FAIL)
- SLO đã chọn và lý do: giữ nguyên threshold trong `config/dashboard.yaml` — latency P95 ≤ 3000ms, traffic ≥ 1 req/phút, error rate ≤ 2%, cost ≤ 2.5 USD/cửa sổ, tokens ≤ 50000, quality mean ≥ 0.75 (theo đúng contract chấm điểm, không tự đổi)
- Alert rules và runbook: xem `config/alert_rules.yaml` và `docs/alerts.md` (chưa test runtime trong buổi này)

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |
