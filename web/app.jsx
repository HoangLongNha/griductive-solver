const { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } = React;

const ASSETS = window.GRIDUCTIVE_ASSETS || { ui: {}, characters: [], environments: {} };

function getInitials(name) {
  return (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `HTTP ${res.status}`);
  }
  return data;
}

function getCharacterAsset(card) {
  const list = ASSETS?.characters || [];
  const byName = list.find(
    (c) => c.name.toLowerCase() === (card.name || "").toLowerCase()
  );
  if (byName && byName.status === "ready" && byName.path) {
    return byName.path;
  }
  return null;
}

function getDispatchThumb(dispatch) {
  const title = dispatch?.title || "";
  if (title.includes("ORACLE") || title.includes("HINT")) {
    return ASSETS.ui?.fortuneTeller?.path;
  }
  if (dispatch?.type === "CONTRADICTED") {
    return ASSETS.characters?.[1]?.path;
  }
  if (dispatch?.type === "NOT_PROVABLE") {
    return ASSETS.ui?.rotaryPhone?.path;
  }
  return ASSETS.characters?.[0]?.path;
}

/* ============================================================
   EVIDENCE CONNECTIONS (SVG STRINGS FROM REAL CLUE TARGETS)
   ============================================================ */
function EvidenceConnections({ containerRef, docRefs, cards, selectedCell, visible }) {
  const [paths, setPaths] = useState([]);
  const [svgSize, setSvgSize] = useState({ w: "100%", h: "100%" });

  const edges = useMemo(() => {
    if (!cards) return [];
    const list = [];
    for (const card of cards) {
      if (!card.revealed || !card.clue?.highlighted_cells) continue;
      for (const target of card.clue.highlighted_cells) {
        if (target === card.cell) continue;
        list.push({
          id: `${card.cell}->${target}`,
          from: card.cell,
          to: target,
        });
      }
    }
    return list;
  }, [cards]);

  const recompute = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    setSvgSize({
      w: container.scrollWidth || "100%",
      h: container.scrollHeight || "100%",
    });
    if (edges.length === 0) {
      setPaths([]);
      return;
    }
    const base = container.getBoundingClientRect();
    if (base.width === 0 || base.height === 0) return;
    const scaleX = base.width / (container.clientWidth || 1);
    const scaleY = base.height / (container.clientHeight || 1);

    const next = [];
    for (const edge of edges) {
      const aEl = docRefs.current[edge.from];
      const bEl = docRefs.current[edge.to];
      if (!aEl || !bEl) continue;

      const aRect = aEl.getBoundingClientRect();
      const bRect = bEl.getBoundingClientRect();

      const x1 = (aRect.left - base.left) / scaleX + aEl.offsetWidth * 0.5 + container.scrollLeft;
      const y1 = (aRect.top - base.top) / scaleY + 8 + container.scrollTop;
      const x2 = (bRect.left - base.left) / scaleX + bEl.offsetWidth * 0.5 + container.scrollLeft;
      const y2 = (bRect.top - base.top) / scaleY + 8 + container.scrollTop;

      const dx = Math.abs(x2 - x1);
      const sag = Math.min(34, Math.max(12, dx * 0.12));
      const cx = (x1 + x2) * 0.5;
      const cy = Math.max(y1, y2) + sag;

      next.push({
        ...edge,
        d: `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`,
      });
    }
    setPaths(next);
  }, [containerRef, docRefs, edges]);

  useLayoutEffect(() => {
    recompute();
    const container = containerRef.current;
    if (!container) return undefined;

    let ro = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(() => recompute());
      ro.observe(container);
    }
    window.addEventListener("resize", recompute);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", recompute);
    };
  }, [recompute, containerRef, visible]);

  return (
    <svg
      className="evidence-strings-svg"
      style={{ width: svgSize.w, height: svgSize.h }}
      aria-hidden="true"
    >
      {paths.map((edge) => {
        const isActive =
          selectedCell && (edge.from === selectedCell || edge.to === selectedCell);
        const isDimmed = selectedCell && !isActive;
        const cls = [
          "evidence-string",
          isActive ? "active" : "",
          isDimmed ? "dimmed" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return <path key={edge.id} d={edge.d} className={cls} />;
      })}
    </svg>
  );
}

