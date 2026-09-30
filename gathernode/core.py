"""采集点：按时间刷新、每玩家采集次数上限、请求幂等。

刷新在节点被访问（采集或查询）时按当前时刻懒结算，单次操作 O(1)，
与节点数、refresh 调用次数都无关。
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
        self.handled = set()
        self.scanned = 0

    def register(self, node_id, ready_at=0):
        self.nodes[node_id] = {
            "uses": self.node_uses,
            "ready_at": ready_at,
            "players": {},
        }

    def _settle(self, state, now_ms):
        """按查询时刻懒结算：跨过整周期就回满次数并清空本周期玩家计数。"""
        delta = now_ms - state["ready_at"]
        if delta >= self.refresh_ms:
            periods = delta // self.refresh_ms
            state["ready_at"] += periods * self.refresh_ms
            state["uses"] = self.node_uses
            state["players"].clear()

    def refresh(self, now_ms):
        """刷新按查询时刻懒结算，显式调用不产生任何代价。"""
        return None

    def harvest(self, request_id, player, node_id, now_ms):
        """采集一次，成功返回 True；任何上限拦截或重复请求返回 False 且不扣次数。"""
        state = self.nodes.get(node_id)
        if state is None:
            raise GatherError("没有这个采集点：%s" % node_id)
        if request_id in self.handled:
            return False
        self._settle(state, now_ms)
        self.scanned += 1
        if state["players"].get(player, 0) >= self.per_player_max:
            return False
        if state["uses"] <= 0:
            return False
        state["uses"] -= 1
        state["players"][player] = state["players"].get(player, 0) + 1
        self.handled.add(request_id)
        return True

    def uses_left(self, node_id, now_ms):
        """节点剩余次数，只访问该节点一条记录。"""
        state = self.nodes.get(node_id)
        if state is None:
            return 0
        self._settle(state, now_ms)
        self.scanned += 1
        return state["uses"]

    def scanned_count(self):
        return self.scanned
