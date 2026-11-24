"""旁路封闸命运条（旁封修丙 · 当班锁死）。

红线：**旁路禁封**。开放旁路挂起仍在册时，正式快照零增；封闸意图只进影子
草稿，待旁路闭合并原子晋升后正式册才改。

甲（直接拒收、整笔回滚）与乙（影子草稿待晋升）不得混用。本仓落乙路径；
禁止第三旁路写法；任何偏离命运条的实现一律按“旁路封闸偏航拒写”拒绝。

登记见 docs/旁路封闸修复册.md。
"""
from __future__ import annotations

# 命运条（当班锁死，不得改写）
FATE_LINE = (
    "旁路开放未结即旁路禁封：正式快照零增；封闸意图只进影子草稿，"
    "待旁路闭合并原子晋升后正式册才改。甲/乙不得混用，禁止第三旁路写法。"
)
REGISTER = "docs/旁路封闸修复册.md"
SHIFT = "旁封修丙"
SEAL_PATH = "乙"
ALLOWED_PATHS = ("甲", "乙")
DRAFT_STATUS = "草稿待晋升"
FORMAL_STATUS = "已封闸"
SIDE_LANE_STATUS = "旁路挂起"


def assert_fate_path(path: str = SEAL_PATH) -> None:
    """偏离命运条 → 旁路封闸偏航拒写。"""
    if path not in ALLOWED_PATHS or path != SEAL_PATH:
        raise RuntimeError(
            f"旁路封闸偏航拒写：只准 {SEAL_PATH} 路径，拒绝第三旁路写法（{path}）"
        )
