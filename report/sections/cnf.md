# Biểu diễn logic và mã hoá CNF (VT2)

Mã nguồn: `src/griductive/logic/` (`regions.py`, `semantics.py`, `cardinality.py`, `extensions.py`, `encoder.py`). Kiểm thử: `tests/logic/`.

## 1. Biến mệnh đề

Với bàn N×N, mỗi ô X được gán một biến chính (primary) `C_X`, với `C_X = True` nghĩa là Criminal và `C_X = False` nghĩa là Innocent. Ánh xạ được cố định theo thứ tự row-major của tọa độ ô, không phụ thuộc vào tên nhân vật:

```
var(X) = (row - 1) * N + column        (row, column đánh số từ 1)
3x3:  A1=1  B1=2  C1=3  A2=4  B2=5  C2=6  A3=7  B3=8  C3=9
```

Các biến chính chiếm ID `1..N²`. Biến phụ (auxiliary), nếu một phép mã hoá cần đến, được cấp tuần tự từ `N²+1` bởi `AuxPool`, theo thứ tự cố định: trước hết là các verdict đã biết, sau đó là clue đã lật theo thứ tự row-major của thẻ. Vì vậy cùng một trạng thái công khai luôn sinh ra đúng cùng một CNF.

## 2. Vùng (region) và ngữ nghĩa clue

`resolve_region` chuyển mỗi vùng thành một bộ ô phân biệt:

| Vùng | Các ô |
|---|---|
| `row i` | `A i, B i, …` (1 ≤ i ≤ N) |
| `column L` | `L1, L2, …, LN` (A ≤ L < A+N) |
| `neighbors X` | các ô Y ≠ X có max(\|Δcột\|, \|Δhàng\|) = 1, gồm 8 ô ở giữa, 5 ô ở cạnh, 3 ô ở góc |
| `cells [...]` | danh sách tường minh, khác rỗng, không trùng ô, nằm trong bàn |

Gọi `#R = Σ_{X∈R} C_X` là số Criminal trong vùng R. Ý nghĩa của các clue:

| Clue | Ý nghĩa |
|---|---|
| FACT(X, s) | `C_X` nếu s = CRIMINAL, `¬C_X` nếu s = INNOCENT |
| SAME(X, Y) | `C_X ↔ C_Y` |
| DIFFERENT(X, Y) | `C_X ⊕ C_Y` |
| EXACTLY(k, R) / AT_LEAST(k, R) / AT_MOST(k, R) | `#R = k` / `#R ≥ k` / `#R ≤ k`, với 0 ≤ k ≤ \|R\| |
| PARITY(ODD\|EVEN, R) *(mở rộng 1)* | `#R` lẻ / chẵn |
| COMPOUND(p₁…p_m ⇒ q) *(mở rộng 2)* | `(p₁ ∧ … ∧ p_m) → q`, trong đó mỗi pᵢ và q là literal của một ô |

Mọi clue đã lật đều đúng, bất kể chủ của clue là Criminal hay Innocent. Tên và nghề nghiệp không mang ý nghĩa logic.

`evaluate_clue` kiểm tra trực tiếp các định nghĩa trên trên một phép gán đầy đủ (bằng cách đếm hoặc so sánh), **không** gọi encoder hay bộ giải SAT. Đây là chuẩn độc lập để đối chiếu với CNF. Clue có tham số sai (ô ngoài bàn, vùng rỗng hoặc trùng ô, k ∉ [0, |R|], status không hợp lệ, loại clue lạ) đều bị từ chối bằng `ClueValidationError`.

## 3. Dẫn xuất CNF

### 3.1 Clue nhị phân: SAME và DIFFERENT

```
SAME:       a ↔ b  ≡ (a → b) ∧ (b → a)          ≡ (¬a ∨ b) ∧ (a ∨ ¬b)
DIFFERENT:  a ⊕ b  ≡ (a ∨ b) ∧ ¬(a ∧ b)         ≡ (a ∨ b) ∧ (¬a ∨ ¬b)
```

Ví dụ: SAME(B1, C1) trên bàn 3×3 cho ra `(¬2 ∨ 3) ∧ (2 ∨ ¬3)`. FACT(B1, INNOCENT) cho ra mệnh đề đơn vị `(¬2)`.

### 3.2 Clue đếm: mã hoá tổ hợp trực tiếp

Với R = {x₁…x_n}:

