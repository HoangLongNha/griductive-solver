# Test case matrix — acceptance evidence for every task

Unit tests must be implemented by the owner when coding. This file contains specifications, **not claims that production modules passed**. Only starter fixture validation tests have been executed.

## 1.1 — Repo, models, contracts và CI

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `CT-01` | Import các dataclass/enum thành công, hợp lệ kiểu dữ liệu | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CT-02` | Mapping A1,B1,C1,A2... deterministic cho 3x3 và 4x4 | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CT-03` | CI gọi pytest tự động khi mở PR | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CT-04` | PublicCard face-down có known_status=None và clue=None | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 1.2 — Game Engine, Session và Loader

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `GE-01` | Snapshot không tiết lộ clue và hidden_status của thẻ úp | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GE-02` | Forced verdict -> ACCEPTED, lật đúng một card và thêm clue | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GE-03` | UNKNOWN -> NOT_PROVABLE; verdict ngược -> CONTRADICTED; state nguyên vẹn | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GE-04` | Restart trả lại danh sách card lật ban đầu | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GE-05` | Loader từ chối duplicate cell, out-of-board region, k không hợp lệ | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 1.3 — Controller và tích hợp

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `INT-01` | Tutorial 3x3 Auto Solve hoàn thành với lộ trình chứng minh | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `INT-02` | 4x4 không đoán, nếu stuck phải trả trạng thái terminal | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `INT-03` | Controller chỉ gửi PublicState cho GUI/Agent | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `INT-04` | Manual verdict không chứng minh được không lật bài | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 1.4 — Release, README, kiểm thử cuối

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `REL-01` | Máy sạch cài thư viện và chạy main.py | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `REL-02` | ZIP có Source/main.py, README.md, requirements.txt, Report.pdf | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `REL-03` | Không có test, secrets, cache hay file sandbox thừa trong release | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `REL-04` | Link video Drive kiểm tra được ở cửa sổ ẩn danh | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 2.1 — Regions, semantic evaluator, validator

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `SEM-01` | 6 clue core đúng theo assignment mẫu | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SEM-02` | Neighbors center=8, edge=5, corner=3; exclude self | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SEM-03` | Explicit cells không trùng; rows/columns theo tọa độ | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SEM-04` | K=0 và k=|R| hợp lệ; k>|R| phải reject | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SEM-05` | Không suy luận truthfulness dựa vào profession/name | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 2.2 — CNF Encoder sáu clue bắt buộc

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `CNF-01` | SAME tạo (¬A∨B) ∧ (A∨¬B); DIFFERENT tạo (A∨B) ∧ (¬A∨¬B) | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CNF-02` | Cardinality EXACTLY k tương đương evaluator với mọi assignment nhỏ | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CNF-03` | Chỉ revealed clue và proved status vào KB; mỗi known verdict là unit | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CNF-04` | Đếm primary, auxiliary, clauses đúng số thực tế | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `CNF-05` | Không hardcode công thức theo từng puzzle | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 2.3 — Extensions PARITY, COMPOUND

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `EXT-01` | PARITY ODD/EVEN đúng với region 0,1,2,3 criminals | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `EXT-02` | COMPOUND (p1 ∧ p2) ⇒ q đúng trong 8 tổ hợp boolean | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `EXT-03` | CNF extension semantic equivalent cho tất cả assignment nhỏ | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `EXT-04` | Không coi chủ clue là người nói thật/nói dối | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 2.4 — Cross-check và viết dẫn xuất CNF

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `VER-01` | Với mỗi clue nhỏ enumerate tất cả assignment: evaluator iff CNF exists aux completion | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `VER-02` | Báo cáo dẫn xuất SAME/DIFFERENT + EXACTLY(2,3) | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `VER-03` | Invalid region/parameter phải có test âm tính | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `VER-04` | Report giải thích primary/aux/clauses counts | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 3.1 — DPLL core

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `SAT-01` | CNF [[1,2],[-1,2]] -> SAT, model B=True | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SAT-02` | CNF [[1],[-1]] -> UNSAT | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SAT-03` | CNF gồm empty clause -> UNSAT; empty CNF -> SAT | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SAT-04` | Deterministic selection smallest unassigned var | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SAT-05` | Case cần backtracking trả đáp án đúng | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 3.2 — Assumptions và SAT statistics

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `STAT-01` | Assumption 1 với KB unit -1 -> UNSAT | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `STAT-02` | Assumptions đồng thời 1 và -1 -> UNSAT | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `STAT-03` | Sau solve KB.clauses không đổi | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `STAT-04` | decisions, propagations, backtracks không âm; runtime_s >= 0 | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 3.3 — SAT unit & randomized differential tests

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `SATT-01` | 100 CNF nhỏ <=8 biến so với brute-force test oracle | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SATT-02` | SAT model thoả mọi clause gốc và assumptions | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SATT-03` | Negative/missing literal, repeated literal, tautology không lỗi | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `SATT-04` | Cùng seed, cùng input -> cùng SAT/UNSAT và selection | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 3.4 — Benchmark validation

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `BEN-01` | Total SAT calls = số lần solve thật được ghi log | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `BEN-02` | Tổng counters từ từng SAT call cộng đúng vào benchmark | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `BEN-03` | Bộ puzzle không thay giữa các lần chạy | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `BEN-04` | Ghi failure/timeout thay vì bỏ dòng | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 4.1 — KB & entailment classification

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `AG-01` | KB SAT & KB∧¬Ci UNSAT -> CRIMINAL | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AG-02` | KB SAT & KB∧Ci UNSAT -> INNOCENT | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AG-03` | Cả hai assumption SAT -> UNKNOWN | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AG-04` | KB UNSAT -> INCONSISTENT, không quyết định verdict | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AG-05` | Không đọc thẻ ẩn; known clues only | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 4.2 — Deduction loop & trace

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `AGL-01` | Khi nhiều forced, chọn row-major cell đầu tiên | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGL-02` | Accepted -> snapshot mới -> KB mới -> tiếp tục | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGL-03` | Không forced -> STUCK, không lật bài | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGL-04` | Trace chứa step, active clues, SAT queries/results, verdict, newly revealed clue | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGL-05` | Contradiction/INCONSISTENT không tạo reveal | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 4.3 — Hint và unique complete checker

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `HINT-01` | Hint chỉ chọn currently forced cell, không đọc hidden labels | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `UNIQ-01` | Full clue set một model primary -> unique=True | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `UNIQ-02` | Hai primary models -> unique=False | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `UNIQ-03` | Blocking clause chỉ dùng primary variables, không dùng aux | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 4.4 — Agent integration & report

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `AGI-01` | Agent thật chạy tutorial_3x3 đến SOLVED | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGI-02` | Ambiguous fixture trả STUCK, không đoán | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGI-03` | Inconsistent public state trả INCONSISTENT | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `AGI-04` | Report mô tả entailment queries và deduction steps | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 5.1 — GUI grid/cards/clue/highlight

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `GUI-01` | Lưới và tọa độ A/B/C, 1/2/3 đúng | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUI-02` | Face-down không hiện clue/status | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUI-03` | Face-up hiện status/clue và tên, nghề | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUI-04` | Click clue -> highlight chính xác các cell tham chiếu | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUI-05` | Không import hidden Puzzle vào GUI | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 5.2 — Verdict/Hint/AutoSolve/Restart controls

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `GUIC-01` | Manual verdict gửi cell+status đúng controller | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUIC-02` | NOT_PROVABLE khác CONTRADICTED, không flip | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUIC-03` | Load/Restart reset board, Hint chỉ ra clue/cell hợp lệ | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUIC-04` | Auto Solve render từng bước; không treo event loop | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `GUIC-05` | Inconsistent/stuck được giải thích rõ | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 5.3 — Puzzle dataset và benchmark charts

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `DATA-01` | Schema valid, card count N², statuses/clues đúng | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `DATA-02` | Full clue set unique và test no-guess cho valid fixtures | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `DATA-03` | Benchmark xuất CSV vars, aux, clauses, SAT calls, decisions, propagations, backtracks, steps, runtime | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `DATA-04` | Cùng dataset cho mọi phép so sánh; giữ failures và timeouts | Assertion matches the stated condition; reproducible via pytest/GUI evidence |

## 5.4 — GUI QA & Demo 5–10 phút

| Test ID | Input / scenario | Expected result |
|---|---|---|
| `DEMO-01` | Trình diễn manual verdict ACCEPTED/NOT_PROVABLE/CONTRADICTED | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `DEMO-02` | Show Hint và Auto Solve, highlight clue | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `DEMO-03` | Narration/subtitles Vietnamese/English, 5–10 phút | Assertion matches the stated condition; reproducible via pytest/GUI evidence |
| `DEMO-04` | Link Drive anyone with link can view, thử incognito; KHÔNG YouTube | Assertion matches the stated condition; reproducible via pytest/GUI evidence |


## Task 1.1 executable evidence

- CT-01: tests/test_models.py::test_ct01_shared_types_and_fake_port.
- CT-02: test_ct02_row_major covers all primary cells on 3x3 and 4x4; invalid cell/variable cases also covered.
- CT-04: test_ct04_face_down_privacy and test_snapshot_clue_data_is_detached_and_recursively_immutable. Engine projection integration remains task 1.2.
- CT-03: .github/workflows/ci.yml runs pytest on pull_request and main pushes (Python 3.11/3.13); real run evidence must be attached to PR.
- Local result: python -m pytest -q -> 22 passed. Independent review and five-role contract approval are pending.

For v0.2 integration, add nested snapshot mutation, timeout/cancel, stale-session events, complete classifier output, separate uniqueness/playability and per-purpose metrics checks in the owning tasks. See CONTRACTS_V02_PROPOSAL.md.
