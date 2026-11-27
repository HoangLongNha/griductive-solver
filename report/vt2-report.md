## 📋 Báo Cáo Công Việc Thành Viên VT2 (`@HoangKhang206`) — Biểu Diễn Logic & Mã Hoá CNF

**Phụ trách:** Thành viên 2 (**VT2** — `@HoangKhang206`, Hoàng Khang, MSSV 24120334)  
**Ngày tổng hợp:** 27/11/2026. Nội dung đối chiếu với repository (nhánh `main` tại commit `05ad812` và nhánh `feat/ui-sound`), lịch sử pull request trên GitHub và kết quả chạy kiểm thử thực tế.  
**Phạm vi mã nguồn sở hữu (`docs/TASKS.md`):**
- `src/griductive/logic/` (`regions.py`, `semantics.py`, `cardinality.py`, `extensions.py`, `encoder.py`, `__init__.py`)
- `tests/logic/` (`test_semantics.py`, `test_encoder.py`, `test_extensions.py`, `test_cross_check.py`, `test_inference_examples.py`, `cnf_check.py`)
- `report/sections/cnf.md`
- Phần làm thêm (giao diện, có trao đổi với nhóm): màn hướng dẫn trong `web/app.jsx`, `web/styles.css`; âm thanh `web/sound.js`, `web/assets/audio/`

### 1. Tổng Quan Nhiệm Vụ Của VT2
VT2 chịu trách nhiệm **lớp logic**: chuyển dữ liệu clue của một vụ án thành công thức logic mệnh đề dạng CNF, để DPLL (VT3) và Agent (VT4) suy luận. Ba yêu cầu xuyên suốt:
1. **Tương đương ngữ nghĩa**: với mọi phép gán, CNF của một clue thỏa được khi và chỉ khi clue đúng. Điều này được kiểm bằng một bộ đánh giá trực tiếp độc lập với encoder.
2. **Chỉ dùng thông tin công khai**: `KB_t` chỉ dựng từ các thẻ đã lật, nên Agent không thể "nhìn trộm" lời giải ẩn.
3. **Tất định và tự động**: cùng một trạng thái luôn sinh cùng một CNF; mọi CNF sinh từ dữ liệu, không viết tay theo từng puzzle.

**Bảng phân công và sản phẩm:**

| Hạng mục | Công việc của VT2 | Sản phẩm đối chiếu |
| :--- | :--- | :--- |
| Task 2.1 — Vùng, ngữ nghĩa, kiểm tra | Giải vùng `row`/`column`/`neighbors`/`cells`, kiểm tra tham số clue, bộ đánh giá trực tiếp | `regions.py`, `semantics.py`; PR #6 |
| Task 2.2 — Encoder 6 clue bắt buộc | Mã hoá FACT, SAME, DIFFERENT, EXACTLY, AT_LEAST, AT_MOST; `KB_t`; đếm biến/mệnh đề | `cardinality.py`, `encoder.py`; PR #7 |
| Task 2.3 — Hai mở rộng | PARITY và COMPOUND, mỗi loại có evaluator và CNF | `extensions.py`; PR #8 |
| Task 2.4 — Đối chiếu & dẫn xuất | Đối chiếu vét cạn evaluator ⇔ CNF, ví dụ suy luận, phần báo cáo CNF | `tests/logic/`, `report/sections/cnf.md`; PR #9 |
| Làm thêm — Review chéo | Review PR của VT1, VT3, VT4 | PR #11, #12, #14, #15, #16, #18 (mục 4.2) |
| Làm thêm — Màn hướng dẫn | Đèn trần làm công tắc, đèn pin giới thiệu các đồ vật | `web/app.jsx`, `web/styles.css`; PR #23 |
| Làm thêm — Âm thanh | Hiệu ứng, tiếng đèn, nhạc nền, nút tắt tiếng | `web/sound.js`, `web/assets/audio/`; nhánh `feat/ui-sound` |

### 2. Chi Tiết Các Hạng Mục Công Việc Đã Hoàn Thành

#### 2.1. Task 2.1 — Vùng, bộ đánh giá ngữ nghĩa và kiểm tra clue (`regions.py`, `semantics.py`)
- **Biến mệnh đề**: với bàn N×N, mỗi ô X có một biến chính `C_X` (True = Criminal, False = Innocent), đánh số theo thứ tự row-major của tọa độ, không phụ thuộc tên hay nghề nghiệp nhân vật:

  ```text
  var(X) = (row - 1) * N + column        (row, column đánh số từ 1)
  3x3:  A1=1  B1=2  C1=3  A2=4  B2=5  C2=6  A3=7  B3=8  C3=9
  ```

- **Giải vùng (`resolve_region`)**:

  | Vùng | Các ô |
  | :--- | :--- |
  | `row i` | `A i, B i, …` (1 ≤ i ≤ N) |
  | `column L` | `L1, L2, …, LN` |
  | `neighbors X` | các ô Y ≠ X có max(\|Δcột\|, \|Δhàng\|) = 1: 8 ô ở giữa, 5 ô ở cạnh, 3 ô ở góc |
  | `cells [...]` | danh sách tường minh, khác rỗng, không trùng ô, nằm trong bàn |

  Mọi vùng sau khi giải phải khác rỗng; ví dụ `neighbors A1` trên bàn 1×1 bị từ chối.