- **AT_MOST k:** `#R ≤ k` khi và chỉ khi không có k+1 biến nào cùng đúng. Vì vậy, với mỗi tập con S gồm k+1 phần tử, thêm mệnh đề `⋁_{x∈S} ¬x`, tổng cộng C(n, k+1) mệnh đề.
- **AT_LEAST k:** `#R ≥ k` khi và chỉ khi số biến sai không vượt quá n−k, tức là mọi tập con gồm n−k+1 biến đều chứa ít nhất một biến đúng. Vì vậy, với mỗi tập con S gồm n−k+1 phần tử, thêm `⋁_{x∈S} x`, tổng cộng C(n, n−k+1) mệnh đề.
- **EXACTLY k** = AT_MOST k ∧ AT_LEAST k.

Các trường hợp biên: AT_MOST k với k ≥ n và AT_LEAST 0 không sinh mệnh đề nào (luôn đúng). AT_MOST 0 cho n mệnh đề đơn vị `¬xᵢ`. AT_LEAST n cho n mệnh đề đơn vị `xᵢ`. Vì k ≤ |R| đã được kiểm tra trước, encoder không bao giờ sinh mệnh đề rỗng.

**Ví dụ EXACTLY(2, row 2)** trên bàn 3×3, với R = {A2, B2, C2} = {4, 5, 6}:

```
AT_MOST 2  : tập con 3 phần tử  → (¬4 ∨ ¬5 ∨ ¬6)                 "không phải cả 3 cùng là Criminal"
AT_LEAST 2 : tập con 2 phần tử  → (4 ∨ 5) ∧ (4 ∨ 6) ∧ (5 ∨ 6)    "không có cặp nào cùng Innocent"
CNF        : (¬4 ∨ ¬5 ∨ ¬6) ∧ (4 ∨ 5) ∧ (4 ∨ 6) ∧ (5 ∨ 6)       4 mệnh đề, 0 biến phụ
```

Kiểm tra đủ 8 phép gán: với #R = 0 hoặc 1, có một cặp toàn sai nên vi phạm mệnh đề dương; với #R = 3, vi phạm mệnh đề âm; chỉ #R = 2 thỏa cả bốn mệnh đề.

### 3.3 Vùng lớn: sequential counter (Sinz, 2005)

Mã hoá trực tiếp có thể bùng nổ. Với EXACTLY(12, 25 ô), vế AT_MOST 12 cần C(25, 13) = 5.200.300 mệnh đề và vế AT_LEAST 12 cần C(25, 14) = 4.457.400 mệnh đề, tổng cộng 9.657.700 mệnh đề. Vì vậy khi số mệnh đề trực tiếp vượt `DIRECT_CLAUSE_LIMIT = 256`, encoder chuyển sang sequential counter. Với chính ví dụ này, encoder chỉ sinh 1.223 mệnh đề và 600 biến phụ.

Biến phụ `s_{i,j}` gắn với điều kiện "trong x₁…x_i có ít nhất j biến đúng", nhưng chỉ theo **một chiều**: các mệnh đề buộc `s_{i,j} = True` khi điều kiện đó xảy ra, còn chiều ngược lại không được ràng buộc (một model vẫn có thể có `s_{i,j} = True` dù số biến đúng ít hơn j). Vì vậy không thể dùng giá trị `s_{i,j}` trong model để đọc ngược số đầu vào đúng. Một chiều là đủ cho tính đúng:

- Nếu #R ≤ k: gán `s_{i,j}` đúng bằng "tiền tố x₁…x_i có ≥ j biến đúng" thỏa mọi mệnh đề, nên có cách gán biến phụ.
- Nếu #R > k: các mệnh đề lan truyền buộc `sᵢ₋₁,ₖ = True` trước biến đúng thứ k+1, khiến `(¬xᵢ ∨ ¬sᵢ₋₁,ₖ)` bị vi phạm, nên không có cách gán biến phụ nào.

Các mệnh đề:

```
(¬x₁ ∨ s₁,₁),  (¬s₁,ⱼ) với j>1
với 1<i<n:  (¬xᵢ ∨ sᵢ,₁), (¬sᵢ₋₁,₁ ∨ sᵢ,₁),
            (¬xᵢ ∨ ¬sᵢ₋₁,ⱼ₋₁ ∨ sᵢ,ⱼ), (¬sᵢ₋₁,ⱼ ∨ sᵢ,ⱼ)  (2≤j≤k),
            (¬xᵢ ∨ ¬sᵢ₋₁,ₖ)
(¬xₙ ∨ ¬sₙ₋₁,ₖ)
```

