from __future__ import annotations

from giclab.sitegen import ROOT, build_experiments, build_falsification, build_status


def test_status_is_generated_from_phase_one_zero_authority_state() -> None:
    page = build_status(ROOT)
    prose = " ".join(page.split())
    assert "`docs/exec-plans/`" in page
    assert "Phase 1 is the active control-plane phase" in page
    assert "| 0.5 | GIC Reading Reconciliation |" in page
    assert "| 0.75 | Upstream Audit, Harness, and Protocol Lock |" in page
    assert "Accelerator hours | 0" in page
    assert "Prototype runs | 0" in page
    assert "Paid compute allowed | `false`" in page
    assert "Cloud mutation allowed | `false`" in page
    assert "proposed budget is not execution authorization" in prose


def test_registered_experiment_is_published_and_template_is_not() -> None:
    page = build_experiments(ROOT)
    assert "| EXP-0001 | SiRA simulative versus matched reactive behavior |" in page
    assert "planned" in page
    assert "not-evaluated" in page
    assert "pending" in page
    assert "| EXP-0000 |" not in page


def test_falsification_page_projects_the_canonical_document() -> None:
    page = build_falsification(ROOT)
    assert "generated from `docs/FALSIFICATION_NOTES.md`" in page
    assert "Learned regulation is useful" in page