- **Ngữ nghĩa clue** (`#R` là số Criminal trong vùng R):

  | Clue | Ý nghĩa |
  | :--- | :--- |
  | FACT(X, s) | `C_X` nếu s = CRIMINAL, `¬C_X` nếu s = INNOCENT |
  | SAME(X, Y) / DIFFERENT(X, Y) | `C_X ↔ C_Y` / `C_X ⊕ C_Y` |
  | EXACTLY / AT_LEAST / AT_MOST(k, R) | `#R = k` / `#R ≥ k` / `#R ≤ k`, với 0 ≤ k ≤ \|R\| |
  | PARITY(ODD\|EVEN, R) | `#R` lẻ / chẵn |
  | COMPOUND(p₁…p_m ⇒ q) | `(p₁ ∧ … ∧ p_m) → q`, mỗi pᵢ, q là literal của một ô |

  Mọi clue đã lật đều đúng, bất kể chủ của clue là Criminal hay Innocent.
- **Bộ đánh giá trực tiếp (`evaluate_clue`)**: đếm hoặc so sánh trên một phép gán đầy đủ, **không** gọi encoder hay SAT. Đây là chuẩn độc lập để đối chiếu với CNF.
- **Kiểm tra tham số (`validate_clue`)**: từ chối bằng `ClueValidationError` các trường hợp ô ngoài bàn, vùng rỗng hoặc trùng ô, k ngoài [0, |R|] hoặc không phải số nguyên (kể cả `bool`), status/parity không hợp lệ, SAME/DIFFERENT trên cùng một ô, COMPOUND không có tiền đề, loại clue lạ.

#### 2.2. Task 2.2 — Encoder CNF và cơ sở tri thức `KB_t` (`cardinality.py`, `encoder.py`)
- **Clue nhị phân**:

  ```text
  SAME:       a ↔ b  ≡ (¬a ∨ b) ∧ (a ∨ ¬b)
  DIFFERENT:  a ⊕ b  ≡ (a ∨ b) ∧ (¬a ∨ ¬b)
  FACT:       mệnh đề đơn vị (v) hoặc (¬v)
  ```

- **Clue đếm, mã hoá tổ hợp trực tiếp** với R = {x₁…x_n}:
  - AT_MOST k: mỗi tập con k+1 biến có ít nhất một biến sai, tức C(n, k+1) mệnh đề `⋁ ¬x`.
  - AT_LEAST k: mỗi tập con n−k+1 biến có ít nhất một biến đúng, tức C(n, n−k+1) mệnh đề `⋁ x`.
  - EXACTLY k = AT_MOST k ∧ AT_LEAST k. Các trường hợp luôn đúng (AT_MOST k ≥ n, AT_LEAST 0) không sinh mệnh đề; encoder không bao giờ sinh mệnh đề rỗng.

  **Ví dụ EXACTLY(2, row 2)** trên bàn 3×3, R = {A2, B2, C2} = {4, 5, 6}:

  ```text
  AT_MOST 2  : (¬4 ∨ ¬5 ∨ ¬6)                 "không phải cả 3 cùng là Criminal"
  AT_LEAST 2 : (4 ∨ 5) ∧ (4 ∨ 6) ∧ (5 ∨ 6)    "không có cặp nào cùng Innocent"
  ```

  | A2 B2 C2 | #R | Mệnh đề bị vi phạm | CNF | Evaluator |
  | :---: | :---: | :--- | :---: | :---: |
  | I I I | 0 | (4∨5), (4∨6), (5∨6) | ✗ | ✗ |
  | I I C | 1 | (4∨5) | ✗ | ✗ |
  | I C I | 1 | (4∨6) | ✗ | ✗ |
  | I C C | 2 | — | ✓ | ✓ |
  | C I I | 1 | (5∨6) | ✗ | ✗ |
  | C I C | 2 | — | ✓ | ✓ |
  | C C I | 2 | — | ✓ | ✓ |
  | C C C | 3 | (¬4∨¬5∨¬6) | ✗ | ✗ |

- **Vùng lớn, sequential counter (Sinz, 2005)**: mã hoá trực tiếp có thể bùng nổ. Ví dụ EXACTLY(12, 25 ô) cần C(25,13) + C(25,14) = 9.657.700 mệnh đề. Khi số mệnh đề trực tiếp vượt `DIRECT_CLAUSE_LIMIT = 256`, encoder chuyển sang sequential counter: (n−1)·k biến phụ và 2nk + n − 3k − 1 mệnh đề. Với ví dụ trên, encoder chỉ sinh 1.223 mệnh đề và 600 biến phụ. Biến phụ `s_{i,j}` ("trong x₁…x_i có ít nhất j biến đúng") chỉ được ràng buộc **một chiều**, và như vậy là đủ cho tính đúng: nếu #R ≤ k thì luôn có cách gán biến phụ, còn nếu #R > k thì mệnh đề `(¬xᵢ ∨ ¬sᵢ₋₁,ₖ)` bị vi phạm. AT_LEAST k được quy về AT_MOST (n−k) trên literal phủ định.

  Luồng chọn cách mã hoá cho một clue đếm:

  ```text
  encode_clue(EXACTLY | AT_LEAST | AT_MOST, k, R)
      │  validate_clue (k ∈ [0, |R|], R khác rỗng)
      ▼
  tính số mệnh đề trực tiếp:  C(n, k+1)  và/hoặc  C(n, n−k+1)
      │
      ├─ ≤ 256  ──►  mã hoá tổ hợp trực tiếp       (0 biến phụ)
      └─ > 256  ──►  sequential counter            (AuxPool cấp sᵢ,ⱼ từ N²+1)
                       AT_LEAST k = AT_MOST (n−k) trên literal phủ định
  ```

