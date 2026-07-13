"""Testes das seções Resumo Executivo e Segurança Ampliada."""

from reportlab.lib.styles import getSampleStyleSheet

from forti_report.data.hierarchy import AntennaInfo, RegionalUnit, build_regional_hierarchy
from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.models import UnitReport
from forti_report.data.wan_models import RankedItem, WebUsageSummary
from forti_report.pdf.sections.resumo_executivo import (
    build_global_resumo_executivo_flowables,
    build_resumo_executivo_flowables,
)
from forti_report.pdf.sections.seguranca import build_seguranca_flowables


def _sample_mensal() -> MensalGeralReport:
    return MensalGeralReport(
        device_name="fw-cas-cruz-azul-ambulatorio",
        summary=WebUsageSummary(
            allowed_requests="9000",
            blocked_requests="1000",
            users=42,
            categories=15,
            applications=80,
            malicious_sites=3,
        ),
        top_users_blocked=[
            RankedItem(rank=1, label="user.blocked", value="500", percentage="50%"),
        ],
        top_risk_users=[
            RankedItem(rank=1, label="user.risk", value="120", percentage="60%"),
        ],
        phishing_victims=[
            RankedItem(rank=1, label="user.phish — evil.com", value="2", percentage="100%"),
        ],
        blocked_usage_summary=[
            RankedItem(rank=1, label="user.cat", value="40", percentage="40%", category="Malware"),
        ],
        top_bandwidth_users=[
            RankedItem(rank=1, label="user.bw", value="10 GB", percentage="30%"),
        ],
    )


def test_resumo_executivo_flowables():
    styles = getSampleStyleSheet()
    flow = build_resumo_executivo_flowables(
        _sample_mensal(),
        width=400,
        styles=styles,
        anchor_prefix="cas-ambulatorio-",
    )
    assert len(flow) >= 4
    titles = [getattr(f, "text", "") for f in flow if hasattr(f, "text")]
    assert any("Resumo Executivo" in t for t in titles)
    assert any("Destaques" in t for t in titles)


def test_seguranca_flowables():
    styles = getSampleStyleSheet()
    flow = build_seguranca_flowables(
        _sample_mensal(),
        width=400,
        styles=styles,
        anchor_prefix="cas-ambulatorio-",
    )
    assert len(flow) >= 5
    titles = [getattr(f, "text", "") for f in flow if hasattr(f, "text")]
    assert any("Segurança Ampliada" in t for t in titles)
    assert any("Top usuários bloqueados" in t for t in titles)


def test_seguranca_empty_when_no_security_data():
    styles = getSampleStyleSheet()
    empty = MensalGeralReport(device_name="fw-test")
    assert build_seguranca_flowables(empty, width=400, styles=styles) == []


def test_global_resumo_executivo_flowables():
    devices = [
        {"name": "fw-cas-cruz-azul-ambulatorio", "ip": "1.1.1.1", "dev_status": 1, "platform_str": "FG-50G"},
    ]
    mensal = _sample_mensal()
    reports = {
        "fw-cas-cruz-azul-ambulatorio": UnitReport(
            device_name="fw-cas-cruz-azul-ambulatorio",
            display_name="Ambulatório",
            faz_tid="123",
            mensal=mensal,
        ),
    }
    units = build_regional_hierarchy(devices, reports)
    styles = getSampleStyleSheet()
    flow = build_global_resumo_executivo_flowables(units, width=400, styles=styles)
    assert flow
    titles = [getattr(f, "text", "") for f in flow if hasattr(f, "text")]
    assert any("Resumo Executivo — Visão Geral" in t for t in titles)
