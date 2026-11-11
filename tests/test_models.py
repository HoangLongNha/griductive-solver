from dataclasses import FrozenInstanceError

import pytest

from griductive import models as m


def test_ct01_shared_types_and_fake_port():
    cnf = m.CNF(((1,),), 1, 1)
    result = m.SATResult(True, {1: True}, m.SATStats(0, 1, 0, 0.0))
    assert cnf.clauses == ((1,),)
    assert result.assignment == {1: True}
    assert m.Status.CRIMINAL.value == m.Inference.CRIMINAL.value
    assert len(m.VerdictStatus) == 4

    class FakeOracle:
        def classify_one(self, state, cell):
            return m.Inference.UNKNOWN

    oracle: m.VerdictOracle = FakeOracle()
    assert oracle.classify_one(m.PublicState('test', 3, ()), 'A1') is m.Inference.UNKNOWN


@pytest.mark.parametrize('size', [3, 4])
def test_ct02_row_major(size):
    cells = [f'{chr(65+c)}{r+1}' for r in range(size) for c in range(size)]
    assert [m.cell_to_var(cell, size) for cell in cells] == list(range(1, size*size+1))
    assert [m.var_to_cell(var, size) for var in range(1, size*size+1)] == cells


@pytest.mark.parametrize('cell', ['A0', 'D1', 'A4', 'a1', 'A01', 'B-1'])
def test_mapping_rejects_invalid_cell(cell):
    with pytest.raises(ValueError):
        m.cell_to_var(cell, 3)


@pytest.mark.parametrize('var', [0, -1, 10, True])
def test_mapping_rejects_auxiliary_or_invalid_variable(var):
    with pytest.raises(ValueError):
        m.var_to_cell(var, 3)


def test_ct04_face_down_privacy():
    card = m.PublicCard('A1', 'Alice', 'Detective', False, None, None)
    assert card.known_status is card.clue is None
    with pytest.raises(FrozenInstanceError):
        card.revealed = True
    with pytest.raises(ValueError):
        m.PublicCard('A1', 'Alice', 'Detective', False, m.Status.CRIMINAL, None)
    with pytest.raises(ValueError):
        m.PublicCard('A1', 'Alice', 'Detective', False, None, m.Clue('c', 'FACT', {}))


def test_snapshot_clue_data_is_detached_and_recursively_immutable():
    data = {'region': {'cells': ['A1', 'B1']}}
    first = m.Clue('c', 'EXACTLY', data)
    second = m.Clue('c', 'EXACTLY', data)
    data['region']['cells'].append('C1')
    assert first.data['region']['cells'] == second.data['region']['cells'] == ('A1', 'B1')
    with pytest.raises(TypeError):
        first.data['region']['cells'] = ()


def test_unfinished_queries_are_not_sat_results():
    assert issubclass(m.SolverTimeout, TimeoutError)
    assert not issubclass(m.SolverCancelled, m.SolverTimeout)
