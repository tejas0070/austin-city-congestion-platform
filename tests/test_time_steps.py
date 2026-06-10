import pytest
from components.sidebar import slot_to_label, advance_step, MAX_SLOT


def test_slot_to_label_start():
    assert slot_to_label(0) == "12:00 AM"


def test_slot_to_label_end():
    assert slot_to_label(47) == "11:30 PM"


def test_slot_to_label_default():
    assert slot_to_label(34) == "5:00 PM"


def test_slot_to_label_midnight_half():
    assert slot_to_label(1) == "12:30 AM"


def test_slot_to_label_noon():
    assert slot_to_label(24) == "12:00 PM"


def test_all_labels_unique():
    labels = [slot_to_label(i) for i in range(MAX_SLOT + 1)]
    assert len(labels) == len(set(labels))


def test_max_slot_is_47():
    assert MAX_SLOT == 47


def test_advance_step_normal_increment():
    assert advance_step(34, True) == (35, True)


def test_advance_step_stop_at_max():
    assert advance_step(47, True) == (47, False)


def test_advance_step_noop_when_not_playing():
    assert advance_step(47, False) == (47, False)


def test_advance_step_idle_at_start():
    assert advance_step(0, False) == (0, False)


def test_advance_step_near_end():
    assert advance_step(46, True) == (47, True)