- **Biến phụ tất định (`AuxPool`)**: biến chính chiếm `1..N²`; biến phụ được cấp tuần tự từ `N²+1`, trước hết cho các verdict đã biết, rồi cho các clue đã lật theo thứ tự row-major của thẻ. Nhờ đó cùng một trạng thái luôn cho cùng một CNF, và bộ kiểm tra nghiệm duy nhất của VT4 chỉ cần chặn trên `1..N²`.
- **Dựng `KB_t` (`encode_kb`)**:

  ```text
  KB_t = ⋀_{X đã lật} (C_X hoặc ¬C_X)  ∧  ⋀_{clue đã lật} CNF(clue)
  ```

  ```text
  PublicState (snapshot của Engine; thẻ úp không chứa clue/status)
      │  lọc thẻ đã lật, sắp theo row-major
      ├─► verdict đã biết  ──►  mệnh đề đơn vị (v) / (¬v)
      └─► clue đã lật      ──►  validate_clue ──► encode_clue ──► AuxPool (nếu cần)
                                         │
                                         ▼
                CNF(clauses, primary_count = N², variable_count)
                                         │
                                         ▼
                   Agent (VT4) ──► DPLL (VT3): KB ∧ ¬l UNSAT ⇒ KB ⊨ l
  ```

  - `encode_kb(public)` chỉ nhận `PublicState`, nên không thể đọc lời giải ẩn. Test xác nhận hai puzzle chỉ khác clue ở thẻ úp sinh ra cùng một KB.
  - `encode_full_clues(puzzle)` mã hoá **toàn bộ** clue, không thêm mệnh đề đơn vị. Hàm này chỉ dùng cho kiểm tra nghiệm duy nhất và validation; Agent không gọi nó.
  - `cnf_counts`, `active_clue_ids`, `referenced_cells` phục vụ trace, benchmark và giao diện.

#### 2.3. Task 2.3 — Hai mở rộng PARITY và COMPOUND (`extensions.py`)
- **PARITY**: nếu 2^(n−1) ≤ 256, encoder loại trực tiếp từng phép gán sai tính chẵn lẻ, mỗi phép gán bởi một mệnh đề. Ví dụ ODD(row 3) = `(7∨8∨9) ∧ (7∨¬8∨¬9) ∧ (¬7∨8∨¬9) ∧ (¬7∨¬8∨9)`. Vùng lớn hơn dùng chuỗi XOR Tseitin: `t ↔ a ⊕ b` mã hoá bằng 4 mệnh đề, tốn n−1 biến phụ, cuối chuỗi thêm một mệnh đề đơn vị.
- **COMPOUND**: `(p₁∧…∧p_m) → q ≡ ¬p₁ ∨ … ∨ ¬p_m ∨ q`, tức một mệnh đề. Literal lặp được gộp; mệnh đề chứa cả `v` và `¬v` (tiền đề mâu thuẫn, hoặc `p → p`) luôn đúng nên bị bỏ.
- **Mở rộng có tác dụng thật trong ván chơi**: với mỗi extension, một puzzle 3×3 được nạp qua `load_puzzle` vào `GameSession`. Có clue extension thì Engine **ACCEPTED** verdict cho C1; thay clue đó bằng một FACT không mang thông tin thì cùng verdict bị trả về **NOT_PROVABLE**. Kết quả được đối chiếu với `fixture_oracle` độc lập.

#### 2.4. Task 2.4 — Đối chiếu vét cạn, ví dụ suy luận và báo cáo CNF (`tests/logic/`, `cnf.md`)
- **Tiêu chí tương đương**: với mọi phép gán A trên biến chính, A thỏa clue ⇔ tồn tại phép gán biến phụ làm CNF đúng. Bộ tìm kiếm "tồn tại phép gán biến phụ" nằm trong `tests/logic/cnf_check.py`, độc lập với DPLL của VT3, để lỗi của bên này không che lỗi của bên kia.
- **VER-01**: duyệt mọi FACT, mọi cặp SAME/DIFFERENT, mọi hàng/cột/neighbors/`cells` × mọi k × cả hai parity, thêm COMPOUND hai tiền đề, trên cả 3×3 và 4×4. Sequential counter được ép dùng với n = 1…7, chuỗi XOR với n = 1…6, và một vùng 10 ô tự chuyển sang XOR.
- **Ví dụ suy luận** (entailment theo định nghĩa `KB ⊨ l ⟺ KB ∧ ¬l UNSAT`):

  | Tình huống | KB | Kết luận |
  | :--- | :--- | :--- |
  | Ví dụ chung 1.3a, bước 0 (`tutorial_3x3`) | `(1) ∧ (¬2)` | B1 **Innocent**; C1 **UNKNOWN** (clue của B1 còn úp) |
  | Sau khi lật B1 | thêm `(¬2∨3) ∧ (2∨¬3)` | C1 **Innocent** |
  | PARITY | A1 Criminal, B1 Innocent, ODD(row 1) | C1 **Innocent**; bỏ PARITY thì **UNKNOWN** |
  | COMPOUND | A1 Criminal, B1 Innocent, (A1 ∧ ¬B1) → C1 | C1 **Criminal**; tiền đề sai thì **UNKNOWN** |
  | KB mâu thuẫn | `(1) ∧ (¬1)` | mọi ô **INCONSISTENT** |

