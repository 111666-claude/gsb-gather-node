"""采集点：按时间刷新、每玩家采集次数上限、请求幂等。

缺陷：刷新按调用次数而不是时间、每玩家上限不生效、重复请求重复生效、
查询全扫节点、刷新之后次数没回满。
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
        self.player_uses = {}
        self.handled = {}
        self.scanned = 0

    def register(self, node_id, ready_at=0):
        self.nodes[node_id] = {"uses": self.node_uses, "ready_at": ready_at}

    def refresh(self, now_ms):
        """刷新采集点。缺陷：每调用一次就给所有节点加一次使用次数。"""
        for state in self.nodes.values():
            state["uses"] += 1
            self.scanned += 1

    def harvest(self, request_id, player, node_id, now_ms):
        """采集一次。缺陷：不看节点剩余次数、不看每玩家上限、也不记 request_id。"""
        state = self.nodes.get(node_id)
        if state is None:
            raise GatherError("没有这个采集点：%s" % node_id)
        state["uses"] -= 1
        key = (player, node_id)
        self.player_uses[key] = self.player_uses.get(key, 0) + 1
        return True

    def uses_left(self, node_id, now_ms):
        """节点剩余次数。缺陷：每次全扫节点表。"""
        self.scanned += len(self.nodes)
        return self.nodes.get(node_id, {}).get("uses", 0)

    def scanned_count(self):
        return self.scanned
