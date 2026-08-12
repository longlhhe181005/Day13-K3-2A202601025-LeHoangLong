# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm `validate_logs.py`: 100/100 (xem `submission/evidence/checkpoint2_validators.txt`)
- Tổng số traces: ≥14 traces trên Langfuse (10 từ `load_test.py --concurrency 5`, 2 so sánh baseline/candidate, 1 sau khi đổi label production, 1 sau khi rollback). Ảnh danh sách: `submission/evidence/checkpoint2_trace_waterfall.png` (bảng Tracing, Total ≈108 observation, filter Name: run=84, llm_call=12, retrieve_docs=12)
- Số PII leak còn lại: 0 (email, số điện thoại VN, số thẻ đều được redact — kiểm chứng bằng `scripts/validate_logs.py` dùng `app.pii.PII_PATTERNS`)
- Link/đường dẫn dashboard: chạy local bằng `streamlit run scripts/dashboard.py` → http://localhost:8502 (đọc trực tiếp `data/logs.jsonl` theo contract `config/dashboard.yaml`)

## 3. Logging và tracing

- Evidence correlation ID: mỗi request có header `x-request-id` dạng `req-<8-hex>` (sinh trong `app/middleware.py`) và field `correlation_id` tương ứng trong `data/logs.jsonl`
- Evidence PII redaction: `submission/evidence/checkpoint2_validators.txt` — 0 leak trên 82 log record; ví dụ `payload.message_preview` chứa `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`
- Evidence trace waterfall: `submission/evidence/checkpoint3_trace_waterfall.PNG` (trace `f725566f4de3f74e425422e0c4083e47` — cây `run` → span con `retrieve_docs` + `llm_call`, xem chi tiết root cause ở mục 6) — https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/193ba6669f2eeca2ae1426476be5e12d
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

- Challenge ID: `day13-k3-observability-v1` (cohort K3, incident chính thức: `rag_slow`, feature bị ảnh hưởng: `refund`, `latency_threshold_ms=2000`)
- Triệu chứng từ metrics: `GET /metrics` trong lúc incident bật cho thấy `latency_p95` nhảy từ baseline ~157ms lên **2653ms** (vượt threshold 2000ms của challenge), trong khi `error_breakdown={}` và `quality_avg` không đổi → khoanh vùng đây là sự cố latency thuần túy, không phải lỗi hay cost. Xem `submission/evidence/checkpoint3_dashboard_incident.png` (panel Latency percentiles tăng vọt từ ~157ms lên 2653ms).
- Trace ID liên quan: `f725566f4de3f74e425422e0c4083e47` — https://jp.cloud.langfuse.com/project/cmso2iqfp003uad0iesi6ljh6/traces/f725566f4de3f74e425422e0c4083e47
  - Ảnh waterfall: `submission/evidence/checkpoint3_trace_waterfall.PNG`
  - Waterfall: `run` (2.66s tổng) → span con `retrieve_docs` (**2.507s**, ~94% tổng thời gian) + span con `llm_call` (0.153s, đúng baseline bình thường) → span bất thường là `retrieve_docs`.
- Log line/correlation ID liên quan (cùng session `k3-challenge-s03`, cùng câu hỏi, khác trạng thái incident):
  - Baseline: `correlation_id=req-9f54dd0c`, `latency_ms=151`
  - Lúc có incident: `correlation_id=req-b3ea75a5`, `latency_ms=2653`, timestamp `request_received` khớp chính xác với thời điểm bắt đầu trace ở trên
- Root cause: `app/mock_rag.py:retrieve()` có `time.sleep(2.5)` khi `STATE["rag_slow"]` bật (do `scripts/inject_incident.py` gọi `POST /incidents/rag_slow/enable` theo đúng `config/challenge.json`). Đây là nguyên nhân duy nhất của độ trễ — không liên quan tới prompt fetch hay LLM generation (đã tách riêng span để loại trừ).
- Fix action: tắt incident bằng `python scripts/inject_incident.py --disable` (đã xác nhận latency về lại 151ms). Trong tình huống thật, cần thêm timeout + fallback cho bước retrieve (vd trả corpus rỗng/cached kèm cảnh báo) thay vì để request treo hết thời gian chờ vector store.
- Preventive measure: thêm alert riêng cho `retrieve_docs` span duration (không chỉ tổng latency) để phát hiện sớm tầng nào chậm; đặt timeout cứng cho lệnh gọi vector store; thêm circuit breaker/fallback corpus khi vector store timeout, tránh lặp lại kiểu lỗi `tool_fail` (raise ngay) hay `rag_slow` (treo) ảnh hưởng toàn bộ pipeline.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| | | | |
