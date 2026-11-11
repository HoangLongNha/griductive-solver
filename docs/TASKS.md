# Task plan — 5 roles / 21 days (v0.1)

This is a plan, not actual progress. Dependencies listed here are **integration dependencies**, not a reason to delay writing local mocks/tests. D1..D21 are relative days (not actual calendar dates). Each role has 30 estimated effort points; review at G1 and G3. Fixed roles: VT1 Architecture/Engine, VT2 Logic/Encoder, VT3 DPLL, VT4 Agent, VT5 GUI/Experiments. Assign named people only after group consensus.

## 1.1 — Repo, models, contracts và CI (VT1)

- **Lịch:** D1–D3 | **Công sức:** 7 | **Phụ thuộc merge cuối:** Không
- **File sở hữu:** `models.py, docs/CONTRACTS.md, pyproject.toml, .github/workflows/ci.yml`
- **Xong khi:** Hợp đồng được 5 người duyệt; pytest chạy trong CI
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** CT-01, CT-02, CT-03, CT-04

## 1.2 — Game Engine, Session và Loader (VT1)

- **Lịch:** D3–D10 | **Công sức:** 12 | **Phụ thuộc merge cuối:** 1.1 (giao diện; mock sẵn)
- **File sở hữu:** `src/griductive/game/{engine,session,loader}.py`
- **Xong khi:** Chạy Load/Restart/Verdict qua FakeVerdictOracle
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** GE-01, GE-02, GE-03, GE-04, GE-05

## 1.3 — Controller và tích hợp (VT1)

- **Lịch:** D10–D17 | **Công sức:** 6 | **Phụ thuộc merge cuối:** 1.2, 2.2, 3.2, 4.2, 5.2 (chỉ để tích hợp thật)
- **File sở hữu:** `src/griductive/controller.py, tests/integration`
- **Xong khi:** Đường đi end-to-end 3x3 qua các module thật
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** INT-01, INT-02, INT-03, INT-04

## 1.4 — Release, README, kiểm thử cuối (VT1)

- **Lịch:** D17–D21 | **Công sức:** 5 | **Phụ thuộc merge cuối:** 1.3, 3.4, 5.4
- **File sở hữu:** `README.md, requirements.txt, Source/, report/final`
- **Xong khi:** Bản nộp sạch, đúng tên MSSV và video Drive hợp lệ
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** REL-01, REL-02, REL-03, REL-04

## 2.1 — Regions, semantic evaluator, validator (VT2)

- **Lịch:** D1–D5 | **Công sức:** 8 | **Phụ thuộc merge cuối:** Không, dùng fixture và data schema
- **File sở hữu:** `src/griductive/logic/{regions,semantics}.py`
- **Xong khi:** Evaluator độc lập, resolve region đúng
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** SEM-01, SEM-02, SEM-03, SEM-04, SEM-05

## 2.2 — CNF Encoder sáu clue bắt buộc (VT2)

- **Lịch:** D3–D10 | **Công sức:** 11 | **Phụ thuộc merge cuối:** 2.1 nội bộ; không cần SAT
- **File sở hữu:** `src/griductive/logic/{encoder,cardinality}.py`
- **Xong khi:** Encode tự động cho mọi clue; semantic-equivalent
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** CNF-01, CNF-02, CNF-03, CNF-04, CNF-05

## 2.3 — Extensions PARITY, COMPOUND (VT2)

- **Lịch:** D8–D13 | **Công sức:** 6 | **Phụ thuộc merge cuối:** 2.2; nhưng có thể viết evaluator từ D1
- **File sở hữu:** `src/griductive/logic/extensions.py`
- **Xong khi:** Cả 2 extension có direct evaluator và CNF
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** EXT-01, EXT-02, EXT-03, EXT-04

## 2.4 — Cross-check và viết dẫn xuất CNF (VT2)

- **Lịch:** D11–D16 | **Công sức:** 5 | **Phụ thuộc merge cuối:** 2.2,2.3
- **File sở hữu:** `tests/logic, report/sections/cnf.md`
- **Xong khi:** Có đối chứng và derivation cho binary/counting
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** VER-01, VER-02, VER-03, VER-04

## 3.1 — DPLL core (VT3)

- **Lịch:** D1–D9 | **Công sức:** 15 | **Phụ thuộc merge cuối:** Không; tự viết CNF trong test
- **File sở hữu:** `src/griductive/sat/dpll.py`
- **Xong khi:** DPLL SAT/UNSAT và trả model đầy đủ
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** SAT-01, SAT-02, SAT-03, SAT-04, SAT-05

## 3.2 — Assumptions và SAT statistics (VT3)

- **Lịch:** D6–D11 | **Công sức:** 5 | **Phụ thuộc merge cuối:** 3.1 nội bộ
- **File sở hữu:** `src/griductive/sat/{dpll,statistics}.py`
- **Xong khi:** Giữ input CNF nguyên, trả thống kê chạy
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** STAT-01, STAT-02, STAT-03, STAT-04

## 3.3 — SAT unit & randomized differential tests (VT3)

