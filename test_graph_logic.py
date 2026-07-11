"""graph_logic.py（ロジック層）の単体テスト。

仕様書 9 章の13観点を網羅する。GUI には依存しない。
実行: python -m unittest test_graph_logic -v
"""

import unittest

from graph_logic import Graph


# ------------------------------------------------------------
# 図形の組み立てヘルパー
# ------------------------------------------------------------

def build_square() -> Graph:
    """四角形（点4・線4、全点の次数2）を作る。"""
    g = Graph()
    p = [g.add_point(c, 0, 0) for c in "ABCD"]
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        g.add_edge(p[a], p[b])
    return g


def build_house() -> Graph:
    """家の形（点5・線6）を作る。

    四角形 A-B-C-D に屋根 A-E-B を載せた形。
    A と B だけが次数3（奇数点）になる。
    """
    g = Graph()
    p = [g.add_point(c, 0, 0) for c in "ABCDE"]
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (4, 1)]:
        g.add_edge(p[a], p[b])
    return g


def build_cross() -> Graph:
    """十字（中心 C から4本、先端4点が奇数点）を作る。"""
    g = Graph()
    center = g.add_point("C", 0, 0)
    for name in ["N", "E", "S", "W"]:
        g.add_edge(center, g.add_point(name, 0, 0))
    return g


def build_two_triangles() -> Graph:
    """離れた三角形2つ（非連結な図形）を作る。"""
    g = Graph()
    p = [g.add_point(c, 0, 0) for c in "ABCDEF"]
    for a, b in [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)]:
        g.add_edge(p[a], p[b])
    return g


def build_directed(edge_list: list[tuple[str, str]], labels: str) -> Graph:
    """有向グラフを作る。edge_list はラベルの (始点, 終点) ペア。"""
    g = Graph(directed=True)
    ids = {c: g.add_point(c, 0, 0) for c in labels}
    for u, v in edge_list:
        g.add_edge(ids[u], ids[v])
    return g


def build_koenigsberg() -> Graph:
    """ケーニヒスベルクの橋（点4・多重辺を含む線7本）を作る。

    A=北岸 / B=南岸 / C=中央の島 / D=東の島。
    全4点が奇数点となり、一筆書きは不可能。
    """
    g = Graph()
    a, b, c, d = (g.add_point(name, 0, 0) for name in "ABCD")
    for u, v in [(a, c), (a, c), (b, c), (b, c), (a, d), (b, d), (c, d)]:
        g.add_edge(u, v)
    return g


class EulerPathAssertions(unittest.TestCase):
    """経路の妥当性を検証する共通ヘルパー（観点11）。"""

    def assert_valid_euler_path(self, g: Graph) -> None:
        """オイラー路が仕様7章の整合条件を満たすことを検証する。

        - 点列長 = 辺列長 + 1
        - 全ての辺をちょうど1回ずつ使用する
        - 経路上の隣接2点は、対応する辺の両端と一致する
        """
        path_points, path_edges = g.find_euler_path()
        self.assertIsNotNone(path_points, "可能な図形なのに経路が None")
        self.assertIsNotNone(path_edges, "可能な図形なのに辺列が None")
        # 点列長 = 辺列長 + 1
        self.assertEqual(len(path_points), len(path_edges) + 1)
        # 全辺をちょうど1回ずつ使用
        self.assertEqual(sorted(path_edges), sorted(g.edges.keys()))
        # 隣接2点はその辺の両端と一致
        for i, eid in enumerate(path_edges):
            edge = g.edges[eid]
            self.assertEqual(
                {path_points[i], path_points[i + 1]},
                {edge.u, edge.v},
                f"{i}番目の辺 {eid} が経路の点と対応していない",
            )
        # 有向モードでは辺の向き（u→v）どおりに通過していること
        if g.directed:
            for i, eid in enumerate(path_edges):
                edge = g.edges[eid]
                self.assertEqual(
                    (path_points[i], path_points[i + 1]),
                    (edge.u, edge.v),
                    f"{i}番目の辺 {eid} を向きに逆らって通過している",
                )


