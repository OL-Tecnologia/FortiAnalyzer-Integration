from forti_report.services.harvest import classify_report


def test_diario_nao_cai_no_mensal_de_configuracoes():
    daily = {
        "name": "RELATÓRIO DIÁRIO DE CONFIGURAÇÕES-FW_MATRIZ_01[root]-2026-10-12-0800-0300_1",
        "title": "RELATÓRIO DIÁRIO DE CONFIGURAÇÕES",
    }
    monthly = {
        "name": "MENSAL-RELATÓRIO MENSAL DE CONFIGURAÇÕES-FW_MATRIZ_01[root]-2026-10-09-0800-0300_2",
        "title": "MENSAL-RELATÓRIO MENSAL DE CONFIGURAÇÕES",
    }
    assert classify_report(daily).cycle == "diario"
    assert classify_report(monthly).cycle == "mensal"
    assert "CONFIGURAÇÕES" in classify_report(monthly).prefix


def test_wan_com_espaco_entra_no_prefixo_certo():
    report = {
        "name": "MENSAL- RELATÓRIO TRÁFEGO WAN-FW_MATRIZ_01[root]-2026-10-09-0800-0300_3",
        "title": "MENSAL- RELATÓRIO TRÁFEGO WAN",
    }
    layout = classify_report(report)
    assert layout is not None
    assert layout.cycle == "mensal"
    assert "WAN" in layout.prefix


def test_data_com_barra_nao_vira_subpasta():
    from forti_report.services.harvest import _file_stem, folder_name

    stem = _file_stem(
        "sem-dispositivo",
        {"period-end": "2026/10/13 08:00:00"},
        "3cc37fbc-aaaa",
    )
    assert "/" not in stem and "\\" not in stem
    assert "2026-10-13" in stem
    assert folder_name("RELATÓRIO DIÁRIO DE CONFIGURAÇÕES") == "RELATORIO_DIARIO_DE_CONFIGURACOES"


def test_relatorio_de_outro_layout_fica_de_fora():
    report = {
        "name": "REPORT MONITORAMENTO SYS ADMIN-2026-10-13-0800-0300_6267",
        "title": "REPORT MONITORAMENTO SYS ADMIN",
    }
    assert classify_report(report) is None