- **Lịch:** D4–D13 | **Công sức:** 6 | **Phụ thuộc merge cuối:** 3.1 nội bộ
- **File sở hữu:** `tests/sat/`
- **Xong khi:** DPLL có coverage các ca biên và nhiều mẫu nhỏ
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** SATT-01, SATT-02, SATT-03, SATT-04

## 3.4 — Benchmark validation (VT3)

- **Lịch:** D12–D17 | **Công sức:** 4 | **Phụ thuộc merge cuối:** 4.2,5.3 để có run thật
- **File sở hữu:** `benchmark/verify.py, tests/benchmark`
- **Xong khi:** Thống kê và tính tái lập được kiểm tra
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** BEN-01, BEN-02, BEN-03, BEN-04

## 4.1 — KB & entailment classification (VT4)

- **Lịch:** D1–D8 | **Công sức:** 10 | **Phụ thuộc merge cuối:** Không; dùng FakeSAT/FakeEncoder
- **File sở hữu:** `src/griductive/agent/{knowledge_base,entailment}.py`
- **Xong khi:** Đủ CRIMINAL, INNOCENT, UNKNOWN, INCONSISTENT
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** AG-01, AG-02, AG-03, AG-04, AG-05

## 4.2 — Deduction loop & trace (VT4)

- **Lịch:** D6–D14 | **Công sức:** 10 | **Phụ thuộc merge cuối:** 4.1 nội bộ; dùng FakeGamePort
- **File sở hữu:** `src/griductive/agent/{deduction,trace}.py`
- **Xong khi:** Luồng reveal từng bước, không đoán
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** AGL-01, AGL-02, AGL-03, AGL-04, AGL-05

## 4.3 — Hint và unique complete checker (VT4)

- **Lịch:** D10–D15 | **Công sức:** 5 | **Phụ thuộc merge cuối:** 4.1; có thể dùng FakeSAT
- **File sở hữu:** `src/griductive/agent/uniqueness.py`
- **Xong khi:** Hint bảo mật và test uniqueness riêng
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** HINT-01, UNIQ-01, UNIQ-02, UNIQ-03

## 4.4 — Agent integration & report (VT4)

- **Lịch:** D13–D19 | **Công sức:** 5 | **Phụ thuộc merge cuối:** 4.2,4.3
- **File sở hữu:** `tests/agent, report/sections/agent.md`
- **Xong khi:** Agent thực tế chạy tutorial + trace
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** AGI-01, AGI-02, AGI-03, AGI-04

## 5.1 — GUI grid/cards/clue/highlight (VT5)

- **Lịch:** D1–D9 | **Công sức:** 11 | **Phụ thuộc merge cuối:** Không; FakeController + PublicState mẫu
- **File sở hữu:** `src/griductive/gui/{app,board,cards,clue_panel}.py`
- **Xong khi:** Render 3x3/4x4, highlight target regions
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** GUI-01, GUI-02, GUI-03, GUI-04, GUI-05

## 5.2 — Verdict/Hint/AutoSolve/Restart controls (VT5)

- **Lịch:** D8–D15 | **Công sức:** 7 | **Phụ thuộc merge cuối:** 5.1 nội bộ; controller mock
- **File sở hữu:** `src/griductive/gui/controls.py`
- **Xong khi:** Đủ nút, báo lỗi, GUI responsive
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** GUIC-01, GUIC-02, GUIC-03, GUIC-04, GUIC-05

## 5.3 — Puzzle dataset và benchmark charts (VT5)

- **Lịch:** D1–D16 | **Công sức:** 7 | **Phụ thuộc merge cuối:** Không để tạo fixtures; số liệu thật chờ G3
- **File sở hữu:** `puzzles/, benchmark/{run,plots}.py`
- **Xong khi:** Cố định >=2 3x3, >=2 4x4 và đầy đủ metrics
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** DATA-01, DATA-02, DATA-03, DATA-04

## 5.4 — GUI QA & Demo 5–10 phút (VT5)

- **Lịch:** D17–D21 | **Công sức:** 5 | **Phụ thuộc merge cuối:** 1.3,5.3 (chỉ bản demo thật)
- **File sở hữu:** `docs/DEMO_SCRIPT.md, report/demo_link.txt`
- **Xong khi:** Video Drive có trình diễn và thuyết minh
- **Có thể bắt đầu ngay:** dùng đúng contracts, fake ports và fixture trước khi phụ thuộc merge
- **Test IDs:** DEMO-01, DEMO-02, DEMO-03, DEMO-04


## Task 1.1 handoff (v0.2)

Branch: feat/1.1-repo-contracts. Shared baseline models, mapping, privacy guards, package configuration and PR pytest workflow are implemented. See tests/test_models.py and docs/CONTRACTS_V02_PROPOSAL.md. Local validation: python -m pytest -q, 22 passed. CT-03 requires a real GitHub Actions run; role approvals, independent review and merge remain pending.

Integration milestones from Notion v0.2: 1.3a is one real Load/public KB/DPLL/verdict/reveal/GUI loop at D10; 1.3b is full integration at D16. Dataset task 5.3a must add mixed counting 4x4, neighbors/explicit regions and diagnostic STUCK cases; current FACT chains alone do not establish counting coverage. Gameplay metrics include actual Engine rechecks, with validation/uniqueness reported separately. These are future tasks, not delivered functionality in 1.1.
