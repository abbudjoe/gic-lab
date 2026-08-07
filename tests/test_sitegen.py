from __future__ import annotations

from giclab.sitegen import ROOT, build_experiments, build_falsification, build_status


def test_status_is_generated_from_zero_use_phase_state() -> None:
    page = build_status(ROOT)
    assert "Accelerator hours | 0" in page
    assert "Prototype runs | 0" in page
    assert "No prototype result has been reproduced" in page


def test_template_is_not_published_as_an_experiment() -> None:
    page = build_experiments(ROOT)
    assert "No registered experiments" in page
    assert "| EXP-0000 |" not in page


def test_falsification_page_projects_the_canonical_document() -> None:
    page = build_falsification(ROOT)
    assert "generated from `docs/FALSIFICATION_NOTES.md`" in page
    assert "Learned regulation is useful" in page