Cách mã hoá này dùng (n−1)·k biến phụ và 2nk + n − 3k − 1 mệnh đề. AT_LEAST k được quy về AT_MOST (n−k) trên các literal phủ định. Với mọi vùng hàng, cột và neighbors (n ≤ 8), mã hoá trực tiếp luôn nằm dưới ngưỡng, nên các puzzle 3×3 và 4×4 hiện tại **không có biến phụ**.

### 3.4 Hai mở rộng

- **PARITY:** nếu 2^(n−1) ≤ 256, encoder loại trực tiếp từng phép gán sai tính chẵn lẻ, mỗi phép gán bị loại bởi một mệnh đề. Ví dụ ODD(row 3) = `(7∨8∨9) ∧ (7∨¬8∨¬9) ∧ (¬7∨8∨¬9) ∧ (¬7∨¬8∨9)`. Nếu vùng lớn hơn, encoder dùng chuỗi XOR Tseitin: `t ↔ a ⊕ b` được mã hoá bằng `(¬t∨a∨b)(¬t∨¬a∨¬b)(t∨¬a∨b)(t∨a∨¬b)`, tốn n−1 biến phụ, sau đó thêm một mệnh đề đơn vị cho biến cuối cùng của chuỗi.
- **COMPOUND:** `(p₁∧…∧p_m) → q ≡ ¬p₁ ∨ … ∨ ¬p_m ∨ q`, tức là một mệnh đề duy nhất. Literal lặp được gộp lại. Nếu mệnh đề chứa cả `v` và `¬v` (tiền đề mâu thuẫn, hoặc `p → p`) thì mệnh đề luôn đúng và bị bỏ.

## 4. Cơ sở tri thức KB_t

```
KB_t = ⋀_{X đã lật} (C_X hoặc ¬C_X)  ∧  ⋀_{clue đã lật} CNF(clue)
```

`encode_kb(public)` chỉ nhận `PublicState`, tức là chỉ đọc các thẻ đã lật, nên không chạm tới trạng thái ẩn hay clue ẩn. `encode_full_clues(puzzle)` mã hoá **toàn bộ** clue và không thêm đơn vị nào. Hàm này chỉ dùng cho kiểm tra uniqueness và validation, agent không bao giờ gọi nó. Mọi CNF được sinh tự động từ dữ liệu clue; không có công thức viết tay cho từng puzzle.

## 5. Số biến và số mệnh đề

`cnf_counts(cnf)` trả về `primary_count = N²`, `aux_count = variable_count − N²` và `clause_count`. Các số dưới đây được đo trực tiếp từ encoder:

| Puzzle | Toàn bộ clue: primary / aux / clauses | KB₀ (sau khi lật thẻ đầu): primary / aux / clauses |
|---|---|---|
| tutorial_3x3 | 9 / 0 / 20 | 9 / 0 / 2 |
| extensions_3x3 | 9 / 0 / 21 | 9 / 0 / 2 |
| chain_4x4_a | 16 / 0 / 16 | 16 / 0 / 2 |
| chain_4x4_b | 16 / 0 / 16 | 16 / 0 / 2 |

Phân tích tutorial_3x3: FACT 1 + SAME 2 + DIFFERENT 2 + FACT 1 + EXACTLY(2,3) 4 + EXACTLY(2,3) 4 + DIFFERENT 2 + AT_MOST(1,3) C(3,2)=3 + AT_LEAST(1,3) C(3,3)=1, tổng cộng 20 mệnh đề. KB₀ gồm mệnh đề đơn vị `(1)` (A1 là Criminal) và `(¬2)` (clue của A1 nói B1 là Innocent).

Với vùng lớn dùng biến phụ, ví dụ EXACTLY(12, 25 ô) trên bàn 5×5: aux = 24·12 + 24·13 = 600 và clauses = 588 + 635 = 1.223 (vế AT_MOST 12 và vế AT_MOST 13 trên literal phủ định), khớp với công thức ở mục 3.3; mã hoá trực tiếp sẽ cần 9.657.700 mệnh đề. Số liệu này được kiểm trong test `test_cnf04_auxiliary_counts_match_sequential_counter`.

## 6. Ví dụ suy luận trên KB_t

Các ví dụ dưới đây có trong `tests/logic/test_inference_examples.py` và `tests/logic/test_extensions.py`. Ở đây entailment được kiểm theo định nghĩa `KB ⊨ l ⟺ KB ∧ ¬l UNSAT`, bằng bộ kiểm tra chỉ dùng trong test.

