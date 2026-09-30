"""按时间刷新、次数上限、请求幂等与参考实现对照。"""

import random
import unittest

from gathernode.core import World


class TimeRefreshTest(unittest.TestCase):
    def test_not_refreshed_before_period(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 0)
        self.assertEqual(world.uses_left("ore", 999), 1)

    def test_refreshed_at_ready_time(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 0)
        world.harvest("r-2", "p", "ore", 0)
        self.assertEqual(world.uses_left("ore", 999), 0)
        self.assertEqual(world.uses_left("ore", 1000), 2)

    def test_refresh_cost_independent_of_calls(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 0)
        for now in range(0, 5000):
            world.refresh(now)
        self.assertEqual(world.uses_left("ore", 5000), 2)
        self.assertEqual(world.scanned_count(), 1)

    def test_multiple_periods_collapse_to_full(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=3)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 0)
        self.assertEqual(world.uses_left("ore", 10000), 3)

    def test_player_quota_resets_after_period(self):
        world = World(refresh_ms=1000, per_player_max=1, node_uses=5)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertFalse(world.harvest("r-2", "p", "ore", 0))
        self.assertTrue(world.harvest("r-3", "p", "ore", 1000))


class LimitsTest(unittest.TestCase):
    def test_empty_node_returns_false_and_keeps_zero(self):
        world = World(refresh_ms=10000, per_player_max=9, node_uses=1)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertFalse(world.harvest("r-2", "p", "ore", 0))
        self.assertFalse(world.harvest("r-3", "p", "ore", 0))
        self.assertEqual(world.uses_left("ore", 0), 0)

    def test_per_player_limit(self):
        world = World(refresh_ms=10000, per_player_max=2, node_uses=5)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertTrue(world.harvest("r-2", "p", "ore", 0))
        self.assertFalse(world.harvest("r-3", "p", "ore", 0))
        self.assertTrue(world.harvest("r-4", "q", "ore", 0))
        self.assertEqual(world.uses_left("ore", 0), 2)

    def test_uses_never_negative(self):
        world = World(refresh_ms=10000, per_player_max=1, node_uses=1)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-0", "p0", "ore", 0))
        for index in range(5):
            self.assertFalse(world.harvest("r-%d" % index, "p%d" % index, "ore", 0))
        self.assertEqual(world.uses_left("ore", 0), 0)


class IdempotencyTest(unittest.TestCase):
    def test_duplicate_request_returns_false_and_costs_nothing(self):
        world = World(refresh_ms=10000, per_player_max=9, node_uses=3)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertFalse(world.harvest("r-1", "p", "ore", 0))
        self.assertFalse(world.harvest("r-1", "q", "ore", 0))
        self.assertEqual(world.uses_left("ore", 0), 2)

    def test_replayed_sequence_is_deterministic(self):
        def run():
            world = World(refresh_ms=1000, per_player_max=2, node_uses=2)
            world.register("ore", 0)
            ops = [
                ("h", "r-1", "p", 0),
                ("h", "r-1", "p", 0),
                ("h", "r-2", "p", 0),
                ("u", None, None, 0),
                ("h", "r-3", "q", 1000),
                ("u", None, None, 1000),
            ]
            results = []
            for kind, rid, player, now in ops:
                if kind == "h":
                    results.append(world.harvest(rid, player, "ore", now))
                else:
                    results.append(world.uses_left("ore", now))
            return results
        self.assertEqual(run(), run())


class ReferenceWorld:
    """参考实现：用独立结构直接按口径模拟。"""

    def __init__(self, refresh_ms, per_player_max, node_uses):
        self.refresh_ms = refresh_ms
        self.per_player_max = per_player_max
        self.node_uses = node_uses
        self.nodes = {}
        self.player_counts = {}
        self.handled = set()

    def register(self, node_id, ready_at):
        self.nodes[node_id] = [self.node_uses, ready_at]

    def _periods(self, ready_at, now):
        return max((now - ready_at) // self.refresh_ms, 0)

    def harvest(self, request_id, player, node_id, now):
        if node_id not in self.nodes:
            raise ValueError(node_id)
        if request_id in self.handled:
            return False
        self.handled.add(request_id)
        periods = self._periods(self.nodes[node_id][1], now)
        if periods > 0:
            self.nodes[node_id][1] += periods * self.refresh_ms
            self.nodes[node_id][0] = self.node_uses
        if self.nodes[node_id][0] <= 0:
            return False
        pkey = (player, node_id, self.nodes[node_id][1])
        if self.player_counts.get(pkey, 0) >= self.per_player_max:
            return False
        self.player_counts[pkey] = self.player_counts.get(pkey, 0) + 1
        self.nodes[node_id][0] -= 1
        return True

    def uses_left(self, node_id, now):
        if node_id not in self.nodes:
            return 0
        periods = self._periods(self.nodes[node_id][1], now)
        if periods > 0:
            self.nodes[node_id][1] += periods * self.refresh_ms
            self.nodes[node_id][0] = self.node_uses
        return self.nodes[node_id][0]


class DifferentialTest(unittest.TestCase):
    def test_200_random_sequences_match_reference(self):
        rng = random.Random(20261001)
        for _ in range(200):
            refresh_ms = rng.randint(1, 10)
            world = World(refresh_ms=refresh_ms,
                          per_player_max=rng.randint(1, 3),
                          node_uses=rng.randint(1, 4))
            ref = ReferenceWorld(refresh_ms, world.per_player_max, world.node_uses)
            node_ids = ["n-%d" % i for i in range(rng.randint(1, 4))]
            players = ["p-%d" % i for i in range(rng.randint(1, 4))]
            for node_id in node_ids:
                ready_at = rng.randint(0, 5)
                world.register(node_id, ready_at)
                ref.register(node_id, ready_at)
            now = rng.randint(0, 5)
            for _ in range(rng.randint(20, 60)):
                now += rng.randint(0, 3)
                if rng.random() < 0.7:
                    node_id = rng.choice(node_ids)
                    rid = "r-%d" % rng.randint(0, 30)
                    player = rng.choice(players)
                    rnow = now
                    got = world.harvest(rid, player, node_id, rnow)
                    want = ref.harvest(rid, player, node_id, rnow)
                    self.assertIs(got, want, (refresh_ms, rid, player, node_id, rnow))
                    if rng.random() < 0.3:
                        got = world.harvest(rid, player, node_id, rnow)
                        want = ref.harvest(rid, player, node_id, rnow)
                        self.assertIs(got, want)
                else:
                    world.refresh(now)
                node_id = rng.choice(node_ids)
                self.assertEqual(world.uses_left(node_id, now),
                                 ref.uses_left(node_id, now))
                for node in node_ids:
                    uses = world.uses_left(node, now)
                    self.assertGreaterEqual(uses, 0)
                    self.assertLessEqual(uses, world.node_uses)


if __name__ == "__main__":
    unittest.main()