class TestGraphEditing(unittest.TestCase):
    """グラフの編集操作（追加・削除・採番）のテスト。"""

    def test_自己ループ追加はValueError(self):
        """観点8: 同じ点同士を結ぶ線は ValueError で拒否される。"""
        g = Graph()
        a = g.add_point("A", 0, 0)
        with self.assertRaises(ValueError):
            g.add_edge(a, a)

    def test_存在しない点への辺追加はKeyError(self):
        """存在しない点IDを指定した add_edge は KeyError になる。"""
        g = Graph()
        a = g.add_point("A", 0, 0)
        with self.assertRaises(KeyError):
            g.add_edge(a, 999)
        with self.assertRaises(KeyError):
            g.add_edge(999, a)

    def test_点削除で接続線が連動削除される(self):
        """観点9: 点を削除すると、その点に接続する線も消える。"""
        g = Graph()
        a, b, c = (g.add_point(name, 0, 0) for name in "ABC")
        g.add_edge(a, b)
        g.add_edge(b, c)
        e_ac = g.add_edge(a, c)
        g.remove_point(b)
        # B と、B に接続していた2本の線が消え、A-C の線だけ残る
        self.assertNotIn(b, g.points)
        self.assertEqual(set(g.edges.keys()), {e_ac})
        self.assertEqual(g.get_degree(a), 1)
        self.assertEqual(g.get_degree(c), 1)

    def test_削除後に点IDが再利用されない(self):
        """観点10: 点を削除しても、次に採番されるIDは重複しない。"""
        g = Graph()
        a = g.add_point("A", 0, 0)
        b = g.add_point("B", 0, 0)
        g.remove_point(b)
        c = g.add_point("C", 0, 0)
        self.assertNotEqual(c, b, "削除した点のIDが再利用された")
        self.assertEqual(len({a, b, c}), 3)

    def test_削除後に辺IDが再利用されない(self):
        """辺についてもIDの再利用がないこと（採番規則の確認）。"""
        g = Graph()
        u = g.add_point("U", 0, 0)
        v = g.add_point("V", 0, 0)
        e1 = g.add_edge(u, v)
        g.remove_edge(e1)
        e2 = g.add_edge(u, v)
        self.assertNotEqual(e2, e1, "削除した辺のIDが再利用された")

    def test_存在しない辺の削除は何もしない(self):
        """remove_edge は不在の辺IDに対して例外を出さない。"""
        g = Graph()
        g.remove_edge(999)  # 例外が出ないこと

    def test_parallel_edgesはID昇順(self):
        """多重辺の辺IDが、端点の指定順によらずID昇順で返る。"""
        g = Graph()
        u, v, w = (g.add_point(name, 0, 0) for name in "UVW")
        e1 = g.add_edge(u, v)
        g.add_edge(u, w)  # 無関係な辺
        e3 = g.add_edge(v, u)  # 逆向きに追加した多重辺
        self.assertEqual(g.parallel_edges(u, v), sorted([e1, e3]))
        self.assertEqual(g.parallel_edges(v, u), sorted([e1, e3]))


class TestCheckIfDrawable(unittest.TestCase):
    """一筆書き可否判定（check_if_drawable）のテスト。"""

    def test_四角形は可能で閉路(self):
        """観点1: 四角形は奇数点0個 → 可能。始点=終点。"""
        g = build_square()
        ok, reason, start, end = g.check_if_drawable()
        self.assertTrue(ok, reason)
        self.assertIsNotNone(start)
        self.assertEqual(start, end, "閉路なのに始点と終点が異なる")
        self.assertGreater(g.get_degree(start), 0)

    def test_家の形は可能で奇数点2つが始点終点(self):
        """観点2: 家の形は奇数点2個 → 可能。その2点が始点・終点。"""
        g = build_house()
        ok, reason, start, end = g.check_if_drawable()
        self.assertTrue(ok, reason)
        self.assertNotEqual(start, end)
        self.assertEqual({start, end}, set(g.get_odd_points()))

    def test_十字は不可能(self):
        """観点3: 十字は奇数点4個 → 不可能。"""
        g = build_cross()
        ok, reason, start, end = g.check_if_drawable()
        self.assertFalse(ok)
        self.assertIn("4", reason, "理由に奇数点の個数が含まれない")
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_離れた三角形2つは不可能(self):
        """観点4: 非連結な図形は不可能。"""
        g = build_two_triangles()
        ok, reason, start, end = g.check_if_drawable()
        self.assertFalse(ok)
        self.assertIn("分離", reason)
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_空グラフは不可能(self):
        """観点5: 線が1本もなければ不可能。"""
        g = Graph()
        ok, reason, start, end = g.check_if_drawable()
        self.assertFalse(ok)
        self.assertEqual(reason, "線が1本もありません。")
        self.assertIsNone(start)
        self.assertIsNone(end)

    def test_点だけで線がない場合も不可能(self):
        """点があっても線が0本なら「線がない」判定になる。"""
        g = Graph()
        g.add_point("A", 0, 0)
        ok, reason, _, _ = g.check_if_drawable()
        self.assertFalse(ok)
        self.assertEqual(reason, "線が1本もありません。")

    def test_孤立点は判定に影響しない(self):
        """観点6: 孤立点を足しても可否判定は変わらない。"""
        g = build_square()
        ok_before, _, _, _ = g.check_if_drawable()
        g.add_point("X", 100, 100)  # 孤立点
        ok_after, reason, _, _ = g.check_if_drawable()
        self.assertTrue(ok_before)
        self.assertTrue(ok_after, f"孤立点の追加で判定が変わった: {reason}")

    def test_ケーニヒスベルクの橋は不可能(self):
        """観点7: 点4・多重辺含む線7本の古典問題 → 不可能。"""
        g = build_koenigsberg()
        self.assertEqual(len(g.points), 4)
        self.assertEqual(len(g.edges), 7)
        self.assertEqual(len(g.get_odd_points()), 4)
        ok, _, _, _ = g.check_if_drawable()
        self.assertFalse(ok)

    def test_連結判定は孤立点を無視する(self):
        """is_connected は次数0の点を無視し、辺0本なら True。"""
        g = Graph()
        self.assertTrue(g.is_connected())  # 辺0本
        g.add_point("X", 0, 0)
        self.assertTrue(g.is_connected())  # 孤立点のみ
        g2 = build_square()
        g2.add_point("X", 100, 100)
        self.assertTrue(g2.is_connected())  # 連結図形 + 孤立点