- **Số biến và số mệnh đề** đo trực tiếp trên bộ puzzle của nhóm (primary / aux / clauses):

  | Puzzle | Toàn bộ clue | KB₀ (ban đầu) |
  | :--- | :---: | :---: |
  | `tutorial_3x3` | 9 / 0 / 20 | 9 / 0 / 2 |
  | `extensions_3x3` | 9 / 0 / 21 | 9 / 0 / 2 |
  | `neighbors_cells_3x3` | 9 / 0 / 116 | 9 / 0 / 3 |
  | `chain_4x4_a`, `chain_4x4_b` | 16 / 0 / 16 | 16 / 0 / 2 |
  | `extensions_4x4` | 16 / 0 / 80 | 16 / 0 / 3 |
  | `mixed_counting_4x4` | 16 / 0 / 162 | 16 / 0 / 3 |
  | `case_5x5_a` | 25 / 0 / 311 | 25 / 0 / 3 |
  | `ambiguous_3x3` *(chẩn đoán)* | 9 / 0 / 19 | 9 / 0 / 1 |
  | `stuck_4x4` *(chẩn đoán)* | 16 / 0 / 37 | 16 / 0 / 2 |

  Mọi vùng hàng, cột, neighbors (n ≤ 8) đều nằm dưới ngưỡng 256, nên không puzzle nào dùng biến phụ; sequential counter và chuỗi XOR hiện chỉ chạy trong test. Số mệnh đề tăng mạnh khi có clue đếm trên vùng `neighbors` 8 ô: EXACTLY(4, 8 ô) tốn C(8,5) + C(8,5) = 112 mệnh đề. `inconsistent_public_3x3` bị loader từ chối nên không có trong bảng. Toàn bộ dẫn xuất được trình bày trong `report/sections/cnf.md`.

#### 2.5. Bộ Kiểm Thử Logic (`tests/logic/`)
Xây dựng **159 bài kiểm thử tự động** chia thành 5 bộ test:

| File kiểm thử | Số lượng test | Nội dung kiểm thử chính |
| :--- | :---: | :--- |
| `test_semantics.py` | 54 | Giải vùng (neighbors 8/5/3 ô, vùng rỗng bị từ chối), biên của k, tham số sai, evaluator khớp `fixture_oracle` trên 800 clue ngẫu nhiên, evaluator chạy được khi mọi hàm sinh CNF bị vô hiệu hoá. |
| `test_encoder.py` | 40 | Mệnh đề chuẩn của SAME/DIFFERENT, tương đương cho mọi k và mọi loại vùng, sequential counter n = 1…7, chỉ thẻ đã lật vào KB, KB không đổi khi clue ẩn đổi, đếm biến/mệnh đề, mô hình của `encode_full_clues` khớp `fixture_oracle`. |
| `test_extensions.py` | 47 | PARITY với 0–3 Criminal, chuỗi XOR n = 1…6 và tự chuyển sang XOR ở n = 10, bảng chân trị COMPOUND, extension quyết định verdict ở mức gameplay. |
| `test_cross_check.py` | 14 | VER-01 duyệt vét cạn trên 3×3 và 4×4; VER-03 tham số sai, encoding tất định. |
| `test_inference_examples.py` | 4 | Ví dụ chung 1.3a và các ví dụ suy luận ở mục 2.4. |

Ngoài test thông thường, VT2 **thử đột biến** để đo độ mạnh của test: xoá một mệnh đề của sequential counter thì 6 test fail; đảo dấu cổng XOR của PARITY thì 10 test fail.

### 3. Kiến Trúc Và Tích Hợp
Encoder giữ đúng chữ ký trong `docs/CONTRACTS.md` §3, nên các vai trò khác dùng trực tiếp, không cần lớp chuyển đổi:

```text
                    ┌──────────────── griductive.logic (VT2) ────────────────┐
PublicState ──────► │ encode_kb ──────────────┬──► Agent: build_kb, classify,  │──► DPLL (VT3)
(Engine, VT1)       │                         │    hint, auto_solve (VT4)      │
                    │                         └──► Controller: oracle, step,   │
                    │                              auto-solve (VT1)            │
Puzzle ───────────► │ encode_full_clues ──────────► Uniqueness checker (VT4)   │──► DPLL (VT3)
                    │ referenced_cells ───────────► Giao diện web (VT5)        │
                    │ validate_clue, encode_* ────► Benchmark                  │
                    └────────────────────────────────────────────────────────┘
```

