#!/usr/bin/env python3
"""Calculate graph degrees, test node failures, and render an SVG from CSV data."""

import csv
import html
from collections import defaultdict, deque
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
MATRIX_FILE = BASE_DIR / "lab4_adjacency.csv"
EDGES_FILE = BASE_DIR / "lab4_edges.csv"
DEGREES_FILE = BASE_DIR / "lab4_degrees.csv"
FAILURES_FILE = BASE_DIR / "lab4_failures.csv"
TIMING_INPUT_FILE = BASE_DIR / "lab4_timing_assumptions.csv"
TIMING_OUTPUT_FILE = BASE_DIR / "lab4_failure_timing.csv"
GRAPH_FILE = BASE_DIR / "lab4_graph.svg"

DISPLAY_NAMES = {
    "resident": "Житель",
    "dispatcher": "Диспетчер",
    "requests": "Реестр заявок",
    "uk": "Управляющая компания",
}

POSITIONS = {
    "resident": (185, 350),
    "dispatcher": (490, 350),
    "requests": (795, 350),
    "uk": (1100, 350),
}

EDGE_LAYOUT = {
    ("resident", "dispatcher"): ("M 270 338 C 330 255 420 255 478 338", 374, 273),
    ("dispatcher", "requests"): ("M 575 338 C 635 255 725 255 783 338", 679, 273),
    ("requests", "uk"): ("M 880 338 C 940 255 1030 255 1088 338", 984, 273),
    ("uk", "requests"): ("M 1088 362 C 1030 445 940 445 880 362", 984, 435),
    ("requests", "dispatcher"): ("M 783 362 C 725 445 635 445 575 362", 679, 435),
    ("dispatcher", "resident"): ("M 478 362 C 420 445 330 445 270 362", 374, 435),
}

MISSION_ROUTES = {
    "intake": ("resident", "uk"),
    "response": ("uk", "resident"),
}


def read_inputs():
    with MATRIX_FILE.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        nodes = reader.fieldnames[1:]
        matrix_rows = list(reader)

    if not nodes or len(nodes) != len(set(nodes)):
        raise ValueError("Matrix must have unique node columns.")
    if [row["node"] for row in matrix_rows] != nodes:
        raise ValueError("Matrix row labels must match column order.")

    matrix = {}
    for row in matrix_rows:
        values = {node: int(row[node]) for node in nodes}
        if any(value not in (0, 1) for value in values.values()):
            raise ValueError("This script expects a binary adjacency matrix (0/1).")
        matrix[row["node"]] = values

    with EDGES_FILE.open(encoding="utf-8-sig", newline="") as source:
        edge_rows = list(csv.DictReader(source))

    edge_map = {}
    for edge in edge_rows:
        pair = (edge["source"], edge["target"])
        if pair in edge_map:
            raise ValueError(f"Duplicate edge: {pair}")
        if pair[0] not in nodes or pair[1] not in nodes:
            raise ValueError(f"Unknown node in edge: {pair}")
        edge_map[pair] = edge

    matrix_edges = {
        (source, target)
        for source in nodes
        for target in nodes
        if matrix[source][target]
    }
    if matrix_edges != set(edge_map):
        raise ValueError("Adjacency matrix and edge list describe different graphs.")

    for mission, (source, target) in MISSION_ROUTES.items():
        if not any(edge["mission"] == mission for edge in edge_rows):
            raise ValueError(f"No edges are marked for mission route: {mission}")
        if source not in nodes or target not in nodes:
            raise ValueError(f"Mission route references an unknown node: {mission}")

    return nodes, matrix, edge_rows, edge_map


def write_degrees(nodes, matrix):
    with DEGREES_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["node", "in_degree", "out_degree", "total_degree"])
        for node in nodes:
            out_degree = sum(matrix[node].values())
            in_degree = sum(matrix[source][node] for source in nodes)
            writer.writerow([node, in_degree, out_degree, in_degree + out_degree])


def has_path(nodes, edges, mission, source, target, removed=None):
    if source == removed or target == removed:
        return False

    adjacency = defaultdict(list)
    for edge in edges:
        if edge["mission"] == mission:
            adjacency[edge["source"]].append(edge["target"])

    queue = deque([source])
    visited = {source}
    while queue:
        current = queue.popleft()
        if current == target:
            return True
        for neighbor in adjacency[current]:
            if neighbor != removed and neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False


def write_failure_tests(nodes, edges):
    candidates = [node for node in nodes if node != "resident"]

    with FAILURES_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            ["removed_node", "intake_path", "response_path", "system_operational", "result"]
        )
        for removed in candidates:
            route_results = {
                mission: has_path(nodes, edges, mission, *route, removed=removed)
                for mission, route in MISSION_ROUTES.items()
            }
            operational = all(route_results.values())
            result = "Критическая точка отказа" if not operational else "Функция сохраняется"
            writer.writerow(
                [
                    removed,
                    str(route_results["intake"]).lower(),
                    str(route_results["response"]).lower(),
                    str(operational).lower(),
                    result,
                ]
            )


