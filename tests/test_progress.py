"""Testes do progresso por fase."""

from forti_report.services.progress import ProgressReporter, overall_percent


def test_overall_percent_weights():
    assert overall_percent("faz", 0) == 0
    assert overall_percent("faz", 100) == 62
    assert overall_percent("hierarchy", 100) == 65
    assert overall_percent("pdf", 50) == 65 + 16
    assert overall_percent("finalize", 100) == 100


def test_progress_reporter_emits_phase_percent():
    events = []

    def cb(update):
        events.append(update)

    rep = ProgressReporter(cb)
    rep.emit(phase="pdf", step="pdf", message="Capa", phase_percent=10)
    assert len(events) == 1
    assert events[0].phase == "pdf"
    assert events[0].phase_percent == 10
    assert events[0].percent == overall_percent("pdf", 10)