| Nơi sử dụng | Hàm của VT2 | Mục đích |
| :--- | :--- | :--- |
| `agent/knowledge_base.py` (VT4) | `encode_kb` | Dựng `KB_t` cho mọi truy vấn entailment |
| `validation/uniqueness.py` (VT4) | `encode_full_clues` | Mã hoá toàn bộ clue để kiểm tra nghiệm duy nhất |
| `game/controller.py` (VT1) | `encode_kb` | `AgentVerdictOracle`, Hint, Auto Solve, bước chứng minh từng thẻ |
| `web/controller.py` (VT5) | `referenced_cells` | Highlight các ô mà một clue nhắc tới |
| `benchmark/run.py` | `validate_clue`, `encode_kb`, `encode_full_clues` | Kiểm tra dữ liệu, đo số biến và số mệnh đề theo từng bước |

- **Phân tách trách nhiệm**: VT2 chỉ biến dữ liệu thành CNF; quyết định "chứng minh được hay không" thuộc DPLL và Agent. Vì vậy lớp logic kiểm thử được hoàn toàn mà không cần solver thật.
- **Khớp trace với CNF thật**: Agent và `encode_kb` cùng duyệt thẻ đã lật theo row-major trên cùng một `PublicState`, nên `active_clue_ids` trong trace khớp đúng với CNF gửi cho DPLL.

### 4. Các Bản Vá Lỗi, Phối Hợp, Review Chéo & Công Việc Làm Thêm

#### 4.1. Sửa theo review của VT1 (anh Long) trước khi merge
1. **PR #6**: vùng `neighbors A1` trên bàn 1×1 trả về tập rỗng nhưng vẫn qua kiểm tra → kiểm tra rỗng áp dụng cho mọi loại vùng, thêm test `test_sem03_empty_region_rejected_for_every_type`.
2. **PR #8**: chưa có ví dụ cho thấy extension thực sự quyết định một bước suy luận → thêm test mức gameplay (mục 2.3).
3. **PR #9**: ba chỗ trong báo cáo cần sửa (ngữ nghĩa một chiều của biến phụ, số mệnh đề trực tiếp của EXACTLY(12, 25 ô), phạm vi kiểm thử) → đã sửa.

#### 4.2. Review chéo Pull Request của các thành viên khác
Mỗi PR được ghép thử với `main`, chạy toàn bộ test và đo bằng số liệu cụ thể trước khi gửi nhận xét. Góp ý được ghi rõ là "cần sửa", "nên sửa" hay "tùy chọn".

| PR | Task (vai trò) | Phát hiện chính | Kết quả |
| :--- | :--- | :--- | :--- |
| #14 | 3.2 SAT statistics (VT3) | DPLL phân nhánh cả trên biến không xuất hiện trong mệnh đề nào: một KB mâu thuẫn 5×5 chỉ 6 mệnh đề tốn 2.097.151 decisions (5,85 s); test chưa kiểm giá trị của bộ đếm. | Chọn biến trong mệnh đề chưa thỏa (ca trên còn 1 decision); thêm test số đếm. Approve 21/11. |
| #15 | 3.3 SAT differential tests (VT3) | Bộ sinh CNF ngẫu nhiên tạo mệnh đề rỗng ở 81/100 ca, không có ca UNSAT thật; một lỗi cài thử ở nhánh quay lui lọt qua SATT-01. | Sinh mệnh đề từ 1 literal; SATT-01 có 55 ca UNSAT và bắt được lỗi cài thử. Approve 21/11. |
| #11 | 4.2 Deduction loop (VT4) | Base trỏ vào nhánh đã merge; Agent đọc thuộc tính private `game._oracle`. | Đổi base sang `main`; dùng kênh `oracle_query_log` công khai; số lượt SAT trong trace khớp solver (104/104, 300/300). Approve 22/11. |
| #12 | 4.3 Hint và uniqueness (VT4) | Kiểm chứng uniqueness khớp bộ duyệt vét cạn trên mọi fixture, đúng cả khi có 24 biến phụ. | Approve 21/11. |
| #16 | 4.4 Agent integration (VT4) | Test AGI-01 chỉ pass nhờ đọc `game._oracle`; báo cáo dẫn file `docs/ARCHITECTURE.md` không tồn tại. | Dùng log công khai trong test; sửa tài liệu tham khảo. Approve 22/11. |
| #18 (#17) | 1.3.1 Controller (VT1) | Hai PR trùng một nhánh; conflict ở `benchmark/run.py`; giao diện ẩn các puzzle chẩn đoán nên không demo được trạng thái STUCK. | Đóng PR trùng, giữ bản benchmark của PR (339 test pass), thêm mục "diagnostic". Approve 25/11. |

Khi kiểm tra bản `main` ngày 25/11, VT2 phát hiện giao diện vẫn chạy bằng `FakeController` (duyệt vét cạn thay cho encoder, DPLL và Agent thật): puzzle 5×5 dừng ở STUCK sau 0 bước trên giao diện, trong khi benchmark giải được. PR #18 nối giao diện với Controller thật; VT2 kiểm tra lại và Auto-Deduce giải 5×5 trong 24 bước. Các mục review là đóng góp kiểm tra; phần sửa vẫn do tác giả PR thực hiện.