/* ============================================================
   PHYSICAL CHARACTER DOCUMENT ON THE BOARD
   ============================================================ */
function CharacterDocument({
  card,
  isSelected,
  isHighlighted,
  isHintTarget,
  busy,
  docRef,
  onSelectDocument,
  onSubmitVerdict,
}) {
  const portraitSrc = card.revealed ? getCharacterAsset(card) : null;
  const classes = [
    "evidence-doc",
    card.revealed ? "revealed" : "sealed",
    isSelected ? "selected" : "",
    isHighlighted ? "clue-target" : "",
    isHintTarget ? "hint-target" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="doc-slot" ref={docRef}>
      <div
        className={classes}
        onClick={() => onSelectDocument(card.cell)}
        role="button"
        tabIndex={0}
        aria-label={`${card.cell} ${card.name} (${card.profession})`}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectDocument(card.cell);
          }
        }}
      >
        <img className="doc-pin" src={ASSETS.ui?.pinBrass?.path} alt="" />

        <div>
          <div className="doc-meta-strip">
            <span className="doc-coord">{card.cell}</span>
            {card.revealed ? (
              <span
                className={`doc-stamp ${
                  card.known_status === "CRIMINAL" ? "criminal" : "innocent"
                }`}
              >
                {card.known_status}
              </span>
            ) : (
              <span className="doc-stamp sealed">SEALED</span>
            )}
          </div>

          <div className="doc-photo-frame">
            {card.revealed && portraitSrc ? (
              <img
                src={portraitSrc}
                alt={`${card.name} (${card.profession})`}
                loading="lazy"
              />
            ) : (
              <div className="doc-sealed-cover">
                <span className="doc-sealed-mark">
                  {card.revealed ? getInitials(card.name) : "?"}
                </span>
              </div>
            )}
          </div>

          <div className="doc-hand-name">{card.name}</div>
          <div className="doc-prof">
            {card.profession} · <span>#{card.cell}</span>
          </div>
          <div className="doc-ink-rule" aria-hidden="true">
            <span className="doc-ink-glyph">
              {card.revealed ? (card.known_status === "CRIMINAL" ? "✕" : "✓") : "§"}
            </span>
            <span className="doc-ink-stroke" />
          </div>
        </div>

        {card.revealed && card.clue ? (
          <div className="doc-clue-note">{card.clue.text}</div>
        ) : (
          <div className="doc-actions">
            <button
              type="button"
              className="doc-stamp-btn criminal"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onSubmitVerdict(card.cell, "CRIMINAL");
              }}
            >
              CRIMINAL
            </button>
            <button
              type="button"
              className="doc-stamp-btn innocent"
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation();
                onSubmitVerdict(card.cell, "INNOCENT");
              }}
            >
              INNOCENT
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================================================
   PHYSICAL CHARACTER DOSSIER (AGED FOLDER SLIDE-OUT)
   ============================================================ */
