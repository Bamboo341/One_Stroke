"""一筆書きパズルソルバーの GUI 層（エントリポイント）。

起動: python gui_app.py
グラフの管理・判定・探索は graph_logic.Graph に委譲し、
本ファイルは描画とユーザー操作のみを担当する。
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, simpledialog

from graph_logic import Edge, Graph

# ------------------------------------------------------------
# 配色（仕様 8.6）
# ------------------------------------------------------------
COLOR_POINT_FILL = "#e8f0fe"     # 点の塗り
COLOR_POINT_OUTLINE = "#1a56b0"  # 通常の縁
COLOR_ODD_OUTLINE = "#d93025"    # 奇数点の縁
COLOR_SELECTED = "#f9ab00"       # 選択中の点
COLOR_EDGE = "#5f6368"           # 線
COLOR_BADGE = "#1a56b0"          # 番号バッジ
COLOR_START = "#188038"          # 「始」
COLOR_END = "#d93025"            # 「終」

# ------------------------------------------------------------
# 寸法・当たり判定（仕様 8.2 / 8.5）
# ------------------------------------------------------------
CANVAS_WIDTH = 680       # Canvas の初期幅
CANVAS_HEIGHT = 500      # Canvas の初期高さ
POINT_RADIUS = 15        # 点の描画半径
POINT_HIT_RADIUS = 19    # 点のクリック判定半径（中心から約19px）
EDGE_HIT_DIST = 6        # 線のクリック判定距離（曲線から6px）
EDGE_OFFSET_STEP = 26    # 多重辺の中点間隔（約26px）
BEZIER_SAMPLES = 24      # 曲線のサンプル分割数
BADGE_RADIUS = 11        # 番号バッジの半径
BADGE_GAP = 2            # バッジ同士に確保する最小すき間
BADGE_T_MIN = 0.25       # バッジをずらせる範囲の下限（曲線の媒介変数）
BADGE_T_MAX = 0.75       # バッジをずらせる範囲の上限


def index_to_label(index: int) -> str:
    """0始まりの連番を A, B, …, Z, AA, AB, … 形式のラベルに変換する。"""
    label = ""
    n = index + 1
    while n > 0:
        n, r = divmod(n - 1, 26)
        label = chr(ord("A") + r) + label
    return label


def quadratic_bezier_points(
    p0: tuple[float, float],
    ctrl: tuple[float, float],
    p1: tuple[float, float],
    samples: int,
) -> list[tuple[float, float]]:
    """2次ベジェ曲線を等間隔の媒介変数でサンプリングした点列を返す。"""
    points = []
    for i in range(samples + 1):
        t = i / samples
        s = 1.0 - t
        x = s * s * p0[0] + 2 * s * t * ctrl[0] + t * t * p1[0]
        y = s * s * p0[1] + 2 * s * t * ctrl[1] + t * t * p1[1]
        points.append((x, y))
    return points


def place_badges(
    curves: list[list[tuple[float, float]]],
    obstacles: list[tuple[float, float, float]],
) -> list[tuple[float, float]]:
    """番号バッジの位置を通過順に決め、重なりを避けた座標列を返す。

    基本は各曲線の中点に置き、配置済みバッジや障害物（点の円・矢じり）と
    重なる場合のみ、その曲線上 t∈[BADGE_T_MIN, BADGE_T_MAX] の範囲を
    中央に近い順に探して空き位置へずらす（貪欲法）。
    全候補が衝突する場合は最も重なりの小さい位置を採用する。
    バッジが自分の線から離れることはない。

    Args:
        curves: 通過順に並んだ、各辺の曲線サンプル点列
        obstacles: (x, y, 確保したい距離) のリスト
    """
    min_gap = BADGE_RADIUS * 2 + BADGE_GAP
    placed: list[tuple[float, float]] = []
    for pts in curves:
        last = len(pts) - 1
        mid = last // 2
        lo = round(last * BADGE_T_MIN)
        hi = round(last * BADGE_T_MAX)
        # 中央から外側へ交互に候補を並べる
        candidates = [mid]
        for step in range(1, last + 1):
            if mid - step >= lo:
                candidates.append(mid - step)
            if mid + step <= hi:
                candidates.append(mid + step)
            if mid - step < lo and mid + step > hi:
                break
        best_pos = pts[mid]
        best_score = -1.0
        for idx in candidates:
            x, y = pts[idx]
            # 最も窮屈な相手との余裕率（1.0以上なら衝突なし）
            margins = [
                math.hypot(x - bx, y - by) / min_gap for bx, by in placed
            ] + [
                math.hypot(x - ox, y - oy) / max(need, 1.0)
                for ox, oy, need in obstacles
            ]
            score = min(margins) if margins else float("inf")
            if score >= 1.0:
                best_pos = (x, y)
                break
            if score > best_score:
                best_score = score
                best_pos = (x, y)
        placed.append(best_pos)
    return placed


def point_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """点 (px, py) と線分 AB の最短距離を返す。"""
    abx, aby = bx - ax, by - ay
    apx, apy = px - ax, py - ay
    ab2 = abx * abx + aby * aby
    if ab2 == 0:
        return math.hypot(apx, apy)
    t = max(0.0, min(1.0, (apx * abx + apy * aby) / ab2))
    return math.hypot(px - (ax + abx * t), py - (ay + aby * t))


class OneStrokeApp:
    """一筆書きパズルソルバーのメインウィンドウ。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("一筆書きパズルソルバー")
        self.root.minsize(560, 420)

        self.graph = Graph()
        # 線を追加モードで1点目に選択中の点ID（未選択なら None）
        self.selected_point: int | None = None
        # 探索結果 (点IDの経路列, 辺IDの通過順)。未探索なら None
        self.solution: tuple[list[int], list[int]] | None = None
        # 点ラベルの自動採番カウンタ（A, B, …, Z, AA, …）
        self._label_count = 0

        self._build_widgets()
        self._refresh_status()

    # ------------------------------------------------------------
    # 画面構築（仕様 8.1）
    # ------------------------------------------------------------

    def _build_widgets(self) -> None:
        """レイアウトを構築する。左: Canvas / 右: 操作パネル / 下: 表示行。"""
        # 下部: 解答表示行 ＋ 判定ステータス行
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 6))
        self.answer_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="")
        self.answer_label = tk.Label(
            bottom, textvariable=self.answer_var, anchor="w",
            font=("", 11, "bold"), fg=COLOR_BADGE,
        )
        self.answer_label.pack(fill=tk.X)
        self.status_label = tk.Label(
            bottom, textvariable=self.status_var, anchor="w",
        )
        self.status_label.pack(fill=tk.X)

        # 右: 操作パネル
        panel = tk.Frame(self.root, padx=10, pady=10)
        panel.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(panel, text="モード", font=("", 11, "bold")).pack(anchor="w")
        self.mode_var = tk.StringVar(value="add_point")
        modes = [
            ("点を追加", "add_point"),
            ("線を追加", "add_edge"),
            ("削除", "delete"),
        ]
        for text, value in modes:
            tk.Radiobutton(
                panel, text=text, value=value, variable=self.mode_var,
                command=self._on_mode_changed,
            ).pack(anchor="w")

        tk.Button(
            panel, text="解答を探索", command=self.on_search,
        ).pack(fill=tk.X, pady=(12, 4))
        tk.Button(
            panel, text="全て消去", command=self.on_clear_all,
        ).pack(fill=tk.X)

        usage = (
            "【使い方】\n"
            "・点を追加: 空白をクリックで点を置く。"
            "既存の点をクリックでラベルを変更。\n"
            "・線を追加: 点を2つ順にクリックで線を引く。"
            "空白クリックで選択解除。"
            "同じ2点間に複数の線も引ける。\n"
            "・削除: 点をクリックでその点と接続線を削除。"
            "線をクリックでその線だけ削除。\n"
            "・図形を編集するたびに一筆書きの可否を自動判定し、"
            "奇数点を赤い縁で表示する。"
        )
        tk.Label(
            panel, text=usage, justify=tk.LEFT, wraplength=180, anchor="w",
        ).pack(fill=tk.X, pady=(12, 0))

        # 左: Canvas（白背景・リサイズ追従）
        self.canvas = tk.Canvas(
            self.root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT,
            bg="white", highlightthickness=1, highlightbackground="#dadce0",
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                         padx=(8, 0), pady=(8, 6))
        self.canvas.bind("<Button-1>", self.on_canvas_click)

    # ------------------------------------------------------------
    # 当たり判定（仕様 8.2）
    # ------------------------------------------------------------

    def find_point_at(self, x: float, y: float) -> int | None:
        """座標に最も近い点のIDを返す。判定半径の外なら None。"""
        best_id = None
        best_dist = POINT_HIT_RADIUS
        for point in self.graph.points.values():
            d = math.hypot(point.x - x, point.y - y)
            if d <= best_dist:
                best_dist = d
                best_id = point.id
        return best_id

    def find_edge_at(self, x: float, y: float) -> int | None:
        """座標に最も近い線のIDを返す。曲線から6pxより遠ければ None。

        描画と同一のサンプル点列に対して距離を測る（見た目とのズレ防止）。
        """
        best_id = None
        best_dist = EDGE_HIT_DIST
        for edge in self.graph.edges.values():
            pts = self._edge_curve_points(edge)
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                d = point_segment_distance(x, y, ax, ay, bx, by)
                if d <= best_dist:
                    best_dist = d
                    best_id = edge.id
        return best_id

    # ------------------------------------------------------------
    # 曲線サンプル（仕様 8.5）— 描画とクリック判定で共用する
    # ------------------------------------------------------------

    def _edge_curve_points(self, edge: Edge) -> list[tuple[float, float]]:
        """辺を表す2次ベジェ曲線のサンプル点列を返す。

        端点IDの小さい方 → 大きい方に向きを正規化するため、
        どちらの点から線を引いても同じ形状・同じオフセットになる。
        多重辺は法線方向に中点間隔が約26pxになるよう対称に振り分ける。
        """
        a_id, b_id = sorted((edge.u, edge.v))
        pa = self.graph.points[a_id]
        pb = self.graph.points[b_id]

        siblings = self.graph.parallel_edges(a_id, b_id)  # ID昇順
        k = len(siblings)
        i = siblings.index(edge.id)
        # 中央の辺がオフセット0になるよう対称に配置する
        mid_offset = (i - (k - 1) / 2) * EDGE_OFFSET_STEP

        dx, dy = pb.x - pa.x, pb.y - pa.y
        length = math.hypot(dx, dy)
        if length == 0:
            # 端点が同一座標に重なった場合の保険（通常は起きない）
            nx, ny = 0.0, -1.0
        else:
            nx, ny = -dy / length, dx / length
        mx, my = (pa.x + pb.x) / 2, (pa.y + pb.y) / 2
        # 2次ベジェは t=0.5 で制御点方向へ半分だけ膨らむため、
        # 曲線の中点を mid_offset ずらすには制御点を2倍ずらす
        ctrl = (mx + nx * mid_offset * 2, my + ny * mid_offset * 2)
        return quadratic_bezier_points(
            (pa.x, pa.y), ctrl, (pb.x, pb.y), BEZIER_SAMPLES
        )

    # ------------------------------------------------------------
    # 操作イベント（仕様 8.2）
    # ------------------------------------------------------------

    def _on_mode_changed(self) -> None:
        """モード切替時は線の1点目選択を解除する。"""
        self.selected_point = None
        self._redraw()

    def on_canvas_click(self, event: tk.Event) -> None:
        """Canvas クリックを現在のモードに応じて振り分ける。"""
        mode = self.mode_var.get()
        if mode == "add_point":
            self._click_add_point(event.x, event.y)
        elif mode == "add_edge":
            self._click_add_edge(event.x, event.y)
        elif mode == "delete":
            self._click_delete(event.x, event.y)

    def _click_add_point(self, x: float, y: float) -> None:
        """点を追加モード: 空白なら点を追加、既存の点ならリネーム。"""
        pid = self.find_point_at(x, y)
        if pid is not None:
            self._rename_point(pid)
            return
        label = index_to_label(self._label_count)
        self._label_count += 1
        self.graph.add_point(label, x, y)
        self._on_graph_edited()

    def _rename_point(self, pid: int) -> None:
        """リネームダイアログを表示して点のラベルを変更する。"""
        current = self.graph.points[pid].label
        new_label = simpledialog.askstring(
            "点のリネーム",
            f"点「{current}」の新しいラベルを入力してください:",
            initialvalue=current,
            parent=self.root,
        )
        if new_label is None:
            return  # キャンセル
        new_label = new_label.strip()
        if not new_label:
            messagebox.showwarning(
                "リネーム", "空のラベルは設定できません。", parent=self.root
            )
            return
        self.graph.points[pid].label = new_label
        self._on_graph_edited()

    def _click_add_edge(self, x: float, y: float) -> None:
        """線を追加モード: 点を2つ順にクリックで線を追加する。"""
        pid = self.find_point_at(x, y)
        if pid is None:
            # 空白クリックで選択解除
            self.selected_point = None
            self._redraw()
            return
        if self.selected_point is None:
            # 1点目を選択（オレンジで強調）
            self.selected_point = pid
            self._redraw()
            return
        if pid == self.selected_point:
            # 自己ループは拒否し、選択解除して警告表示
            self.selected_point = None
            self._redraw()
            messagebox.showwarning(
                "線を追加",
                "同じ点を2回クリックしました。"
                "自己ループ（同じ点を結ぶ線）は作れません。",
                parent=self.root,
            )
            return
        first = self.selected_point
        self.selected_point = None
        self.graph.add_edge(first, pid)
        self._on_graph_edited()

    def _click_delete(self, x: float, y: float) -> None:
        """削除モード: 点を優先して削除し、なければ線を削除する。"""
        pid = self.find_point_at(x, y)
        if pid is not None:
            self.graph.remove_point(pid)
            self._on_graph_edited()
            return
        eid = self.find_edge_at(x, y)
        if eid is not None:
            self.graph.remove_edge(eid)
            self._on_graph_edited()

    # ------------------------------------------------------------
    # ボタン操作（仕様 8.4）
    # ------------------------------------------------------------

    def on_search(self) -> None:
        """［解答を探索］: 不可能なら理由をダイアログ表示、可能なら解答を描画。"""
        ok, reason, _start, _end = self.graph.check_if_drawable()
        if not ok:
            messagebox.showwarning("探索できません", reason, parent=self.root)
            return
        path_points, path_edges = self.graph.find_euler_path()
        self.solution = (path_points, path_edges)
        labels = [self.graph.points[pid].label for pid in path_points]
        self.answer_var.set("解答: " + " → ".join(labels))
        self._redraw()

    def on_clear_all(self) -> None:
        """［全て消去］: 確認ダイアログを挟んで全消去する。"""
        if not messagebox.askyesno(
            "確認", "全ての点と線を消去します。よろしいですか？",
            parent=self.root,
        ):
            return
        self.graph.clear()
        self._label_count = 0
        self.selected_point = None
        self._on_graph_edited()

    # ------------------------------------------------------------
    # リアルタイム判定と再描画（仕様 8.3）
    # ------------------------------------------------------------

    def _on_graph_edited(self) -> None:
        """図形の編集直後に呼ぶ。解答を即時クリアし、判定・再描画する。"""
        self.solution = None
        self.answer_var.set("")
        self._redraw()
        self._refresh_status()

    def _refresh_status(self) -> None:
        """ステータス行に check_if_drawable の判定理由を常時表示する。"""
        ok, reason, _start, _end = self.graph.check_if_drawable()
        self.status_var.set("判定: " + reason)
        self.status_label.config(fg=COLOR_START if ok else COLOR_END)

    def _redraw(self) -> None:
        """Canvas 全体を描き直す。線 → 点 → 解答表示の順に重ねる。"""
        self.canvas.delete("all")
        odd_points = set(self.graph.get_odd_points())

        # 線（多重辺はベジェ曲線でオフセット描画）
        for edge in self.graph.edges.values():
            pts = self._edge_curve_points(edge)
            flat = [coord for xy in pts for coord in xy]
            self.canvas.create_line(*flat, fill=COLOR_EDGE, width=3)

        # 点（奇数点は赤い縁取り、選択中はオレンジ）
        for point in self.graph.points.values():
            if point.id == self.selected_point:
                outline, width = COLOR_SELECTED, 4
            elif point.id in odd_points:
                outline, width = COLOR_ODD_OUTLINE, 3
            else:
                outline, width = COLOR_POINT_OUTLINE, 2
            self.canvas.create_oval(
                point.x - POINT_RADIUS, point.y - POINT_RADIUS,
                point.x + POINT_RADIUS, point.y + POINT_RADIUS,
                fill=COLOR_POINT_FILL, outline=outline, width=width,
            )
            self.canvas.create_text(
                point.x, point.y, text=point.label,
                fill=COLOR_POINT_OUTLINE, font=("", 10, "bold"),
            )

        # 解答（番号バッジと始・終マーカー）
        if self.solution is not None:
            self._draw_solution()

    def _draw_solution(self) -> None:
        """探索結果を描画する（仕様 8.4）。"""
        path_points, path_edges = self.solution

        # 1. 各線に通過順の番号バッジ（青丸＋白数字、1始まり）。
        #    基本は中点、重なる場合は自分の曲線に沿ってずらす
        curves = [
            self._edge_curve_points(self.graph.edges[eid])
            for eid in path_edges
        ]
        obstacles = [
            (p.x, p.y, POINT_RADIUS + BADGE_RADIUS + 2)
            for p in self.graph.points.values()
        ]
        positions = place_badges(curves, obstacles)
        for order, (bx, by) in enumerate(positions, start=1):
            self.canvas.create_oval(
                bx - BADGE_RADIUS, by - BADGE_RADIUS,
                bx + BADGE_RADIUS, by + BADGE_RADIUS,
                fill=COLOR_BADGE, outline="white", width=2,
            )
            self.canvas.create_text(
                bx, by, text=str(order), fill="white", font=("", 10, "bold"),
            )

        # 2. 始点・終点マーカー。閉路なら「始/終」を1つだけ表示
        start_id, end_id = path_points[0], path_points[-1]
        marker_dy = POINT_RADIUS + 13
        if start_id == end_id:
            p = self.graph.points[start_id]
            self.canvas.create_text(
                p.x, p.y - marker_dy, text="始/終",
                fill=COLOR_START, font=("", 12, "bold"),
            )
        else:
            ps = self.graph.points[start_id]
            pe = self.graph.points[end_id]
            self.canvas.create_text(
                ps.x, ps.y - marker_dy, text="始",
                fill=COLOR_START, font=("", 12, "bold"),
            )
            self.canvas.create_text(
                pe.x, pe.y - marker_dy, text="終",
                fill=COLOR_END, font=("", 12, "bold"),
            )


def main() -> None:
    """アプリを起動する。"""
    root = tk.Tk()
    OneStrokeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