- **Ví dụ chung 1.3a** (tutorial_3x3). Ban đầu KB₀ = `(1) ∧ (¬2)`. Khi đó `KB₀ ∧ (2)` UNSAT nên B1 là Innocent, còn C1 vẫn UNKNOWN vì clue `c-B1` đang ẩn. Sau khi B1 được lật, KB₁ có thêm `(¬2∨3) ∧ (2∨¬3)`, từ đó suy ra C1 là Innocent.
- **PARITY ảnh hưởng tới kết luận:** biết A1 là Criminal, B1 là Innocent và PARITY(ODD, row 1) thì C1 bắt buộc là Innocent. Nếu bỏ clue PARITY, C1 trở về UNKNOWN.
- **COMPOUND ảnh hưởng tới kết luận:** biết A1 là Criminal, B1 là Innocent và có `(A1 Criminal ∧ B1 Innocent) → C1 Criminal` thì C1 là Criminal. Nếu tiền đề sai (B1 là Criminal), C1 là UNKNOWN, vì không được suy ngược từ một kéo theo có tiền đề sai.
- **Mức gameplay** (`test_extensions.py`): với mỗi extension, một puzzle 3×3 được nạp qua `load_puzzle` vào `GameSession` (A1, B1 đã lật, clue extension nằm trên A1). Verdict cho C1 được Engine **ACCEPTED** và C1 được lật; trên cùng bàn đó nhưng thay clue extension bằng một FACT không mang thông tin, cùng verdict bị trả về **NOT_PROVABLE**. Kết luận được đối chiếu với `fixture_oracle` độc lập.
- **KB mâu thuẫn:** khi KB UNSAT, mọi ô được phân loại là INCONSISTENT.

## 7. Kiểm chứng

Tiêu chí tương đương ngữ nghĩa: với mọi phép gán A trên các biến chính, A thỏa clue **khi và chỉ khi** tồn tại một cách gán biến phụ làm CNF đúng.

- **VER-01** (`test_cross_check.py`): duyệt hết mọi FACT, mọi cặp SAME/DIFFERENT, mọi hàng, cột, neighbors (cùng một vùng `cells` không liên tiếp) với mọi k và cả hai tính chẵn lẻ, thêm một loạt COMPOUND hai tiền đề, trên cả bàn 3×3 và 4×4. Với mỗi clue, test duyệt hết mọi phép gán của các ô liên quan.
- Evaluator độc lập với encoder: test vô hiệu hoá toàn bộ các hàm sinh CNF (monkeypatch để chúng ném lỗi), và `evaluate_clue` vẫn chạy đúng trên mọi fixture.
- Phạm vi kiểm các phép mã hoá có biến phụ:
  - Sequential counter: ép dùng (`direct_limit=0`) với n = 1…7, mọi k từ 0 tới n, cho cả AT_MOST, AT_LEAST và EXACTLY.
  - Chuỗi XOR của PARITY: ép dùng với n = 1…6, cho cả ODD và EVEN; thêm một test vùng 10 ô, nơi encoder tự chuyển sang XOR (2⁹ > 256) với 9 biến phụ.
  - Số biến phụ và số mệnh đề của sequential counter ở quy mô lớn (EXACTLY(12, 25 ô)) được kiểm theo công thức.
- Mô hình của `encode_full_clues` trên các fixture trùng khớp với tập mô hình do bộ duyệt độc lập `tests/fixture_oracle.py` liệt kê.
- Việc kiểm tra "có tồn tại cách gán biến phụ" dùng một bộ tìm kiếm nhỏ chỉ có trong test (`tests/logic/cnf_check.py`), không phải DPLL production của VT3.
- **VER-03:** có test âm cho vùng hoặc tham số sai, kể cả clue sai nằm trong KB.
- Thử đột biến: khi xoá một mệnh đề của sequential counter, 6 test fail; khi đảo dấu cổng XOR của PARITY, 10 test fail.
- Lệnh tái lập: `python -m pytest -q tests/logic`.

## 8. Giới hạn

- Ngưỡng 256 là lựa chọn của nhóm, không được tối ưu bằng thực nghiệm. Có thể đổi trong `cardinality.DIRECT_CLAUSE_LIMIT`.
- CNF không loại mệnh đề trùng giữa các clue khác nhau. Số mệnh đề báo cáo là số thực tế được sinh ra.
- COMPOUND chỉ hỗ trợ dạng hội các literal suy ra một literal. Mở rộng này do nhóm tự chọn, không phải cú pháp bắt buộc của đề.
