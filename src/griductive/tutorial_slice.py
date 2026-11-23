"""Small Tkinter view for exercising the tutorial's first real proof and reveal."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from griductive.game.controller import Controller, VerdictTrace
from griductive.models import PublicCard, PublicState, Status, SubmitResult


def _describe(card: PublicCard) -> str:
    clue = card.clue
    if clue is None:
        return f'{card.cell}: Hidden clue'
    if clue.kind == 'FACT':
        meaning = f"{clue.data['cell']} is {clue.data['status']}."
    elif clue.kind == 'SAME':
        a, b = clue.data['cells']
        meaning = f'{a} and {b} have the same status.'
    else:
        meaning = f'{clue.kind} {dict(clue.data)}'
    return f'{clue.id}  {clue.kind}\n{meaning}'


class SliceView:
    """Render public result snapshots on the Tk thread, one command at a time."""

    def __init__(self, root: tk.Tk, puzzle_path: Path) -> None:
        self.root = root
        self.state: PublicState | None = None
        self.last_trace: VerdictTrace | None = None
        self.selected: str | None = None
        self.cards: dict[str, ttk.Button] = {}
        self.busy = False
        self._controller = Controller()
        self._commands = ThreadPoolExecutor(max_workers=1)
        self._poll_id: str | None = None
        root.title('Griductive | Tutorial 3×3')
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.columnconfigure(0, weight=1)

        panel = ttk.Frame(root, padding=16)
        panel.grid(sticky='nsew')
        panel.columnconfigure(0, weight=1)
        toolbar = ttk.Frame(panel)
        toolbar.grid(sticky='w')
        self.load_button = ttk.Button(toolbar, text='Load tutorial',
                                      command=lambda: self._run(self._controller.load, puzzle_path))
        self.step_button = ttk.Button(toolbar, text='Prove one move',
                                      command=lambda: self._run(self._controller.step))
        self.restart_button = ttk.Button(toolbar, text='Restart',
                                         command=lambda: self._run(self._controller.restart))
        for button in (self.load_button, self.step_button, self.restart_button):
            button.pack(side='left', padx=(0, 8))

        self.board = ttk.Frame(panel, padding=(0, 12))
        self.board.grid(sticky='ew')
        self.clue_text = tk.StringVar(value='Load the tutorial to view its first clue.')
        clue_panel = ttk.LabelFrame(panel, text='Selected clue', padding=8)
        clue_panel.grid(sticky='ew')
        ttk.Label(clue_panel, textvariable=self.clue_text, wraplength=490).pack(anchor='w')

        verdicts = ttk.Frame(panel, padding=(0, 8))
        verdicts.grid(sticky='w')
        self.verdict_buttons = {}
        for status in Status:
            button = ttk.Button(verdicts, text=f'Submit {status.value.title()}',
                                command=lambda value=status: self._submit(value))
            button.pack(side='left', padx=(0, 8))
            self.verdict_buttons[status] = button
        self.result_text = tk.StringVar()
        ttk.Label(panel, textvariable=self.result_text, wraplength=490).grid(sticky='w')
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.load_button.configure(state='disabled' if self.busy else 'normal')
        loaded = self.state is not None and not self.busy
        self.restart_button.configure(state='normal' if loaded else 'disabled')
        has_hidden = loaded and any(not card.revealed for card in self.state.cards)
        self.step_button.configure(state='normal' if has_hidden else 'disabled')
        selected_hidden = has_hidden and any(
            card.cell == self.selected and not card.revealed for card in self.state.cards
        )
        for button in self.verdict_buttons.values():
            button.configure(state='normal' if selected_hidden else 'disabled')
        for button in self.cards.values():
            button.configure(state='disabled' if self.busy else 'normal')

    def _select(self, card: PublicCard) -> None:
        self.selected = card.cell
        self.clue_text.set(_describe(card))
        self._sync_buttons()

    def _render(self, state: PublicState, selected: str | None) -> None:
        self.state = state
        for widget in self.board.winfo_children():
            widget.destroy()
        self.cards.clear()
        for index, card in enumerate(state.cards):
            label = card.known_status.value if card.revealed and card.known_status else 'Face down'
            button = ttk.Button(self.board, width=23,
                                text=f'{card.cell}  {card.name}\n{card.profession} · {label}',
                                command=lambda current=card: self._select(current))
            row, column = divmod(index, state.size)
            button.grid(row=row, column=column, sticky='ew', padx=3, pady=3, ipady=8)
            self.cards[card.cell] = button
        default = next((card for card in state.cards if card.revealed), state.cards[0])
        self._select(next((card for card in state.cards if card.cell == selected), default))

    def _submit(self, status: Status) -> None:
        if self.selected is not None:
            self._run(self._controller.submit_verdict, self.selected, status)

    def _run(self, command, *args) -> None:
        if self.busy:
            return
        self.busy = True
        self._sync_buttons()

        def execute():
            result = command(*args)
            return result, self._controller.last_trace

        future = self._commands.submit(execute)

        def poll():
            if not future.done():
                self._poll_id = self.root.after(15, poll)
                return
            self._poll_id = None
            self.busy = False
            try:
                result, self.last_trace = future.result()
                if isinstance(result, SubmitResult):
                    self._render(result.state, result.newly_revealed or self.selected)
                    message = result.message
                    if self.last_trace is not None:
                        trace = self.last_trace
                        message = f'{trace.cell} {trace.verdict.value} · {len(trace.queries)} SAT queries'
                        if trace.newly_revealed_clue_id:
                            message += f' · Revealed {trace.newly_revealed_clue_id}'
                    self.result_text.set(f'{result.outcome.value} · {message}')
                else:
                    self._render(result, None)
                    self.result_text.set('Initial clues ready')
            except Exception as exc:
                self.result_text.set(f'Action failed ({type(exc).__name__})')
            finally:
                self._sync_buttons()

        self._poll_id = self.root.after(0, poll)

    def close(self) -> None:
        if self._poll_id is not None:
            self.root.after_cancel(self._poll_id)
        self._commands.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('puzzle', nargs='?', type=Path,
                        default=Path('puzzles/3x3/tutorial_3x3.json'))
    args = parser.parse_args()
    root = tk.Tk()
    SliceView(root, args.puzzle)
    root.mainloop()


if __name__ == '__main__':
    main()