class TestFindEulerPath(EulerPathAssertions):
    """オイラー路探索（find_euler_path）のテスト。"""

    def test_四角形の経路の妥当性(self):
        """観点1・11: 四角形で妥当な閉路が求まる。"""
        g = build_square()
        self.assert_valid_euler_path(g)
        path_points, _ = g.find_euler_path()
        self.assertEqual(path_points[0], path_points[-1], "閉路になっていない")

    def test_家の形の経路の妥当性(self):
        """観点2・11: 家の形で妥当な経路が求まり、端が奇数点になる。"""
        g = build_house()
        self.assert_valid_euler_path(g)
        path_points, path_edges = g.find_euler_path()
        self.assertEqual(len(path_edges), 6)
        self.assertEqual(
            {path_points[0], path_points[-1]},
            set(g.get_odd_points()),
            "経路の両端が奇数点になっていない",
        )

    def test_多重辺2本のみのグラフで経路が求まる(self):
        """観点12: 2点間に多重辺2本だけのグラフ（U→V→U の閉路）。"""
        g = Graph()
        u = g.add_point("U", 0, 0)
        v = g.add_point("V", 0, 0)
        g.add_edge(u, v)
        g.add_edge(u, v)
        self.assert_valid_euler_path(g)
        path_points, _ = g.find_euler_path()
        self.assertEqual(len(path_points), 3)
        self.assertEqual(path_points[0], path_points[-1])

    def test_不可能な図形はNoneNoneを返す(self):
        """観点13: 不可能な図形では (None, None) が返る。"""
        for name, g in [
            ("十字", build_cross()),
            ("分離三角形", build_two_triangles()),
            ("空グラフ", Graph()),
            ("ケーニヒスベルク", build_koenigsberg()),
        ]:
            with self.subTest(figure=name):
                self.assertEqual(g.find_euler_path(), (None, None))

    def test_ラベル列の取得(self):
        """get_path_as_labels が経路をラベルで返し、不可能なら None。"""
        g = build_square()
        labels = g.get_path_as_labels()
        self.assertEqual(len(labels), 5)  # 点列長 = 辺4本 + 1
        self.assertTrue(all(lb in "ABCD" for lb in labels))
        self.assertIsNone(build_cross().get_path_as_labels())

    def test_大規模な閉路でも再帰上限に当たらない(self):
        """反復実装の確認: 数万辺の閉路でも例外なく経路が求まる。"""
        g = Graph()
        n = 5000
        ids = [g.add_point(str(i), 0, 0) for i in range(n)]
        for i in range(n):
            g.add_edge(ids[i], ids[(i + 1) % n])
        path_points, path_edges = g.find_euler_path()
        self.assertEqual(len(path_edges), n)
        self.assertEqual(len(path_points), n + 1)


