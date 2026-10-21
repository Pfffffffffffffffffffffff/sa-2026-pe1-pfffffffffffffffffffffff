#!/usr/bin/env python3
"""Simulate the resident request backlog and render scenario charts from CSV inputs."""

import csv
import html
import math
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PARAMETERS_FILE = BASE_DIR / "lab6_parameters.csv"
RUNS_FILE = BASE_DIR / "lab6_runs.csv"
RESULTS_FILE = BASE_DIR / "lab6_results.csv"
BOUNDARY_FILE = BASE_DIR / "lab6_boundary.csv"
CHART_FILE = BASE_DIR / "lab6_scenarios.svg"

SCENARIOS = [
    ("Как есть", 1.0, 1.0),
    ("Нагрузка x2", 2.0, 1.0),
    ("Задержка x2", 1.0, 2.0),
]


def read_parameters():
    with PARAMETERS_FILE.open(encoding="utf-8-sig", newline="") as source:
        return {row["parameter"]: float(row["value"]) for row in csv.DictReader(source)}


def simulate(parameters, load_multiplier, delay_multiplier):
    dt = parameters["Time Step"]
    horizon = parameters["Simulation Horizon"]
    steps = round(horizon / dt)
    backlog = parameters["Initial Backlog"]
    arrival_rate = parameters["Base Arrival Rate"] * load_multiplier
    delay = parameters["Base Service Delay"] * delay_multiplier
    capacity = parameters["Inspection Capacity"]
    points = []

    for step in range(steps + 1):
        time = step * dt
        inspection_rate = min(backlog / delay, capacity)
        points.append((time, backlog, arrival_rate, inspection_rate))
        if step < steps:
            backlog = max(0.0, backlog + (arrival_rate - inspection_rate) * dt)

    return points


def write_outputs(parameters, scenario_points):
    with RUNS_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["scenario", "time_day", "backlog_requests", "arrival_rate_per_day", "inspection_rate_per_day"])
        for name, points in scenario_points:
            for time, backlog, arrivals, inspections in points:
                writer.writerow([name, f"{time:.2f}", f"{backlog:.4f}", f"{arrivals:.4f}", f"{inspections:.4f}"])

    base_arrival = parameters["Base Arrival Rate"]
    capacity = parameters["Inspection Capacity"]
    critical_multiplier = capacity / base_arrival

    with RESULTS_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["scenario", "arrival_rate_per_day", "capacity_per_day", "final_backlog", "max_backlog", "equilibrium_backlog_if_stable", "behaviour"])
        for name, points in scenario_points:
            arrivals = points[0][2]
            final_backlog = points[-1][1]
            max_backlog = max(point[1] for point in points)
            stable = arrivals <= capacity
            equilibrium = arrivals * parameters["Base Service Delay"] * (2.0 if name == "Задержка x2" else 1.0) if stable else ""
            behaviour = "bounded; approaches equilibrium" if stable else f"unbounded in model; backlog grows about {arrivals - capacity:.2f} requests/day after capacity saturates"
            writer.writerow([name, f"{arrivals:.4f}", f"{capacity:.4f}", f"{final_backlog:.4f}", f"{max_backlog:.4f}", f"{equilibrium:.4f}" if stable else "", behaviour])

    with BOUNDARY_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["parameter", "critical_value", "units", "stable_side", "unstable_side", "derivation"])
        writer.writerow(["Load Multiplier", f"{critical_multiplier:.4f}", "dimensionless", f"<= {critical_multiplier:.4f}: bounded", f"> {critical_multiplier:.4f}: growing backlog", "Inspection Capacity / Base Arrival Rate"])


def render_chart(parameters, scenario_points):
    width = 1200
    panel_height = 220
    top = 125
    left = 105
    right = 1150
    chart_width = right - left
    horizon = parameters["Simulation Horizon"]
    colors = ["#16803c", "#d97706", "#2563eb"]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="850" viewBox="0 0 {width} 850" role="img" aria-labelledby="title desc">',
        '<title id="title">Сценарии очереди заявок на осмотр</title>',
        '<desc id="desc">Графики очереди для базового сценария, удвоенной нагрузки и удвоенной задержки, построенные из lab6_runs.csv.</desc>',
        '<style>text{font-family:Arial,sans-serif;fill:#172554}.axis{stroke:#64748b;stroke-width:1}.grid{stroke:#e2e8f0;stroke-width:1}.tick{font-size:12px;fill:#475569}.curve{fill:none;stroke-width:3}.legend{font-size:13px}</style>',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="38" y="42" font-size="24" font-weight="700">Очередь заявок на осмотр: три прогона</text>',
        '<text x="38" y="68" font-size="13" fill="#92400e">Иллюстративные допущения; фактические потоки и мощность УК не измерялись.</text>',
    ]

    for index, ((name, points), color) in enumerate(zip(scenario_points, colors)):
        panel_top = top + index * panel_height
        baseline_y = panel_top + 165
        max_value = max(point[1] for point in points)
        y_max = max(10.0, math.ceil(max_value / 10.0) * 10.0)
        plot_height = 145
        lines.append(f'<text x="{left}" y="{panel_top - 8}" font-size="16" font-weight="700">{html.escape(name)}: очередь</text>')

        for tick_index in range(4):
            value = y_max * tick_index / 3
            y = baseline_y - plot_height * tick_index / 3
            lines.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}"/>')
            lines.append(f'<text class="tick" x="{left - 42}" y="{y + 4:.2f}">{value:.0f}</text>')

        lines.append(f'<line class="axis" x1="{left}" y1="{panel_top + 20}" x2="{left}" y2="{baseline_y}"/>')
        lines.append(f'<line class="axis" x1="{left}" y1="{baseline_y}" x2="{right}" y2="{baseline_y}"/>')
        for time_tick in (0, 10, 20, 30):
            x = left + chart_width * time_tick / horizon
            lines.append(f'<line class="grid" x1="{x:.2f}" y1="{panel_top + 20}" x2="{x:.2f}" y2="{baseline_y}"/>')
            lines.append(f'<text class="tick" x="{x - 8:.2f}" y="{baseline_y + 18}">{time_tick}</text>')

        coordinates = []
        for time, backlog, _, _ in points:
            x = left + chart_width * time / horizon
            y = baseline_y - plot_height * backlog / y_max
            coordinates.append(f"{x:.2f},{y:.2f}")
        lines.append(f'<polyline class="curve" stroke="{color}" points="{" ".join(coordinates)}"/>')
        lines.append(f'<text class="tick" x="{right - 90}" y="{baseline_y + 35}">дни</text>')

    lines.extend([
        '<text x="38" y="830" font-size="12" fill="#475569">Начальный backlog одинаков во всех сценариях; кривые построены скриптом из расчётных рядов.</text>',
        '</svg>',
    ])
    CHART_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parameters = read_parameters()
    scenario_points = [
        (name, simulate(parameters, load_multiplier, delay_multiplier))
        for name, load_multiplier, delay_multiplier in SCENARIOS
    ]
    write_outputs(parameters, scenario_points)
    render_chart(parameters, scenario_points)
    critical_multiplier = parameters["Inspection Capacity"] / parameters["Base Arrival Rate"]
    print(f"Критический Load Multiplier: {critical_multiplier:.2f}")
    for name, points in scenario_points:
        print(f"{name}: backlog {points[0][1]:.2f} -> {points[-1][1]:.2f} заявок")
    print(f"Созданы: {RUNS_FILE.name}, {RESULTS_FILE.name}, {BOUNDARY_FILE.name}, {CHART_FILE.name}")


if __name__ == "__main__":
    main()