#### 4.3. Làm thêm — Màn hướng dẫn trong phòng làm việc (PR #23, merge 26/11)
Người chơi mới không biết đồ vật nào trong phòng bấm được và chúng làm gì. VT2 làm màn hướng dẫn theo phong cách noir của game, chỉ sửa `web/app.jsx`, `web/styles.css`, không đụng backend.
- **Ngọn đèn trần là công tắc**: lần đầu vào game có dấu "!" nhảy cạnh bóng đèn (đánh dấu đã xem bằng `localStorage`). Bấm vào thì đèn chập chờn khoảng 2,3 s rồi tắt.
- **Đèn pin**: chùm sáng từ phía dưới màn hình (sau lưng người chơi) lần lượt rọi bảng điều tra và hồ sơ, điện thoại (Hint), kính lúp (Auto-Deduce), máy đánh chữ (Ledger), rồi tổng kết. Có 6 bước, tổng khoảng 30 s; vùng sáng trượt mượt 700 ms giữa các đồ vật, và ghi chú tự né để không che đồ vật đang sáng.
- **Tương tác trong lúc xem**: bấm vào đồ vật đang sáng thì chức năng thật chạy, hướng dẫn tạm dừng và tiếp tục khi quay lại. Auto-Deduce cần bấm hai lần vì sẽ giải hết vụ án. Có tạm dừng, bỏ qua bằng Esc (kể cả lúc đèn đang tắt), và chế độ giảm chuyển động.
- **Kết thúc**: đèn trần sáng lại, đóng dấu "CASE OPEN". Muốn xem lại, người chơi tắt đèn trần lần nữa.

Luồng trạng thái của `RoomBriefing`:

```text
OFF ──(bấm đèn trần)──► LIGHTS_OFF ──(2,3 s / Esc bỏ qua)──► PLAYING
                                                              │  6 bước tự chạy, Space tạm dừng, → chuyển bước
                                                              ├──(bấm đồ vật đang sáng)──► EXPLORING
                                                              │     chức năng thật chạy ◄──(Resume)──┘
                                                              └──(hết bước cuối)──► ENDING ──► OFF (đã xem = 1)
                                     Esc ở bất kỳ trạng thái nào ──► mờ dần ──► OFF
```

Kiểm chứng bằng kịch bản tự động điều khiển Chrome headless qua DevTools Protocol: 22 kiểm tra gồm tự chạy, tạm dừng, thử đồ vật, vị trí chùm sáng, Esc, tải lại trang và xem lại; không có lỗi JavaScript.

#### 4.4. Làm thêm — Âm thanh (nhánh `feat/ui-sound`, chưa tạo PR tại thời điểm viết)
- **Hiệu ứng theo trạng thái game**: đóng dấu khi verdict được chấp nhận, tiếng gõ khi NOT_PROVABLE, tiếng "sai" khi CONTRADICTED, chuông điện thoại cho Hint, máy đánh chữ cho Ledger, hợp âm khi phá án, tiếng giấy và tiếng đóng khi mở/đóng hồ sơ hoặc bấm X.
- **Tiếng đèn trong màn hướng dẫn**: tiếng công tắc, tiếp đó là tiếng bóng đèn yếu rè rè chập chờn theo đúng nhịp nhấp nháy trên màn hình (cùng mốc 2,3 s với `@keyframes briefing-lights-off`), tiếng bật và lia đèn pin, tiếng đèn bật lại khi kết thúc.
- **Nhạc nền** noir jazz nhẹ (Rê thứ, 70 bpm), tổng hợp bằng Web Audio API, âm lượng thấp để không lấn hiệu ứng.
- **Nút bật/tắt tiếng** có ghi nhớ lựa chọn; âm thanh chỉ bắt đầu sau thao tác đầu tiên của người chơi, theo chính sách autoplay của trình duyệt.
- **Nguồn âm**: tiếng công tắc và tiếng rè dùng hai bản ghi từ Pixabay (Pixabay Content License), đã cắt đoạn và lọc tần số; nguồn ghi trong `web/assets/audio/CREDITS.md`. Mọi âm còn lại tổng hợp trong `web/sound.js`, với API công khai chỉ gồm `play`, `isMuted`, `setMuted`, `subscribe`.

Luồng âm thanh khi tắt đèn:

```text
bấm đèn trần ──► play("switchOff")
                   ├─ 0 s     light-switch.wav (tiếng công tắc)
                   ├─ 0,03 s  bulb-buzz.wav (rè rè), âm lượng bám theo LIGHTS_OFF_TIMELINE
                   │          ↕ cùng mốc thời gian với keyframes nhấp nháy trong styles.css
                   └─ 2,3 s   đèn tắt hẳn ──► PLAYING ──► play("torchOn") lần đầu rọi,
                                                          play("sweep") mỗi lần chuyển đồ vật
```

Kiểm chứng bằng kịch bản Chrome headless riêng (22 kiểm tra: âm phát đúng sự kiện, nút tắt tiếng, Esc lúc đèn tắt) và chạy lại kịch bản của màn hướng dẫn (22/22).