class TestDirectedGraph(EulerPathAssertions):
    """有向グラフモード（directed=True）のテスト。"""

    def test_有向三角形の閉路は可能(self):
        """観点14: A→B→C→A は全点均衡 → 閉路として可能。"""
        g = build_directed([("A", "B"), ("B", "C"), ("C", "A")], "ABC")
        ok, reason, start, end = g.check_if_drawable()
        self.assertTrue(ok, reason)
        self.assertEqual(start, end)
        self.assert_valid_euler_path(g)

    def test_有向パスの始点終点(self):
        """観点15: A→B→C は +1 の点が始点、−1 の点が終点になる。"""
        g = build_directed([("A", "B"), ("B", "C")], "ABC")
        ok, reason, start, end = g.check_if_drawable()
        self.assertTrue(ok, reason)
        self.assertEqual(g.points[start].label, "A")
        self.assertEqual(g.points[end].label, "C")
        self.assert_valid_euler_path(g)

    def test_合流する2辺は不可能(self):
        """観点16: A→B, C→B は B に入るだけの点ができ不可能。"""
        g = build_directed([("A", "B"), ("C", "B")], "ABC")
        ok, reason, start, end = g.check_if_drawable()
        self.assertFalse(ok)
        self.assertIn("合わない", reason)
        self.assertIsNone(start)
        self.assertIsNone(end)
        self.assertEqual(g.find_euler_path(), (None, None))

    def test_一辺だけ逆向きの四角形は不可能(self):
        """一周の向きが揃っていない閉路（±2の不均衡）は不可能。"""
        g = build_directed(
            [("A", "B"), ("B", "C"), ("D", "C"), ("D", "A")], "ABCD"
        )
        ok, _, _, _ = g.check_if_drawable()
        self.assertFalse(ok)

    def test_相互の2辺で閉路(self):
        """観点17: A→B と B→A は往復の閉路として可能。"""
        g = build_directed([("A", "B"), ("B", "A")], "AB")
        ok, reason, start, end = g.check_if_drawable()
        self.assertTrue(ok, reason)
        self.assertEqual(start, end)
        self.assert_valid_euler_path(g)

    def test_共有点を持つ2つの有向閉路(self):
        """8の字（点Xを共有する向き付き閉路2つ）→ 全点均衡で可能。"""
        g = build_directed(
            [("X", "A"), ("A", "X"), ("X", "B"), ("B", "X")], "XAB"
        )
        ok, reason, start, end = g.check_if_drawable()
        self.assertTrue(ok, reason)
        self.assertEqual(start, end)
        self.assert_valid_euler_path(g)

    def test_同じ図形でも無向と有向で判定が変わる(self):
        """観点18: U→V の多重辺2本は無向なら可能、有向では不可能。"""
        g = Graph()
        u = g.add_point("U", 0, 0)
        v = g.add_point("V", 0, 0)
        g.add_edge(u, v)
        g.add_edge(u, v)
        ok_undirected, _, _, _ = g.check_if_drawable()
        self.assertTrue(ok_undirected)
        # モードを切り替えても図形は保持されたまま判定だけが変わる
        g.directed = True
        ok_directed, _, _, _ = g.check_if_drawable()
        self.assertFalse(ok_directed)
        self.assertEqual(g.find_euler_path(), (None, None))

    def test_有向の多重辺で経路が求まる(self):
        """観点19: 往復2組（計4辺）の有向多重辺で向きどおりの経路。"""
        g = build_directed(
            [("U", "V"), ("V", "U"), ("U", "V"), ("V", "U")], "UV"
        )
        self.assert_valid_euler_path(g)

    def test_不均衡点の一覧(self):
        """get_unbalanced_points が (点ID, 出−入の差) を返す。"""
        g = build_directed([("A", "B"), ("A", "C")], "ABC")
        unbalanced = dict(g.get_unbalanced_points())
        ids = {p.label: p.id for p in g.points.values()}
        self.assertEqual(unbalanced[ids["A"]], 2)
        self.assertEqual(unbalanced[ids["B"]], -1)
        self.assertEqual(unbalanced[ids["C"]], -1)

    def test_有向でも連結判定は向きを無視する(self):
        """観点20: 合流形（A→B, C→B）でも底グラフとしては連結。"""
        g = build_directed([("A", "B"), ("C", "B")], "ABC")
        self.assertTrue(g.is_connected())
        # 理由は「分離」ではなく次数の不均衡になる
        _, reason, _, _ = g.check_if_drawable()
        self.assertNotIn("分離", reason)


if __name__ == "__main__":
    unittest.main()
