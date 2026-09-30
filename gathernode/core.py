"""采集点：按时间刷新、每玩家采集次数上限、请求幂等。

刷新按查询时刻懒结算：访问节点时若 ready_at + refresh_ms <= now，
回满次数并把 ready_at 往后推相应周期数，单次操作摊还 O(1)，
代价与 refresh 调用次数、节点总数均无关。
"""


class GatherError(ValueError):
    """采集请求不合法。"""


class World:
    """采集点世界。"""

    def __init__(self, refresh_ms=1000, per_player_max=1, node_uses=2):
        self.refresh_ms = refresh_ms
        self.per_player_max = per_player_max
        self.node_uses = node_uses
        self.nodes = {}
        # (player, node_id) -> [period_ready_at, count]，周期随节点刷新推进
        self.player_uses = {}
        # 幂等台账：已受理的 request_id
        self.handled = set()
        self.scanned = 0

    def register(self, node_id, ready_at=0):
        self.nodes[node_id] = {"uses": self.node_uses, "ready_at": ready_at}

    def _settle(self, state, now_ms):
        """按时间懒结算：到期则回满次数，ready_at 推进已过去的周期数。"""
        elapsed = (now_ms - state["ready_at"]) // self.refresh_ms
        if elapsed > 0:
            state["uses"] = self.node_uses
            state["ready_at"] += elapsed * self.refresh_ms

    def refresh(self, now_ms):
        """刷新按查询时刻懒结算，调用本身不逐节点扫描，摊还 O(1)。"""

    def harvest(self, request_id, player, node_id, now_ms):
        """采集一次：幂等台账 -> 懒结算 -> 节点次数上限 -> 每玩家周期上限。"""
        state = self.nodes.get(node_id)
        if state is None:
            raise GatherError("没有这个采集点：%s" % node_id)
        if request_id in self.handled:
            return False
        self.handled.add(request_id)
        self._settle(state, now_ms)
        if state["uses"] <= 0:
            return False
        key = (player, node_id)
        quota = self.player_uses.get(key)
        if quota is None or quota[0] != state["ready_at"]:
            quota = [state["ready_at"], 0]
            self.player_uses[key] = quota
        if quota[1] >= self.per_player_max:
            return False
        quota[1] += 1
        state["uses"] -= 1
        return True

    def uses_left(self, node_id, now_ms):
        """节点剩余次数：只结算目标节点，O(1)，不扫节点表。"""
        self.scanned += 1
        state = self.nodes.get(node_id)
        if state is None:
            return 0
        self._settle(state, now_ms)
        return state["uses"]

    def scanned_count(self):
        return self.scanned
