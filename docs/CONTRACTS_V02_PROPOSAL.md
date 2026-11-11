# Notion v0.2 integration proposal

Source: https://app.notion.com/p/40f9cc1ed390818a9574d0006d788489

Pending approval by VT1–VT5. This source snapshot is a proposal, not implemented API.


<callout icon="🧭" color="blue_bg">
<b>Bổ sung tích hợp v0.2 — cần nhóm phê duyệt tại G0.</b> Các API v0.1 bên dưới được giữ làm baseline. Những quy ước v0.2 là đề xuất để chốt trước triển khai, chưa phải code đã có. Task 1.1 phải đồng bộ models, contracts và test vào GitHub; ghi PR/commit sau khi đồng bộ.
</callout>

# Ranh giới bảo mật

<b>GameSession</b> giữ hidden solution và unrevealed clues. Logic Agent và GUI chỉ nhận <b>PublicState</b>: cell ID, tên, nghề, revealed flag; known\_status và clue là null khi chưa lật.

Mọi kết luận phải từ KB hiện có. Không dùng hidden\_status để chọn hint, không dùng một SAT model đơn lẻ để gọi verdict.

## Chuẩn chung

- Cell IDs: A1, B1, C1, A2 ... theo row-major; tên nhân vật chỉ để hiển thị.
- Criminal=True; Innocent=False.
- Biến CNF 1..N² cho primary; auxiliary bắt đầu tại N²+1.
- Clause là tuple số nguyên có dấu. CNF là dataclass gồm clauses: tuple\[Clause, ...\], primary\_count và variable\_count; solve không thay đổi input.
- Kết quả manual verdict: ACCEPTED, NOT\_PROVABLE, CONTRADICTED, INCONSISTENT.

## API signatures (đề xuất, chờ G0 phê duyệt)

```py
# VT1
class GameSession:
    def snapshot(self) -> PublicState: ...
    def submit_verdict(self, cell: str, status: Status) -> SubmitResult: ...
    def restart(self) -> PublicState: ...

# VT2
def resolve_region(region: Region, size: int) -> tuple[str, ...]: ...
def evaluate_clue(clue: Clue, assignment: dict[str,bool], size: int) -> bool: ...
def encode_kb(public: PublicState) -> CNF: ...

# VT3
def solve(cnf: CNF, assumptions: tuple[int,...]=()) -> SATResult: ...

# VT4
def classify(public: PublicState, encoder, solver) -> dict[str,Inference]: ...
def next_forced_verdict(public: PublicState, encoder, solver) -> tuple[str,Status]|None: ...
def auto_solve(game: PublicGamePort, encoder, solver) -> DeductionTrace: ...

# VT5
class GameView:
    def render(self, public: PublicState) -> None: ...
    def highlight_cells(self, cells: tuple[str,...]) -> None: ...
    def show_trace(self, trace: DeductionTrace) -> None: ...
```

## Quy tắc entailment

- KB UNSAT -> INCONSISTENT
- KB ∧ ¬Ci UNSAT -> CRIMINAL
- KB ∧ Ci UNSAT -> INNOCENT
- Cả hai SAT -> UNKNOWN

Nếu nhiều người đã được chứng minh, chọn người đầu tiên theo row-major. Chỉ sau khi accepted verdict mới nhận clue mới và tạo KB bước tiếp theo.

## Uniqueness check

Kiểm tra riêng trên complete clue set: tìm model đầu, thêm blocking clause chỉ với <b>primary</b> variables, gọi SAT lần hai. Nếu lần hai UNSAT, nghiệm Criminal/Innocent là duy nhất. Không đưa hidden clues vào public KB.

## Quy trình thay đổi