def write_failure_timing(nodes):
    with TIMING_INPUT_FILE.open(encoding="utf-8-sig", newline="") as source:
        assumptions = list(csv.DictReader(source))

    with TIMING_OUTPUT_FILE.open("w", encoding="utf-8", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(
            [
                "failure_node",
                "detect_after_min",
                "survives_hours",
                "surviving_activity",
                "activity_outlasts_detection_min",
                "basis",
            ]
        )
        for row in assumptions:
            node = row["failure_node"]
            if node not in nodes:
                raise ValueError(f"Unknown failure node in timing assumptions: {node}")
            detect_minutes = int(row["detect_after_min"])
            survives_hours = float(row["survives_hours"])
            remaining_minutes = int(survives_hours * 60) - detect_minutes
            writer.writerow(
                [
                    node,
                    detect_minutes,
                    survives_hours,
                    row["surviving_activity"],
                    remaining_minutes,
                    row["basis"],
                ]
            )


def edge_color(mission):
    return {
        "intake": "#2563eb",
        "processing": "#16803c",
        "response": "#c2410c",
    }.get(mission, "#475569")


def render_graph(nodes, matrix, edge_map):
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="650" viewBox="0 0 1200 650" role="img" aria-labelledby="title desc">',
        '<title id="title">Граф обработки заявок жильцов в управляющей компании</title>',
        '<desc id="desc">Направленные связи между жильцом, диспетчером, реестром заявок и управляющей компанией.</desc>',
        "<defs>",
        '<marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="context-stroke"/></marker>',
        '<style>text{font-family:Arial,sans-serif;fill:#172554}.edge{fill:none;stroke-width:2.4;marker-end:url(#arrow)}.node{stroke-width:2;rx:10}.label{font-size:14px;text-anchor:middle}.flow{font-size:12px;text-anchor:middle;fill:#334155}.legend{font-size:13px}</style>',
        "</defs>",
        '<rect width="1200" height="650" fill="#ffffff"/>',
        '<text x="40" y="42" font-size="24" font-weight="700">Граф обработки заявок жильцов в УК</text>',
        '<text x="40" y="68" font-size="14" fill="#475569">Рёбра и подписи построены из lab4_adjacency.csv и lab4_edges.csv</text>',
    ]

    for source in nodes:
        for target in nodes:
            if not matrix[source][target]:
                continue
            edge = edge_map[(source, target)]
            path_data, label_x, label_y = EDGE_LAYOUT[(source, target)]
            color = edge_color(edge["mission"])
            lines.append(
                f'<path class="edge" d="{path_data}" stroke="{color}" marker-end="url(#arrow)"/>'
            )
            lines.append(
                f'<text class="flow" x="{label_x}" y="{label_y}" paint-order="stroke" stroke="white" stroke-width="5">{html.escape(edge["flow"])}</text>'
            )

    fills = {
        "resident": ("#ecfdf5", "#16a34a"),
        "dispatcher": ("#eff6ff", "#2563eb"),
        "requests": ("#fff7ed", "#ea580c"),
        "uk": ("#f8fafc", "#64748b"),
    }
    for node in nodes:
        x, y = POSITIONS[node]
        fill, stroke = fills.get(node, ("#f8fafc", "#64748b"))
        lines.append(
            f'<rect class="node" x="{x - 90}" y="{y - 30}" width="180" height="60" fill="{fill}" stroke="{stroke}"/>'
        )
        lines.append(
            f'<text class="label" x="{x}" y="{y + 5}" font-weight="700">{html.escape(DISPLAY_NAMES.get(node, node))}</text>'
        )

    lines.extend(
        [
            '<line x1="55" y1="600" x2="95" y2="600" stroke="#2563eb" stroke-width="3"/>',
            '<text class="legend" x="105" y="605">приём и регистрация</text>',
            '<line x1="300" y1="600" x2="340" y2="600" stroke="#16803c" stroke-width="3"/>',
            '<text class="legend" x="350" y="605">передача в работу и статус</text>',
            '<line x1="630" y1="600" x2="670" y2="600" stroke="#c2410c" stroke-width="3"/>',
            '<text class="legend" x="680" y="605">ответ жильцу</text>',
            "</svg>",
        ]
    )
    GRAPH_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    nodes, matrix, edges, edge_map = read_inputs()
    write_degrees(nodes, matrix)
    write_failure_tests(nodes, edges)
    write_failure_timing(nodes)
    render_graph(nodes, matrix, edge_map)

    critical_nodes = []
    with FAILURES_FILE.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row["system_operational"] == "false":
                critical_nodes.append(row["removed_node"])

    if critical_nodes:
        print("Критические внутренние вершины:", ", ".join(critical_nodes))
    else:
        print("Критические внутренние вершины не найдены.")
    print(
        f"Созданы: {DEGREES_FILE.name}, {FAILURES_FILE.name}, "
        f"{TIMING_OUTPUT_FILE.name}, {GRAPH_FILE.name}"
    )


if __name__ == "__main__":
    main()