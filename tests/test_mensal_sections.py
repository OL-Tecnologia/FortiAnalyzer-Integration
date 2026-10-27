"""Testes das seções Resumo Executivo e Segurança Ampliada."""

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table

from forti_report.data.hierarchy import AntennaInfo, RegionalUnit, build_regional_hierarchy
from forti_report.data.mensal_models import MensalGeralReport
from forti_report.data.models import UnitReport
from forti_report.data.parsers.mensal_utils import split_phishing_item
from forti_report.data.wan_models import RankedItem, WebUsageSummary
from forti_report.pdf.sections.resumo_executivo import (
    build_global_resumo_executivo_flowables,
    build_resumo_executivo_flowables,
)
from forti_report.pdf.sections.seguranca import build_seguranca_flowables


def _sample_mensal() -> MensalGeralReport:
    return MensalGeralReport(
        device_name="fw-sul-filial",
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
            RankedItem(
                rank=1,
                label="user.phish",
                value="2",
                percentage="100%",
                category="https://evil.com/",
            ),
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
    assert any("Top usuários bloqueados" in t or "bloqueados" in t.lower() for t in titles)

    flow_no_charts = build_seguranca_flowables(
        _sample_mensal(),
        width=400,
        styles=styles,
        anchor_prefix="t-",
        charts_enabled=False,
    )
    tables = [f for f in flow_no_charts if isinstance(f, Table)]
    assert tables

    def _cell_text(cell) -> str:
        return getattr(cell, "text", None) or str(cell)

    phishing_ok = False
    for table in tables:
        header = table._cellvalues[0] if table._cellvalues else []
        if len(header) == 5 and _cell_text(header[1]) == "Usuário" and _cell_text(header[2]) == "Site":
            phishing_ok = True
            break
    assert phishing_ok


def test_split_phishing_item():
    user, site = split_phishing_item(
        RankedItem(rank=1, label="172.16.1.1", value="3", category="https://evil.test/")
    )
    assert user == "172.16.1.1"
    assert site.startswith("https://")
    user2, site2 = split_phishing_item(
        RankedItem(rank=1, label="alice — bad.example", value="1")
    )
    assert user2 == "alice"
    assert site2 == "bad.example"


def test_seguranca_empty_when_no_security_data():
    styles = getSampleStyleSheet()
    empty = MensalGeralReport(device_name="fw-test")
    assert build_seguranca_flowables(empty, width=400, styles=styles) == []


def test_global_resumo_executivo_flowables():
    devices = [
        {"name": "fw-sul-filial", "ip": "1.1.1.1", "dev_status": 1, "platform_str": "FG-50G"},
    ]
    mensal = _sample_mensal()
    reports = {
        "fw-sul-filial": UnitReport(
            device_name="fw-sul-filial",
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