1. Đề xuất API thay đổi và các module bị ảnh hưởng.
2. Chủ sở hữu và các vai trò sử dụng API cùng duyệt.
3. Cập nhật [docs/CONTRACTS.md](https://github.com/HoangLongNha/griductive-solver/blob/main/docs/CONTRACTS.md), tests và implementation đồng thời; ghi PR/commit đồng bộ.
4. Merge PR khi CI xanh và không còn breaking callers.

Baseline chi tiết: [docs/CONTRACTS.md trên GitHub](https://github.com/HoangLongNha/griductive-solver/blob/main/docs/CONTRACTS.md), phiên bản starter v0.1. Phần bổ sung Notion v0.2 bên dưới cần được duyệt và đồng bộ qua task 1.1; không coi API đề xuất là implementation đã có.

## Giao diện tích hợp tối thiểu v0.2

VT1 quản lý Controller và shared models; VT5 triển khai view/FakeController cùng chữ ký. VT4 cung cấp suy luận chỉ từ public state. Phác thảo sau cần được chốt tại G0 và đồng bộ ở task 1.1 trước khi các bên dùng làm contract chính thức:

```py
class ControllerPort(Protocol):
    def load(self, path: str) -> PublicState: ...
    def restart(self) -> PublicState: ...
    def submit_verdict(self, cell: str, status: Status) -> SubmitResult: ...
    def hint(self) -> HintResult: ...
    def start_auto(self) -> None: ...
    def cancel_auto(self) -> None: ...

# Event được đưa qua hàng đợi; GUI đọc bằng Tkinter.after.
# on_event(event: AppEvent) được đăng ký khi khởi tạo Controller.
# Logic Agent có thể cung cấp iter_solve(...) hoặc callback on_step.
# auto_solve(...) vẫn có thể gom các step thành DeductionTrace cuối.
```

| Dữ liệu | Trường tối thiểu cần chốt |
| --- | --- |
| HintResult | outcome, cell/status nếu forced, revealed\_clue\_ids, message; không chứa hidden clue |
| SATQuery | assumptions, result SAT/UNSAT, stats, purpose |
| DeductionStep | step\_number, active\_clue\_ids, queries, verdict, newly\_revealed\_clue\_id, cumulative\_stats |
| AppEvent | session\_id, revision, kind, payload; kind gồm STATE\_CHANGED, STEP, FINISHED, ERROR |
| DeductionTrace | steps, terminal SOLVED/STUCK/INCONSISTENT, totals |
| Lỗi tính toán | SolverTimeout/SolverCancelled có kiểu riêng; không diễn giải thành verdict logic |

Trace ghi SAT queries và kết quả thật; không bắt buộc UNSAT core. Classifier công khai vẫn phải phân loại <b>mọi unresolved character</b>. Hint có thể trả một forced character; không thay thế đầu ra classifier đầy đủ.

## Snapshot và validation

- Snapshot phải độc lập với dữ liệu Engine, kể cả dict/list lồng trong clue. Frozen dataclass chứa dict chưa đủ bất biến: dùng typed immutable data hoặc copy/freeze toàn bộ dữ liệu được chiếu ra.
- Test sửa nested data trong snapshot không được làm thay đổi Engine hay các snapshot khác.
- Full-clue uniqueness đặt trong scope <code>validation/uniqueness.py</code>; được dùng private puzzle cho kiểm tra dữ liệu, không truyền private Puzzle vào public Agent.
- Full-clue unique và có no-guess path từ initial public KB là hai kiểm tra riêng. Unique không bảo đảm bước hiện tại có verdict forced.
- Kiểm tra base KB SAT trước các assumption queries. Base UNSAT trả INCONSISTENT; không suy ra verdict từ một KB mâu thuẫn.

## Timeout, thao tác và phiên chạy

Timeout hoặc cancel là kết quả tính toán chưa hoàn tất, không phải UNSAT và không phải UNKNOWN theo nghĩa logic. Giữ API SATResult SAT/UNSAT cho lượt chạy hoàn tất; dùng exception có kiểu riêng hoặc trạng thái riêng được nhóm thống nhất. Khi query chưa xong, không dùng nó để accept/reveal.

Controller tuần tự hóa thay đổi GameSession. Mỗi Load/Restart tạo session\_id hoặc tăng revision. Worker chỉ nhận public snapshot và gửi event có phiên bản; Controller bỏ kết quả cũ trước khi áp dụng. Widget chỉ được cập nhật trên UI thread.

Khi Auto Solve đang chạy, khóa manual verdict/Hint theo chính sách đã chốt; Load/Restart phải cancel hoặc làm vô hiệu kết quả phiên cũ. Load lỗi giữ phiên hiện tại và báo lỗi. Cell không tồn tại hoặc đã reveal không làm đổi state; chốt exception/result riêng tại G0, không gán tùy tiện vào hai loại từ chối logic.

## Phạm vi metrics

Gắn purpose cho mỗi lần solve: BASE\_KB, CLASSIFY, VERDICT\_RECHECK, HINT, UNIQUENESS hoặc VALIDATION. Tổng gameplay gồm các SAT calls thực sự phát sinh để chơi, kể cả recheck ở Engine; báo riêng validation/uniqueness ngoài phiên chơi. Nếu cache, khóa theo session\_id/revision và ghi cache hit, không đếm cache hit thành SAT call mới.

Định nghĩa decisions/propagations/backtracks phải có trong code/report và có test CNF nhỏ với số mong đợi. Tổng counter bằng tổng per-call logs; SAT runtime và end-to-end runtime ghi thành cột riêng. Counts CNF lưu theo step vì KB thay đổi sau reveal.

## Ví dụ dùng chung cho 1.3a

Mapping row-major A1=1, B1=2, C1=3. Ban đầu A1 Criminal đã reveal và c-A1 là FACT(B1, INNOCENT):

1. Public KB là (1) ∧ (¬2).
2. KB ∧ (2) UNSAT; KB ∧ (¬2) SAT → B1 Innocent.
3. C1 vẫn UNKNOWN trước khi B1 lật; không được dùng c-B1 đang ẩn.
4. Submit B1 Innocent được ACCEPTED; Engine reveal c-B1 = SAME(B1,C1).
5. Thêm (¬2∨3) ∧ (2∨¬3); từ ¬2 suy ra ¬3.
6. Trace ghi active clue IDs, assumptions/results, verdict và clue mới ở đúng bước.

Liên hệ workflow tại <mention url="https://app.notion.com/p/40f9cc1ed39081668618eee18ac4413b">01 · Workflow & Roadmap 21 ngày</mention>; tiêu chí kiểm chứng ở <mention url="https://app.notion.com/p/40f9cc1ed390816f85f3fc89fba25862">05 · Verification & Experiments</mention>.

