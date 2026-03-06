#!/usr/bin/env python3
"""Calcula KPIs de receipts por janela de ciclos e gera relatório markdown com semáforo."""
"""Calcula KPIs de receipts (24h/7d) e gera relatório markdown com semáforo."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def percentile_p95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    values_sorted = sorted(values)
    idx = ceil(0.95 * len(values_sorted)) - 1
    idx = max(0, min(idx, len(values_sorted) - 1))
    return float(values_sorted[idx])


def score_semph(value: Optional[float], green_cond, yellow_cond) -> Tuple[str, str]:
    if value is None:
        return ("⚪", "sem dados")
    if green_cond(value):
        return ("🟢", "verde")
    if yellow_cond(value):
        return ("🟡", "amarelo")
    return ("🔴", "vermelho")


@dataclass
class WindowResult:
    label: str
    start: datetime
    end: datetime
    cycles: int
    pct_in_db: Optional[float]
    pct_fallback: Optional[float]
    latency_p95_ms: Optional[float]
    telemetry_coverage_pct: Optional[float]
    sem_in_db: Tuple[str, str]
    sem_fallback: Tuple[str, str]
    sem_latency: Tuple[str, str]
    sem_coverage: Tuple[str, str]
    window_color: str


def _last_n_by_cycle(rows: List[Dict[str, Any]], n: int, cycle_key: str = "cycle_number") -> List[Dict[str, Any]]:
    valid_rows = [r for r in rows if isinstance(r.get(cycle_key), int)]
    sorted_rows = sorted(valid_rows, key=lambda r: r[cycle_key], reverse=True)
    return sorted_rows[:n]


def compute_window(
    label: str,
    window_cycles: int,
    cycle_rows: List[Dict[str, Any]],
    receipt_rows: List[Dict[str, Any]],
) -> WindowResult:
    cycle_w = _last_n_by_cycle(cycle_rows, window_cycles)
    cycles = len(cycle_w)
    selected_cycles = {r.get("cycle_number") for r in cycle_w}
def compute_window(
    label: str,
    now: datetime,
    hours: int,
    cycle_rows: List[Dict[str, Any]],
    receipt_rows: List[Dict[str, Any]],
) -> WindowResult:
    start = now - timedelta(hours=hours)

    cycle_w = [r for r in cycle_rows if (parse_iso(r.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= start]
    cycles = len(cycle_w)

    if cycles:
        fallback_cycles = sum(1 for r in cycle_w if bool(r.get("fallback_active")))
        pct_fallback = round((fallback_cycles / cycles) * 100, 2)
        pct_in_db = round(((cycles - fallback_cycles) / cycles) * 100, 2)
    else:
        pct_fallback = None
        pct_in_db = None

    rec_w = [
        r for r in receipt_rows
        if isinstance(r.get("cycle_number"), int) and r.get("cycle_number") in selected_cycles
    ]
    rec_w = [r for r in receipt_rows if (parse_iso(r.get("finished_at") or r.get("started_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= start]

    latencies = [float(r.get("latency_ms")) for r in rec_w if isinstance(r.get("latency_ms"), (int, float))]
    latency_p95 = percentile_p95(latencies)

    if rec_w:
        required_fields = ["tool", "status", "latency_ms", "final_url", "chars_captured"]
        complete = sum(1 for r in rec_w if all(r.get(k) not in (None, "") for k in required_fields))
        complete = 0
        for r in rec_w:
            if all(r.get(k) not in (None, "") for k in required_fields):
                complete += 1
        telemetry_coverage = round((complete / len(rec_w)) * 100, 2)
    else:
        telemetry_coverage = None

    sem_in_db = score_semph(
        pct_in_db,
        green_cond=lambda v: v >= 99,
        yellow_cond=lambda v: 95 <= v < 99,
    )
    sem_fallback = score_semph(
        pct_fallback,
        green_cond=lambda v: v <= 1,
        yellow_cond=lambda v: 1 < v <= 5,
    )
    sem_latency = score_semph(
        latency_p95,
        green_cond=lambda v: v <= 1500,
        yellow_cond=lambda v: 1500 < v <= 2500,
    )
    sem_coverage = score_semph(
        telemetry_coverage,
        green_cond=lambda v: v >= 99,
        yellow_cond=lambda v: 95 <= v < 99,
    )

    colors = [sem_in_db[1], sem_fallback[1], sem_latency[1], sem_coverage[1]]
    if "vermelho" in colors:
        window_color = "🔴"
    elif "amarelo" in colors:
        window_color = "🟡"
    elif "verde" in colors:
        window_color = "🟢"
    else:
        window_color = "⚪"

    return WindowResult(
        label=label,
        start=start,
        end=now,
        cycles=cycles,
        pct_in_db=pct_in_db,
        pct_fallback=pct_fallback,
        latency_p95_ms=latency_p95,
        telemetry_coverage_pct=telemetry_coverage,
        sem_in_db=sem_in_db,
        sem_fallback=sem_fallback,
        sem_latency=sem_latency,
        sem_coverage=sem_coverage,
        window_color=window_color,
    )


def fmt(v: Optional[float], suffix: str = "") -> str:
    if v is None:
        return "sem dados"
    if float(v).is_integer():
        return f"{int(v)}{suffix}"
    return f"{v:.2f}{suffix}"


def conclusion(results: List[WindowResult]) -> str:
    colors = [r.window_color for r in results]
    if all(c == "🟢" for c in colors):
        return "eficaz"
    if all(c in {"🔴", "⚪"} for c in colors):
        return "não eficaz"
    return "parcialmente eficaz"


def render_report(results: List[WindowResult], final_conclusion: str, cycle_file: Path, receipt_file: Path) -> str:
    lines = [
        "# Relatório de Avaliação de Eficiência e Eficácia — execution_receipts",
        "",
        f"- Arquivo de ciclos: `{cycle_file}`",
        f"- Arquivo de receipts: `{receipt_file}`",
        f"- Conclusão automática: **{final_conclusion}**",
        "",
        "## Semáforo por janela",
        "",
        "| Janela | Semáforo | % ciclos com receipts no banco | % fallback local | p95 latência persistência (ms) | cobertura telemetria | ciclos analisados |",
        "| Janela | Semáforo | % ciclos com receipts no banco | % fallback local | p95 latência persistência (ms) | cobertura telemetria | ciclos |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]

    for r in results:
        lines.append(
            "| "
            f"{r.label} | {r.window_color} | "
            f"{r.sem_in_db[0]} {fmt(r.pct_in_db, '%')} | "
            f"{r.sem_fallback[0]} {fmt(r.pct_fallback, '%')} | "
            f"{r.sem_latency[0]} {fmt(r.latency_p95_ms)} | "
            f"{r.sem_coverage[0]} {fmt(r.telemetry_coverage_pct, '%')} | "
            f"{r.cycles} |"
        )

    lines.extend([
        "",
        "## Regras da conclusão automática",
        "",
        "- **eficaz**: todas as janelas em verde.",
        "- **parcialmente eficaz**: mistura de verde/amarelo/vermelho.",
        "- **não eficaz**: todas as janelas em vermelho ou sem dados suficientes.",
        "- **eficaz**: janelas 24h e 7d em verde.",
        "- **parcialmente eficaz**: mistura de verde/amarelo/vermelho, sem falha total nas duas janelas.",
        "- **não eficaz**: ambas as janelas em vermelho ou sem dados suficientes para comprovar melhora.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Avalia KPIs de execution_receipts por número de ciclos")
    parser.add_argument("--cycle-metrics", default="receipts_cycle_metrics.jsonl", help="JSONL com métricas por ciclo")
    parser.add_argument("--receipts", default="execution_receipts.jsonl", help="JSONL com receipts")
    parser.add_argument("--window-cycles", type=int, default=5, help="Quantidade de ciclos na janela de análise")
    parser.add_argument("--output", default="RELATORIO_AVALIACAO_RECEIPTS.md", help="Arquivo markdown de saída")
    args = parser.parse_args()

    parser = argparse.ArgumentParser(description="Avalia KPIs de execution_receipts e gera relatório markdown")
    parser.add_argument("--cycle-metrics", default="receipts_cycle_metrics.jsonl", help="JSONL com métricas por ciclo")
    parser.add_argument("--receipts", default="execution_receipts.jsonl", help="JSONL com receipts")
    parser.add_argument("--output", default="RELATORIO_AVALIACAO_RECEIPTS.md", help="Arquivo markdown de saída")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    cycle_file = Path(args.cycle_metrics)
    receipt_file = Path(args.receipts)

    cycle_rows = read_jsonl(cycle_file)
    receipt_rows = read_jsonl(receipt_file)

    windows = [
        compute_window(f"últimos {args.window_cycles} ciclos", args.window_cycles, cycle_rows, receipt_rows),
        compute_window("24h", now, 24, cycle_rows, receipt_rows),
        compute_window("7d", now, 24 * 7, cycle_rows, receipt_rows),
    ]
    final_conclusion = conclusion(windows)

    md = render_report(windows, final_conclusion, cycle_file, receipt_file)
    Path(args.output).write_text(md + "\n", encoding="utf-8")

    print(f"[OK] Relatório gerado em: {args.output}")
    print(f"[OK] Conclusão automática: {final_conclusion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
