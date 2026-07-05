# プロジェクト: 一筆書きパズルソルバー

## 原則
- 仕様の正は SPEC.md。実装・変更の前に必ず読むこと
- Python 3.10+ / 標準ライブラリのみ（pip install 禁止、GUIはtkinter）
- graph_logic.py（ロジック層）と gui_app.py（GUI層）を分離する。
  graph_logic.py では tkinter を import しないこと
- コメント・docstring・ユーザー向け文言は日本語で書く

## コマンド
- 起動: python gui_app.py
- テスト: python -m unittest test_graph_logic -v

## 完了条件
- テストが全件パスしてから完了報告すること
- SPEC.md 10章の受け入れ基準を満たすこと