### 5. Kết Quả Nghiệm Thu
- **Chạy kiểm thử phần logic (`python -m pytest -q tests/logic`)**: `159 passed`.
- **Chạy kiểm thử toàn bộ dự án (`python -m pytest -q`, `main` tại `05ad812`)**: `374 passed`.
- **Chạy thật trên giao diện**: Auto-Deduce giải `case_5x5_a` trong 24 bước bằng encoder, DPLL và Agent thật; màn hướng dẫn và âm thanh chạy trên Chrome không lỗi JavaScript.
- **Pull request**: #6 (2.1), #7 (2.2), #8 (2.3), #9 (2.4) đã merge vào `main` ngày 18/11 (người merge: HoangLongNha); #23 (màn hướng dẫn) merge ngày 26/11; âm thanh nằm trên nhánh `feat/ui-sound`, chưa tạo PR.
- **Tuân thủ quy trình Git & quyền sở hữu file**: phần logic chỉ sửa file thuộc VT2 trong `docs/TASKS.md`; phần giao diện làm thêm được trao đổi với nhóm và ghi rõ trong PR; review chỉ góp ý, không sửa trực tiếp file của thành viên khác.
- **Giới hạn đã biết**:
  - Ngưỡng `DIRECT_CLAUSE_LIMIT = 256` do nhóm chọn, chưa tối ưu bằng thực nghiệm.
  - CNF không loại mệnh đề trùng giữa các clue khác nhau.
  - COMPOUND chỉ hỗ trợ dạng hội literal suy ra một literal.
  - Bộ puzzle hiện tại chưa có vùng đủ lớn để kích hoạt sequential counter hay chuỗi XOR khi chơi.
  - Trên màn hình rất rộng hoặc thấp (ultrawide, 1366×768), tranh nền bị cắt nên ngọn đèn trần có thể bị che một phần.

### 6. Phụ Lục Sử Dụng Generative AI
**Công cụ:** Claude Code (trợ lý lập trình của Anthropic), chạy trong VS Code trên repository của nhóm.

**Cách phân chia công việc với AI:**
- **Thành viên:** đọc đặc tả và chia việc; đặt yêu cầu, ràng buộc và tiêu chí nghiệm thu cho từng phần; nghiệm thu và yêu cầu chỉnh lại khi kết quả chưa đúng; tự commit, push, tạo PR và đăng review.
- **AI:** lập trình từng phần nhỏ theo yêu cầu; đề xuất phương án kỹ thuật khi được hỏi, để thành viên kiểm tra; chạy test và đo đạc; soạn nháp văn bản.
- **Trình bày:** mỗi mục bên dưới gồm prompt chính và các điều chỉnh của thành viên sau khi kiểm tra kết quả. Prompt được biên tập lại từ yêu cầu gốc cho rõ ràng; nội dung yêu cầu giữ nguyên.

#### 6.1. Lớp logic (Task 2.1–2.4)
> **P1 — Đọc đặc tả.** Đọc `docs/CONTRACTS.md`, `docs/TASKS.md` và bảng phân công trên Notion tôi cung cấp. Tóm tắt các giao diện VT2 phải cung cấp, và xác nhận task nào làm được ngay mà không cần chờ thành viên khác merge.

> **P2 — Triển khai theo từng task.** Làm lần lượt 2.1 → 2.4, mỗi task là một phần riêng, theo đúng chữ ký trong `CONTRACTS.md` §3. Ràng buộc:
> 1. bộ đánh giá clue phải tính trực tiếp, không gọi encoder;
> 2. CNF phải tương đương ngữ nghĩa với clue;
> 3. `KB_t` chỉ đọc `PublicState`.
>
> Với clue đếm trên vùng lớn, đề xuất cách mã hoá và giải thích dẫn xuất để tôi kiểm tra trước khi dùng. Mỗi task phải có test theo đúng Test IDs trong `TASKS.md`.

> **P3 — Tự kiểm định theo yêu cầu.** Đối chiếu từng task với các tiêu chí "Xong khi" trên Notion tôi gửi, và liệt kê chỗ nào chưa đạt trước khi tôi gửi cho thành viên khác review.

> **P4 — Quy tắc Git.** Không tự commit hay push. Chia thay đổi thành nhánh và commit riêng cho từng task, đưa tôi các lệnh để tự chạy. Commit và PR không có dấu hiệu AI.

- **Điều chỉnh của thành viên:** sửa theo review của VT1 (mục 4.1); yêu cầu kiểm tra lại trạng thái commit trên máy và trên GitHub trước mỗi lần push.

#### 6.2. Review chéo
> **P5 — Review có kiểm chứng.** Review lần lượt các PR chưa được review: ghép thử với `main`, chạy toàn bộ test, đưa số liệu cho từng nhận định. Tôi sẽ đọc lại và tự đăng lên GitHub.

- **Điều chỉnh của thành viên:**
  - Rút ngắn nhận xét.
  - Đánh giá lại từng điểm: có thật sự phải sửa về cú pháp lẫn nghiệp vụ không? Điểm nào chỉ là đề xuất thì ghi rõ là đề xuất.
  - Trước khi merge, kiểm tra lại xem tác giả đã sửa đủ chưa.

> **P6 — Kiểm tra bản tích hợp.** Kéo bản `main` mới nhất, chạy chương trình và giải thích các thành phần bấm được trên giao diện mà tôi chưa rõ cách dùng.

#### 6.3. Màn hướng dẫn (UI/UX)
> **P7 — Ý tưởng và mô phỏng trước.** Người chơi không biết các nút ban đầu bấm được và có tác dụng gì. Tôi muốn một màn hướng dẫn theo phong cách của game:
> - làm tối nền;
> - các đồ vật bấm được sáng lên và có chú thích.
>
> Đánh giá và mô phỏng trước khi làm.

