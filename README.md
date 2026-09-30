# gather-node

采集点：按时间刷新、每玩家采集次数上限、请求幂等，只用 Python 标准库。

```
python3 -m gathernode.cli --sample refresh
python3 -m gathernode.cli --sample duplicate
python3 -m gathernode.cli --sample player
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **按时间刷新**：节点在 `ready_at + refresh_ms <= now` 时回满使用次数，
  刷新按查询时刻懒结算，代价与调用次数无关；刷新后 `ready_at` 往后推一个周期。
- **次数上限**：节点使用次数不足时采集返回 `False` 且不扣次数，`uses` 不许为负；
  同一玩家在同一个刷新周期内对同一节点最多采 `per_player_max` 次，超出返回 `False`。
- **请求幂等**：同一个 `request_id` 重复提交只生效一次，第二次返回 `False` 且不扣次数。
- **查询代价**：`uses_left` 不许每次全扫节点表，`scanned_count()` 不随节点数线性增长。
- **规模**：10 万采集点、每秒 20 万次采集与查询，单次操作摊还 O(1)，内存 O(节点数)。

## 输出契约（不改格式）

```
third=false uses=0
first=true second=false uses=2
same_first=true same_second=false other=true
scanned<=3000
```

## 目录

```
gathernode/core.py   刷新、次数与幂等
gathernode/cli.py    命令行入口
tests/               unittest 用例
```
