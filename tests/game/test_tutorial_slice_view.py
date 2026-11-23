from pathlib import Path
from time import monotonic, sleep

import pytest

from griductive.models import Status


def wait_for_action(root, view):
    deadline = monotonic() + 5
    while view.busy and monotonic() < deadline:
        root.update()
        sleep(0.01)
    assert not view.busy
    root.update()


def test_tkinter_slice_renders_only_revealed_clues():
    tk = pytest.importorskip('tkinter')
    from griductive.tutorial_slice import SliceView

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f'Tk display unavailable: {exc}')
    puzzle = Path(__file__).resolve().parents[2] / 'puzzles/3x3/tutorial_3x3.json'
    view = SliceView(root, puzzle)
    try:
        view.load_button.invoke()
        wait_for_action(root, view)
        assert 'c-A1' in view.clue_text.get()
        view.cards['C1'].invoke()
        assert 'Hidden' in view.clue_text.get()
        view.verdict_buttons[Status.INNOCENT].invoke()
        wait_for_action(root, view)
        assert 'NOT_PROVABLE' in view.result_text.get()
        assert 'Face down' in view.cards['C1'].cget('text')

        view.cards['B1'].invoke()
        view.verdict_buttons[Status.CRIMINAL].invoke()
        wait_for_action(root, view)
        assert 'CONTRADICTED' in view.result_text.get()
        assert 'Face down' in view.cards['B1'].cget('text')

        view.step_button.invoke()
        wait_for_action(root, view)
        assert 'ACCEPTED' in view.result_text.get()
        assert 'INNOCENT' in view.cards['B1'].cget('text')
        assert 'c-B1' in view.clue_text.get()
        assert 'Face down' in view.cards['C1'].cget('text')

        view.restart_button.invoke()
        wait_for_action(root, view)
        assert 'Face down' in view.cards['B1'].cget('text')
        assert 'c-A1' in view.clue_text.get()
    finally:
        view.close()