function CharacterDossier({
  card,
  allCards,
  busy,
  onClose,
  onSelectCell,
  onSubmitVerdict,
}) {
  // Compute real evidence connections involving this character
  const referencingClues = useMemo(() => {
    if (!allCards || !card) return [];
    return allCards.filter(
      (c) =>
        c.revealed &&
        c.clue?.highlighted_cells &&
        c.clue.highlighted_cells.includes(card.cell) &&
        c.cell !== card.cell
    );
  }, [allCards, card?.cell]);

  if (!card) return null;
  const portraitSrc = card.revealed ? getCharacterAsset(card) : null;

  return (
    <aside
      className="dossier-drawer"
      role="dialog"
      aria-label={`Dossier for ${card.name}`}
    >
      <div className="dossier-folder-tab">
        <span className="dossier-folder-label">
          DOSSIER // FILE {card.cell}
        </span>
        <button type="button" className="paper-tab" onClick={onClose}>
          Close Folder
        </button>
      </div>

      <div className="dossier-photo-sheet">
        {card.revealed && portraitSrc ? (
          <img src={portraitSrc} alt={`${card.name} (${card.profession})`} />
        ) : (
          <div className="dossier-photo-placeholder">
            <span className="doc-sealed-mark">
              {card.revealed ? getInitials(card.name) : "?"}
            </span>
          </div>
        )}
        <div>
          <h2 className="dossier-name-hand">{card.name}</h2>
          <div className="doc-prof" style={{ marginTop: 4 }}>
            {card.profession} · Seat {card.cell}
          </div>
          <div style={{ marginTop: 6 }}>
            {card.revealed ? (
              <span
                className={`doc-stamp ${
                  card.known_status === "CRIMINAL" ? "criminal" : "innocent"
                }`}
              >
                {card.known_status}
              </span>
            ) : (
              <span className="doc-stamp sealed">SEALED RECORD</span>
            )}
          </div>
        </div>
      </div>

      <div className="dossier-section">
        <h3>Statement & Evidence</h3>
        {card.revealed && card.clue ? (
          <>
            <p style={{ margin: 0, fontSize: "0.8rem" }}>{card.clue.text}</p>
            {card.clue.highlighted_cells?.length > 0 && (
              <div className="target-chip-row">
                {card.clue.highlighted_cells.map((cid) => (
                  <button
                    key={cid}
                    type="button"
                    className="target-paper-chip"
                    onClick={() => onSelectCell(cid)}
                    style={{ cursor: "pointer" }}
                  >
                    {cid}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <p style={{ margin: "0 0 8px", fontSize: "0.78rem", color: "var(--muted-olive)" }}>
              This suspect's file remains sealed. Only a logically entailed verdict will unseal their statement.
            </p>
            <div className="doc-actions">
              <button
                type="button"
                className="doc-stamp-btn criminal"
                disabled={busy}
                onClick={() => onSubmitVerdict(card.cell, "CRIMINAL")}
              >
                STAMP CRIMINAL
              </button>
              <button
                type="button"
                className="doc-stamp-btn innocent"
                disabled={busy}
                onClick={() => onSubmitVerdict(card.cell, "INNOCENT")}
              >
                STAMP INNOCENT
              </button>
            </div>
          </>
        )}
      </div>

      <div className="dossier-section">
        <h3>Referenced By Active Clues</h3>
        {referencingClues.length > 0 ? (
          referencingClues.map((ref) => (
            <div
              key={ref.cell}
              style={{
                fontSize: "0.76rem",
                padding: "5px 0",
                borderBottom: "1px dashed var(--warm-beige)",
              }}
            >
              <strong>
                {ref.name} ({ref.cell}):
              </strong>{" "}
              {ref.clue.text}
            </div>
          ))
        ) : (
          <p style={{ margin: 0, fontSize: "0.76rem", color: "var(--muted-olive)" }}>
            No revealed clues currently point to {card.cell}.
          </p>
        )}
      </div>
    </aside>
  );
}

/* ============================================================
   STATE C — INVESTIGATION BOARD SCENE
   ============================================================ */
function InvestigationBoardScene({
  visible,
  puzzles,
  selectedPuzzleId,
  onChangePuzzleId,
  onLoadPuzzle,
  onRestart,
  onHint,
  onAutoSolve,
  onOpenLedger,
  onStepBack,
  gameState,
  selectedCell,
  highlightedSet,
  hintInfo,
  dispatch,
  onDismissDispatch,
  onSelectDocument,
  onSubmitVerdict,
  busy,
}) {
  const surfaceRef = useRef(null);
  const docRefs = useRef({});
  const size = gameState?.size || 3;
  const colLabels = Array.from({ length: size }, (_, i) => String.fromCharCode(65 + i));

  return (
    <section
      className={`investigation-stage ${visible ? "visible" : ""}`}
      aria-hidden={!visible}
      aria-label="Investigation Board"
    >
      <div className="physical-board">
        {/* Contextual Paper Tabs along Wooden Frame */}
        <div className="board-ribbon">
          <div className="board-ribbon-left">
            <button type="button" className="paper-tab" onClick={onStepBack}>
              ← Room View
            </button>

            <select
              className="case-select-note"
              value={selectedPuzzleId}
              disabled={busy}
              aria-label="Select Case File"
              onChange={(e) => onChangePuzzleId(e.target.value)}
            >
              {puzzles.map((p) => (
                <option key={p.id} value={p.id}>
                  [{p.category}] {p.id} ({p.size}x{p.size})
                </option>
              ))}
            </select>

            <button
              type="button"
              className="paper-tab"
              disabled={busy || !selectedPuzzleId}
              onClick={() => onLoadPuzzle(selectedPuzzleId)}
            >
              Open File
            </button>

            <button
              type="button"
              className="paper-tab"
              disabled={busy || !gameState}
              onClick={onRestart}
            >
              Reset Pins
            </button>
          </div>

          <div className="board-ribbon-right">
            <button
              type="button"
              className="paper-tab oracle-tab"
              disabled={busy || !gameState || gameState.solved}
              onClick={onHint}
            >
              <img
                className="oracle-mini-portrait"
                src={ASSETS.ui?.fortuneTeller?.path}
                alt=""
              />
              Oracle Hint
            </button>

            <button
              type="button"
              className="paper-tab primary"
              disabled={busy || !gameState || gameState.solved}
              onClick={onAutoSolve}
            >
              Auto-Deduce
            </button>

            <button type="button" className="paper-tab" onClick={onOpenLedger}>
              Ledger ({gameState?.trace?.length || 0})
            </button>

            {gameState && (
              <span className={`board-tally-slip ${gameState.solved ? "solved" : ""}`}>
                {gameState.revealed_count}/{gameState.total_count}
              </span>
            )}
          </div>
        </div>

        {/* Pinned Documents & SVG Evidence Strings */}
        <div className="board-surface-wrap" ref={surfaceRef}>
          <EvidenceConnections
            containerRef={surfaceRef}
            docRefs={docRefs}
            cards={gameState?.cards}
            selectedCell={selectedCell}
            visible={visible}
          />

          {gameState ? (
            <div
              className="board-documents-grid"
              style={{
                gridTemplateColumns: `24px repeat(${size}, minmax(0, 1fr))`,
              }}
            >
              <div />
              {colLabels.map((col) => (
                <div key={col} className="board-axis-note">
                  {col}
                </div>
              ))}

              {Array.from({ length: size }, (_, r) => {
                const rowNum = r + 1;
                const rowCards = gameState.cards.slice(r * size, (r + 1) * size);
                return (
                  <React.Fragment key={rowNum}>
                    <div className="board-axis-note">{rowNum}</div>
                    {rowCards.map((card) => (
                      <CharacterDocument
                        key={card.cell}
                        card={card}
                        isSelected={selectedCell === card.cell}
                        isHighlighted={highlightedSet.has(card.cell)}
                        isHintTarget={hintInfo?.cell === card.cell}
                        busy={busy}
                        docRef={(el) => {
                          if (el) docRefs.current[card.cell] = el;
                          else delete docRefs.current[card.cell];
                        }}
                        onSelectDocument={onSelectDocument}
                        onSubmitVerdict={onSubmitVerdict}
                      />
                    ))}
                  </React.Fragment>
                );
              })}
            </div>
          ) : (
            <p style={{ color: "var(--warm-cream)" }}>Pinning case records...</p>
          )}
        </div>

        {/* Quiet Contextual Pinned Dispatch Note */}
        {dispatch && (
          <div className={`board-dispatch-slip ${dispatch.type}`} role="status">
            <div className="board-dispatch-left">
              <img className="dispatch-thumb" src={getDispatchThumb(dispatch)} alt="" />
              <div>
                <strong>[{dispatch.title}]</strong> {dispatch.message}
              </div>
            </div>
            <button type="button" className="paper-tab" onClick={onDismissDispatch}>
              Acknowledge
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

/* ============================================================
   STATE A & B — DETECTIVE ROOM & CAMERA ZOOM CONTROLLER
   ============================================================ */
function RoomScene({
  viewState,
  gameState,
  onApproachBoard,
  onOpenLedger,
  onConsultOracle,
  onAutoDeduce,
}) {
  const isRoom = viewState === "ROOM";
  const size = gameState?.size || 3;

  return (
    <>
      <div className={`room-title-slip ${isRoom ? "" : "hidden"}`}>
        <h1>Griductive — Detective's Caseboard</h1>
        <p>
          {gameState
            ? `Case "${gameState.puzzle_id}" · ${gameState.revealed_count}/${gameState.total_count} unsealed · Click the board to examine`
            : "Opening detective's office..."}
        </p>
      </div>

      <div className={`room-canvas ${isRoom ? "" : "focused"}`}>
        <img
          className="env-layer env-background"
          src={ASSETS.environments?.detectiveOffice?.background?.path}
          alt="Detective's office"
        />

        {/* Physical Investigation Board Hotspot aligned with painted wall perspective */}
        <button
          type="button"
          className={`wall-board-hotspot size-${size} ${isRoom ? "" : "dimmed"}`}
          onClick={onApproachBoard}
          aria-label="Examine the investigation board"
        >
          {gameState && (
            <div
              className="wall-board-mini-grid"
              style={{
                gridTemplateColumns: `repeat(${size}, minmax(0, 1fr))`,
                gridTemplateRows: `repeat(${size}, minmax(0, 1fr))`,
              }}
            >
              {gameState.cards.map((card) => {
                const thumb = card.revealed ? getCharacterAsset(card) : null;
                const statusCls = card.revealed
                  ? card.known_status === "CRIMINAL"
                    ? "revealed criminal"
                    : "revealed innocent"
                  : "sealed";
                const stampGlyph = card.revealed
                  ? card.known_status === "CRIMINAL"
                    ? "✕"
                    : "✓"
                  : "?";
                return (
                  <div key={card.cell} className={`mini-pinned-note ${statusCls}`}>
                    <span className="mini-pin-dot" />
                    <div className="mini-note-head">
                      <span className="mini-note-code">{card.cell}</span>
                      <span className="mini-note-glyph">{stampGlyph}</span>
                    </div>
                    <div className="mini-note-body">
                      {card.revealed && thumb ? (
                        <div className="mini-thumb-frame">
                          <img className="mini-thumb" src={thumb} alt="" />
                        </div>
                      ) : (
                        <div className="mini-seal-box">
                          <span className="mini-seal">
                            {card.revealed ? getInitials(card.name) : "?"}
                          </span>
                        </div>
                      )}
                      <div className="mini-note-lines" aria-hidden="true">
                        <span className="mini-note-name">
                          {card.revealed ? card.name.split(" ")[0] : `FILE ${card.cell}`}
                        </span>
                        <span className="mini-ink-bar long" />
                        <span className="mini-ink-bar med" />
                        <span className="mini-ink-bar short">
                          {card.revealed && card.clue ? "→" : "·"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <span className="board-hover-tag">Approach Investigation Board</span>
        </button>

        <img
          className="env-layer env-midground"
          src={ASSETS.environments?.detectiveOffice?.midground?.path}
          alt=""
        />
        <img
          className="env-layer env-foreground"
          src={ASSETS.environments?.detectiveOffice?.foreground?.path}
          alt=""
        />

        {/* Room Object Hotspots (only interactive in Room View) */}
        {isRoom && (
          <>
            <button
              type="button"
              className="room-hotspot hotspot-phone"
              onClick={onConsultOracle}
              aria-label="Consult Fortune Teller on rotary phone"
            >
              <span className="hotspot-tooltip">Ask Oracle Hint</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-typewriter"
              onClick={onOpenLedger}
              aria-label="Open Case Ledger"
            >
              <span className="hotspot-tooltip">Open Case Ledger</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-folder"
              onClick={onApproachBoard}
              aria-label="Open Case Dossier on desk"
            >
              <span className="hotspot-tooltip">Inspect Case Board</span>
            </button>

            <button
              type="button"
              className="room-hotspot hotspot-magnifier"
              onClick={onAutoDeduce}
              aria-label="Run logical deduction with magnifying glass"
            >
              <span className="hotspot-tooltip">Auto-Deduce Case</span>
            </button>
          </>
        )}
      </div>
    </>
  );
}

/* ============================================================
   MAIN APP CONTROLLER (PRESERVES ALL GAME LOGIC & API FLOWS)
   ============================================================ */
function App() {
  const [viewState, setViewState] = useState("ROOM"); // "ROOM" | "TRANSITIONING" | "BOARD"
  const [puzzles, setPuzzles] = useState([]);
  const [selectedPuzzleId, setSelectedPuzzleId] = useState("");
  const [gameState, setGameState] = useState(null);
  const [selectedCell, setSelectedCell] = useState(null);
  const [openDossierCell, setOpenDossierCell] = useState(null);
  const [hintInfo, setHintInfo] = useState(null);
  const [dispatch, setDispatch] = useState(null);
  const [showLedger, setShowLedger] = useState(false);
  const [busy, setBusy] = useState(false);
  const transitionTimerRef = useRef(null);

  useEffect(() => {
    (async () => {
      try {
        const [puzzleRes, stateRes] = await Promise.all([
          apiFetch("/api/puzzles"),
          apiFetch("/api/game/state"),
        ]);
        setPuzzles(puzzleRes.puzzles || []);
        setGameState(stateRes);
        setSelectedPuzzleId(stateRes.puzzle_id);
      } catch (err) {
        setDispatch({ type: "CONTRADICTED", title: "ERROR", message: err.message });
      }
    })();
    return () => {
      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    };
  }, []);

  const enterBoardView = useCallback(() => {
    if (viewState === "BOARD") return;
    if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    setViewState("TRANSITIONING");
    transitionTimerRef.current = setTimeout(() => {
      setViewState("BOARD");
    }, 520);
  }, [viewState]);

  const returnToRoomView = useCallback(() => {
    if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    setOpenDossierCell(null);
    setViewState("ROOM");
  }, []);

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key !== "Escape") return;
      if (showLedger) {
        setShowLedger(false);
      } else if (openDossierCell) {
        setOpenDossierCell(null);
      } else if (viewState === "BOARD") {
        returnToRoomView();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [showLedger, openDossierCell, viewState, returnToRoomView]);

  const selectedClueCard = useMemo(() => {
    if (!gameState || !selectedCell) return null;
    return gameState.cards.find((c) => c.cell === selectedCell) || null;
  }, [gameState, selectedCell]);

  const openDossierCard = useMemo(() => {
    if (!gameState || !openDossierCell) return null;
    return gameState.cards.find((c) => c.cell === openDossierCell) || null;
  }, [gameState, openDossierCell]);

  const highlightedSet = useMemo(() => {
    const set = new Set();
    if (selectedClueCard?.revealed && selectedClueCard?.clue?.highlighted_cells) {
      selectedClueCard.clue.highlighted_cells.forEach((cid) => set.add(cid));
    } else if (hintInfo?.highlighted_cells) {
      hintInfo.highlighted_cells.forEach((cid) => set.add(cid));
    }
    return set;
  }, [selectedClueCard, hintInfo]);

  const handleLoadPuzzle = async (puzzleId) => {
    if (!puzzleId) return;
    setBusy(true);
    try {
      const state = await apiFetch("/api/game/load", {
        method: "POST",
        body: JSON.stringify({ puzzle_id: puzzleId }),
      });
      setGameState(state);
      setSelectedPuzzleId(state.puzzle_id);
      setSelectedCell(null);
      setOpenDossierCell(null);
      setHintInfo(null);
      setDispatch({
        type: "ACCEPTED",
        title: "CASE OPENED",
        message: `Loaded dossier "${state.puzzle_id}" (${state.size}x${state.size}).`,
      });
    } catch (err) {
      setDispatch({ type: "CONTRADICTED", title: "LOAD ERROR", message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleRestart = async () => {
    setBusy(true);
    try {
      const state = await apiFetch("/api/game/restart", { method: "POST" });
      setGameState(state);
      setSelectedCell(null);
      setOpenDossierCell(null);
      setHintInfo(null);
      setDispatch({
        type: "NOT_PROVABLE",
        title: "BOARD RESET",
        message: "Returned pinboard to initial revealed clues.",
      });
    } catch (err) {
      setDispatch({ type: "CONTRADICTED", title: "ERROR", message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleVerdict = async (cell, status) => {
    setBusy(true);
    try {
      const res = await apiFetch("/api/game/verdict", {
        method: "POST",
        body: JSON.stringify({ cell, status }),
      });
      setGameState(res.state);
      setHintInfo(null);
      if (res.newly_revealed) {
        setSelectedCell(res.newly_revealed);
      }
      setDispatch({
        type: res.outcome,
        title: res.outcome,
        message: res.message,
      });
    } catch (err) {
      setDispatch({ type: "CONTRADICTED", title: "ERROR", message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleHint = async () => {
    setBusy(true);
    try {
      const hint = await apiFetch("/api/game/hint");
      setHintInfo(hint);
      setSelectedCell(hint.relevant_clue_cell || hint.cell || null);
      setDispatch({
        type: hint.status === "INCONSISTENT" ? "CONTRADICTED" : "ACCEPTED",
        title: hint.status === "FOUND" ? "ORACLE LEAD" : hint.status,
        message: hint.message,
      });
      if (viewState === "ROOM") enterBoardView();
    } catch (err) {
      setDispatch({ type: "CONTRADICTED", title: "ERROR", message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleAutoSolve = async () => {
    setBusy(true);
    try {
      const res = await apiFetch("/api/game/auto-solve", { method: "POST" });
      setGameState(res.state);
      setHintInfo(null);
      setSelectedCell(null);
      const count = res.steps_added ? res.steps_added.length : 0;
      setDispatch({
        type: res.terminal_status === "SOLVED" ? "ACCEPTED" : "NOT_PROVABLE",
        title: `AUTO-DEDUCE: ${res.terminal_status}`,
        message:
          res.terminal_status === "SOLVED"
            ? `Case closed in ${count} logically entailed step(s).`
            : `Stopped (${res.terminal_status}) after ${count} step(s).`,
      });
      if (viewState === "ROOM") enterBoardView();
    } catch (err) {
      setDispatch({ type: "CONTRADICTED", title: "ERROR", message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleSelectDocument = (cell) => {
    setHintInfo(null);
    setSelectedCell(cell);
    setOpenDossierCell(cell);
  };

  return (
    <div className="game-viewport">
      <RoomScene
        viewState={viewState}
        gameState={gameState}
        onApproachBoard={enterBoardView}
        onOpenLedger={() => setShowLedger(true)}
        onConsultOracle={handleHint}
        onAutoDeduce={handleAutoSolve}
      />

      <InvestigationBoardScene
        visible={viewState === "BOARD"}
        puzzles={puzzles}
        selectedPuzzleId={selectedPuzzleId}
        onChangePuzzleId={setSelectedPuzzleId}
        onLoadPuzzle={handleLoadPuzzle}
        onRestart={handleRestart}
        onHint={handleHint}
        onAutoSolve={handleAutoSolve}
        onOpenLedger={() => setShowLedger(true)}
        onStepBack={returnToRoomView}
        gameState={gameState}
        selectedCell={selectedCell}
        highlightedSet={highlightedSet}
        hintInfo={hintInfo}
        dispatch={dispatch}
        onDismissDispatch={() => setDispatch(null)}
        onSelectDocument={handleSelectDocument}
        onSubmitVerdict={handleVerdict}
        busy={busy}
      />

      {viewState === "BOARD" && openDossierCard && (
        <CharacterDossier
          card={openDossierCard}
          allCards={gameState?.cards}
          busy={busy}
          onClose={() => setOpenDossierCell(null)}
          onSelectCell={(cid) => {
            setSelectedCell(cid);
            setOpenDossierCell(cid);
          }}
          onSubmitVerdict={handleVerdict}
        />
      )}

      {showLedger && (
        <div className="ledger-backdrop" onClick={() => setShowLedger(false)}>
          <div className="ledger-book" onClick={(e) => e.stopPropagation()}>
            <div className="ledger-header">
              <h2 style={{ margin: 0, fontFamily: "var(--font-serif)" }}>
                Investigation Ledger ({gameState?.trace?.length || 0} steps)
              </h2>
              <button type="button" className="paper-tab" onClick={() => setShowLedger(false)}>
                Close
              </button>
            </div>
            {gameState?.trace?.length ? (
              gameState.trace.map((item) => (
                <div key={item.step} className="ledger-entry">
                  <div>
                    <strong>
                      #{item.step} {item.cell} → {item.verdict}
                    </strong>{" "}
                    (Revealed: {item.newly_revealed_clue})
                  </div>
                  <div style={{ color: "var(--muted-olive)", fontSize: "0.73rem" }}>
                    Active clues: {item.active_clues.join(", ")}
                  </div>
                </div>
              ))
            ) : (
              <p>No verdicts recorded yet.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