> **P8 — Hành vi mong muốn.** Màn hướng dẫn chạy như một đoạn video:
> - bấm để bắt đầu, xong thì có hiệu ứng kết thúc và chuyển sang màn chính;
> - trong lúc một đồ vật đang sáng, người chơi vẫn bấm thử được;
> - lần đầu vào game thì tự chạy, dừng ở mỗi đồ vật một khoảng phù hợp;
> - nút xem lại để nhỏ và mờ, vì hiếm khi dùng.

- **Điều chỉnh của thành viên sau từng lần chạy thử:**
  - Làm nền tối hơn, dùng hiệu ứng light focus cho chân thật.
  - Đặt điểm sáng đúng vào bóng đèn; rút ngắn thời gian dừng ở mỗi đồ vật; làm chuyển cảnh giữa các đồ vật mượt hơn.
  - Chọn hướng chiếu từ phía sau lưng người chơi, như một chiếc đèn pin, thay cho chiếu từ đèn trần.
  - Sửa viền đen trên bảng và máy in ở màn cuối.
  - Bỏ nút "?": dùng chính bóng đèn trong tranh, lần đầu có dấu "!" nhảy cạnh đèn để người chơi biết mà bấm.

#### 6.4. Âm thanh
> **P9 — Hiệu ứng và nhạc nền.** Thêm âm thanh cho trò chơi. Chỉnh từng âm một.
> - Khi tắt đèn: tiếng công tắc, rồi tiếng rè rè của bóng điện yếu chớp chớp, rồi tắt.
> - Nhạc nền: kịch tính nhưng nhẹ nhàng.

> **P10 — Nguồn âm do thành viên chọn.** Tiếng công tắc lấy từ file `dragon-studio-light-switch-382712`. Tiếng rè lấy theo file `freesound_community-room-with-buzz-incandescent-light-bulb-23892`. Cả hai file nằm trong thư mục tải về.

- **Điều chỉnh của thành viên:**
  - Tiếng rè chưa đúng bản ghi: chọn lại đúng đoạn có tiếng rè.
  - Kéo dài giai đoạn chớp tắt để nghe được tiếng rè lâu hơn.
  - Làm lại tiếng sau công tắc khi bật đèn.
  - Thêm âm thanh khi bấm X và khi thoát.

#### 6.5. Dọn mã và báo cáo
> **P11 — Phạm vi dọn mã.** Chỉ dọn mã thừa trong những phần chúng tôi viết, không động vào phần của thành viên khác.

> **P12 — Báo cáo.** Gom thành một file `vt2-report` theo cấu trúc báo cáo VT4 của Project 1:
> - trình bày theo task, thêm các việc làm thêm để hỗ trợ thành viên khác;
> - phần nào phức tạp thì vẽ luồng;
> - lấy các phần phù hợp từ `cnf.md`.

#### 6.6. Kiểm soát kết quả do AI tạo ra
- **Mã nguồn:** kiểm bằng `pytest` (159 test logic, 374 test toàn dự án), đối chiếu vét cạn với bộ đánh giá độc lập và thử đột biến.
- **Giao diện và âm thanh:** thành viên chạy thử trực tiếp, nhận xét qua ảnh chụp màn hình và nghe thử; ngoài ra có kịch bản Chrome headless, 22 kiểm tra cho mỗi phần.
- **Review và báo cáo:** nhận xét review do thành viên đọc lại và tự đăng; số liệu trong báo cáo được đo lại từ mã nguồn và lịch sử PR.
- **Git:** việc commit, push và tạo PR do thành viên tự thực hiện.

### 7. Nguồn Đối Chiếu
1. Repository [HoangLongNha/griductive-solver](https://github.com/HoangLongNha/griductive-solver): `main` tại commit `05ad812`; nhánh `feat/ui-sound`.
2. Pull request của VT2: [#6](https://github.com/HoangLongNha/griductive-solver/pull/6), [#7](https://github.com/HoangLongNha/griductive-solver/pull/7), [#8](https://github.com/HoangLongNha/griductive-solver/pull/8), [#9](https://github.com/HoangLongNha/griductive-solver/pull/9), [#23](https://github.com/HoangLongNha/griductive-solver/pull/23).
3. PR đã review: [#11](https://github.com/HoangLongNha/griductive-solver/pull/11), [#12](https://github.com/HoangLongNha/griductive-solver/pull/12), [#14](https://github.com/HoangLongNha/griductive-solver/pull/14), [#15](https://github.com/HoangLongNha/griductive-solver/pull/15), [#16](https://github.com/HoangLongNha/griductive-solver/pull/16), [#18](https://github.com/HoangLongNha/griductive-solver/pull/18).
4. Russell, S., & Norvig, P. (2020). *Artificial Intelligence: A Modern Approach* (4th ed.), chương 7 — logic mệnh đề, CNF, entailment.
5. Sinz, C. (2005). *Towards an Optimal CNF Encoding of Boolean Cardinality Constraints*. CP 2005, LNCS 3709 — sequential counter.
6. Tseitin, G. S. (1968). *On the complexity of derivation in propositional calculus* — biến phụ cho cổng XOR.
7. Âm thanh: Pixabay (Pixabay Content License), chi tiết trong `web/assets/audio/CREDITS.md`.
8. Tài liệu nhóm: `docs/CONTRACTS.md`, `docs/TASKS.md`, `report/sections/cnf.md`.
