#!/usr/bin/env bash
# Fork VorEdgeJP/kagekit, push fix/stop-view-on-panel-edit, open a PR (Japanese body).
set -euo pipefail
cd "$(dirname "$0")/.."

if ! gh auth status -h github.com >/dev/null 2>&1; then
  echo "GitHub CLI に未ログインです: gh auth login -h github.com -p ssh -s repo -w"
  exit 1
fi

USER="$(gh api user --jq .login)"
BRANCH="$(git branch --show-current)"
if [[ "$BRANCH" != fix/stop-view-on-panel-edit ]]; then
  echo "ブランチ fix/stop-view-on-panel-edit で実行してください（現在: $BRANCH）"
  exit 1
fi

if ! git remote get-url fork >/dev/null 2>&1; then
  gh repo fork VorEdgeJP/kagekit --remote=true --remote-name=fork --clone=false
fi

git push -u fork "$BRANCH"

gh pr create --repo VorEdgeJP/kagekit \
  --base main \
  --head "${USER}:${BRANCH}" \
  --title "パネル編集時に前の LayoutView を stop して ViewStore の蓄積を防ぐ" \
  --body "$(cat <<'EOF'
## 概要

`Page.edit`（`ComponentBuilder.edit_interaction_response`）で同じメッセージを差し替えるたびに `Page.build()` が新しい `LayoutView` とランダム `custom_id` を生成します。discord.py 2.7.x の `edit_message` は同期用の View 参照を外すだけで、旧 View を `stop()` しないため、プロセス内の ViewStore にディスパッチ表が編集回数分残り続けます。

本 PR では `edit_message` の直前に `prevent_view_updates_for` で取得した旧 View を `stop()` します。

## 影響

- 高頻度で in-place 編集する長寿命ボットでのメモリ／ViewStore 増加を抑止
- 認証突破などのセキュリティ問題ではありません（可用性・リソース管理）

## テスト

- [x] `pytest -q`（`tests/test_kagekit_view_store.py` を追加）
- [ ] 任意: `python scripts/viewstore_edit_repro.py`

## 補足

CONTRIBUTING.md の upstream 運用に合わせ、BotShade 側への反映が必要な場合はお知らせください。
EOF
)"
