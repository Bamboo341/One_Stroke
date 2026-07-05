"""一筆書きパズルソルバーのロジック層。

点・線からなる無向グラフを管理し、一筆書き（オイラー路）の
判定と経路探索を行う。GUI ライブラリには一切依存しない。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass
class Point:
    """グラフ上の点（頂点）。

    Attributes:
        id: 一意な点ID（再利用されない）
        label: 表示用ラベル（例: "A"）
        x: Canvas 上の X 座標
        y: Canvas 上の Y 座標
    """

    id: int
    label: str
    x: float
    y: float


@dataclass
class Edge:
    """グラフ上の線（無向辺）。

    Attributes:
        id: 一意な辺ID（再利用されない）
        u: 端点の点ID
        v: 端点の点ID
    """

    id: int
    u: int
    v: int

    def other(self, pid: int) -> int:
        """指定した点IDの反対側の端点IDを返す。

        Args:
            pid: 端点のいずれかの点ID

        Raises:
            ValueError: pid がこの辺の端点でない場合
        """
        if pid == self.u:
            return self.v
        if pid == self.v:
            return self.u
        raise ValueError(f"点ID {pid} は辺 {self.id} の端点ではありません。")


class Graph:
    """点と線を管理する無向グラフ（多重辺を許可、自己ループは禁止）。"""

    def __init__(self) -> None:
        self.points: dict[int, Point] = {}
        self.edges: dict[int, Edge] = {}
        # 点ID → 接続する辺IDのリスト
        self.adjacency: dict[int, list[int]] = {}
        # 採番用カウンタ。削除後もデクリメントせず、IDを再利用しない
        self._next_point_id: int = 0
        self._next_edge_id: int = 0

    # ------------------------------------------------------------
    # 編集操作
    # ------------------------------------------------------------

    def add_point(self, label: str, x: float, y: float) -> int:
        """点を追加し、採番した点IDを返す。"""
        pid = self._next_point_id
        self._next_point_id += 1
        self.points[pid] = Point(pid, label, x, y)
        self.adjacency[pid] = []
        return pid

    def add_edge(self, u: int, v: int) -> int:
        """線を追加し、採番した辺IDを返す。多重辺は許可する。

        Raises:
            ValueError: u == v の場合（自己ループ禁止）
            KeyError: 存在しない点IDが指定された場合
        """
        if u == v:
            raise ValueError("同じ点を結ぶ線（自己ループ）は追加できません。")
        if u not in self.points:
            raise KeyError(f"点ID {u} は存在しません。")
        if v not in self.points:
            raise KeyError(f"点ID {v} は存在しません。")
        eid = self._next_edge_id
        self._next_edge_id += 1
        self.edges[eid] = Edge(eid, u, v)
        self.adjacency[u].append(eid)
        self.adjacency[v].append(eid)
        return eid

    def remove_edge(self, edge_id: int) -> None:
        """線を削除する。存在しない辺IDなら何もしない。"""
        edge = self.edges.pop(edge_id, None)
        if edge is None:
            return
        self.adjacency[edge.u].remove(edge_id)
        self.adjacency[edge.v].remove(edge_id)

    def remove_point(self, point_id: int) -> None:
        """点を削除する。接続する線も連動して削除する。

        存在しない点IDなら何もしない。
        """
        if point_id not in self.points:
            return
        # リスト走査中の変更を避けるためコピーしてから削除する
        for eid in list(self.adjacency[point_id]):
            self.remove_edge(eid)
        del self.adjacency[point_id]
        del self.points[point_id]

    def clear(self) -> None:
        """全ての点と線を削除する。採番カウンタはリセットしない。"""
        self.points.clear()
        self.edges.clear()
        self.adjacency.clear()

    # ------------------------------------------------------------
    # 参照系
    # ------------------------------------------------------------

    def get_degree(self, pid: int) -> int:
        """点の次数（接続する線の本数）を返す。"""
        return len(self.adjacency[pid])

    def get_odd_points(self) -> list[int]:
        """次数が奇数の点のIDリストを返す。"""
        return [pid for pid in self.points if self.get_degree(pid) % 2 == 1]

    def parallel_edges(self, u: int, v: int) -> list[int]:
        """u-v 間の辺IDをID昇順で返す（多重辺の描画オフセット計算用）。"""
        if u not in self.adjacency or v not in self.adjacency:
            return []
        return sorted(
            eid for eid in self.adjacency[u] if self.edges[eid].other(u) == v
        )

    def is_connected(self) -> bool:
        """次数1以上の点だけを対象に BFS で連結判定する。

        孤立点（次数0）は無視する。線が1本もなければ True を返す。
        """
        active = [pid for pid in self.points if self.get_degree(pid) > 0]
        if not active:
            return True
        visited: set[int] = {active[0]}
        queue: deque[int] = deque([active[0]])
        while queue:
            cur = queue.popleft()
            for eid in self.adjacency[cur]:
                nxt = self.edges[eid].other(cur)
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        return len(visited) == len(active)

    # ------------------------------------------------------------
    # 一筆書き判定・探索
    # ------------------------------------------------------------

    def check_if_drawable(self) -> tuple[bool, str, int | None, int | None]:
        """一筆書きが可能かを判定する。

        Returns:
            (可否, 理由, 始点ID or None, 終点ID or None) のタプル。
        """
        # 1. 辺が0本
        if not self.edges:
            return (False, "線が1本もありません。", None, None)
        # 2. 非連結
        if not self.is_connected():
            return (
                False,
                "図形が分離しています。全ての線がつながるようにしてください。",
                None,
                None,
            )
        odd = self.get_odd_points()
        # 3. 奇数点0個 → 閉路（どの点から始めても同じ点に戻る）
        if len(odd) == 0:
            start = next(
                pid for pid in self.points if self.get_degree(pid) > 0
            )
            return (
                True,
                "一筆書き可能です（閉路）。どの点から始めても元の点に戻ります。",
                start,
                start,
            )
        # 4. 奇数点2個 → その2点が始点・終点
        if len(odd) == 2:
            s, t = odd
            return (
                True,
                f"一筆書き可能です。始点 {self.points[s].label}"
                f" → 終点 {self.points[t].label}（逆順も可）。",
                s,
                t,
            )
        # 5. それ以外 → 不可能
        labels = "、".join(self.points[pid].label for pid in odd)
        return (
            False,
            f"一筆書きできません。奇数点が{len(odd)}個あります"
            f"（{labels}）。奇数点は0個か2個である必要があります。",
            None,
            None,
        )

    def find_euler_path(self) -> tuple[list[int], list[int]] | tuple[None, None]:
        """Hierholzer 法（スタックによる反復実装）でオイラー路を求める。

        Returns:
            (点IDの経路列, 辺IDの通過順) のタプル。
            不可能な場合は (None, None)。
            len(点列) == len(辺列) + 1 が常に成り立つ。
        """
        ok, _reason, start, _end = self.check_if_drawable()
        if not ok:
            return (None, None)

        # 各点の隣接リスト走査位置ポインタ。使用済み辺を再走査しない
        ptr: dict[int, int] = {pid: 0 for pid in self.points}
        used: set[int] = set()
        # スタック要素は (点ID, その点へ到達するのに使った辺ID)
        stack: list[tuple[int, int | None]] = [(start, None)]
        path_points: list[int] = []
        path_edges: list[int] = []

        while stack:
            cur, via = stack[-1]
            adj = self.adjacency[cur]
            i = ptr[cur]
            # 使用済みの辺を読み飛ばす（枝刈り）
            while i < len(adj) and adj[i] in used:
                i += 1
            ptr[cur] = i
            if i < len(adj):
                # 未使用の辺があれば進む。使用済み判定は辺ID単位で行う
                eid = adj[i]
                used.add(eid)
                ptr[cur] = i + 1
                stack.append((self.edges[eid].other(cur), eid))
            else:
                # 行き止まりなら経路として確定する
                stack.pop()
                path_points.append(cur)
                if via is not None:
                    path_edges.append(via)

        path_points.reverse()
        path_edges.reverse()
        return (path_points, path_edges)

    def get_path_as_labels(self) -> list[str] | None:
        """オイラー路を点のラベル列で返す。不可能なら None を返す。"""
        path_points, _path_edges = self.find_euler_path()
        if path_points is None:
            return None
        return [self.points[pid].label for pid in path_points]
