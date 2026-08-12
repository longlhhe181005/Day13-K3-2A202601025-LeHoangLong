# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: high_response_latency
- Severity: High
- SLI/SLO liên quan: `latency_p95_ms` (config/slo.yaml, objective ≤ 3000ms, target 99.5%) — panel `latency` trong config/dashboard.yaml
- Điều kiện và thời gian duy trì: `latency_p95_ms > 3000` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Câu trả lời chat mất hơn 3 giây, người dùng có thể timeout phía client hoặc bỏ chờ giữa chừng
- Ba bước kiểm tra đầu tiên:
  1. Xem `/metrics` hoặc dashboard xác nhận `latency_p95` hiện tại và mốc thời gian bắt đầu tăng
  2. Mở 1 trace chậm trong khoảng đó trên Langfuse, so sánh thời gian các span con (`retrieve_docs` vs `llm_call`) để khoanh vùng bước nào chậm
  3. Tra `data/logs.jsonl` theo cùng `correlation_id` để xác nhận `feature`/`model` liên quan, và request lỗi có xảy ra trên toàn bộ traffic hay chỉ 1 feature (vd `refund`)
- Mitigation tạm thời: Nếu span chậm là `retrieve_docs`, fallback sang corpus cached/rút gọn kèm cảnh báo thay vì chờ hết timeout; nếu do incident giả lập `rag_slow` đang bật nhầm trong môi trường test, tắt bằng `POST /incidents/rag_slow/disable`
- Owner: backend-oncall

## Alert 2

- Tên: elevated_error_rate
- Severity: Critical
- SLI/SLO liên quan: `error_rate_pct` (config/slo.yaml, objective ≤ 2%, target 99.0%) — panel `errors` trong config/dashboard.yaml
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` liên tục trong 5 phút (tối thiểu 5 request trong cửa sổ để tránh nhiễu do mẫu quá nhỏ)
- Ảnh hưởng tới người dùng: Request `/chat` trả về lỗi 500, người dùng không nhận được câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Xem `error_breakdown` trong `/metrics` hoặc panel Errors để biết `error_type` nào chiếm đa số
  2. Mở log `level=error` gần nhất trong `data/logs.jsonl`, đọc `payload.detail` (đã kèm `correlation_id`) để biết exception cụ thể
  3. Kiểm tra `/health` và trạng thái incident (đặc biệt `tool_fail`) xem có đang bật nhầm trong môi trường test không
- Mitigation tạm thời: Tắt incident nếu đang bật thử nghiệm (`POST /incidents/tool_fail/disable`); nếu là lỗi thật từ dependency ngoài (vector store timeout), bật fallback trả lời mặc định thay vì để request thất bại hoàn toàn
- Owner: backend-oncall

## Alert 3

- Tên: cost_spike
- Severity: Warning
- SLI/SLO liên quan: `daily_cost_usd` (config/slo.yaml, objective ≤ 2.5 USD/cửa sổ, target 100%) — panel `cost`/`tokens` trong config/dashboard.yaml
- Điều kiện và thời gian duy trì: tổng `cost_usd` trong cửa sổ trượt 60 phút vượt 2.5 USD, duy trì qua 2 lần đánh giá liên tiếp (tránh 1 request đơn lẻ gây false positive)
- Ảnh hưởng tới người dùng: không ảnh hưởng trực tiếp trải nghiệm ngay lập tức, nhưng có rủi ro vượt ngân sách vận hành nếu kéo dài
- Ba bước kiểm tra đầu tiên:
  1. Xem panel `tokens` (đặc biệt `tokens_out`) có tăng bất thường không, đối chiếu với thời điểm cost tăng
  2. Mở trace gần nhất trên Langfuse, xem `usage_details.completion_tokens` trong generation để xác nhận model đang trả lời dài bất thường
  3. Kiểm tra log `incident_enabled` gần nhất để biết đây là traffic thật tăng hay đang test incident `cost_spike`
- Mitigation tạm thời: Giới hạn tạm thời độ dài output (max tokens) của model; tắt incident `cost_spike` nếu đang bật nhầm trong môi trường test (`POST /incidents/cost_spike/disable`)
- Owner: ai-platform-lead
