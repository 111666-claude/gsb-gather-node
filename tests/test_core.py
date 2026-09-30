import io
import random
import time
import unittest
from contextlib import redirect_stdout

from gathernode import cli
from gathernode.core import GatherError, World


class RegisterTest(unittest.TestCase):
    def test_register_fills_uses(self):
        world = World(node_uses=3)
        world.register("ore", 0)
        self.assertEqual(world.uses_left("ore", 0), 3)

    def test_scanned_starts_at_zero(self):
        self.assertEqual(World().scanned_count(), 0)


class HarvestTest(unittest.TestCase):
    def test_harvest_costs_one_use(self):
        world = World(per_player_max=9, node_uses=2)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 100)
        self.assertEqual(world.uses_left("ore", 100), 1)

    def test_unknown_node_raises(self):
        with self.assertRaises(GatherError):
            World().harvest("r-1", "p", "missing", 0)


class RefreshTest(unittest.TestCase):
    def test_refresh_is_callable(self):
        world = World(node_uses=1)
        world.register("ore", 0)
        world.refresh(0)
        self.assertGreaterEqual(world.uses_left("ore", 0), 1)


class TimeRefreshTest(unittest.TestCase):
    def test_refill_only_when_period_passed(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 100)
        world.harvest("r-2", "p", "ore", 200)
        self.assertEqual(world.uses_left("ore", 999), 0)
        self.assertEqual(world.uses_left("ore", 1000), 2)

    def test_refill_after_consumption_in_new_period(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 1000))
        self.assertEqual(world.uses_left("ore", 1999), 1)
        self.assertEqual(world.uses_left("ore", 2000), 2)

    def test_explicit_refresh_is_lazy_and_free(self):
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        world.harvest("r-1", "p", "ore", 100)
        for _ in range(100):
            world.refresh(500)
        self.assertEqual(world.uses_left("ore", 500), 1)
        self.assertLessEqual(world.scanned_count(), 2)

    def test_player_window_resets_with_period(self):
        world = World(refresh_ms=1000, per_player_max=1, node_uses=5)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 100))
        self.assertFalse(world.harvest("r-2", "p", "ore", 200))
        self.assertTrue(world.harvest("r-3", "p", "ore", 1000))


class CapTest(unittest.TestCase):
    def test_exhausted_node_returns_false_without_deduction(self):
        world = World(per_player_max=9, node_uses=2)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertTrue(world.harvest("r-2", "p", "ore", 0))
        self.assertFalse(world.harvest("r-3", "p", "ore", 0))
        self.assertFalse(world.harvest("r-4", "p", "ore", 0))
        self.assertEqual(world.uses_left("ore", 0), 0)

    def test_per_player_max(self):
        world = World(per_player_max=2, node_uses=9)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertTrue(world.harvest("r-2", "p", "ore", 0))
        self.assertFalse(world.harvest("r-3", "p", "ore", 0))
        self.assertTrue(world.harvest("r-4", "q", "ore", 0))


class IdempotencyTest(unittest.TestCase):
    def test_duplicate_request_applies_once(self):
        world = World(per_player_max=9, node_uses=3)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 100))
        self.assertFalse(world.harvest("r-1", "p", "ore", 100))
        self.assertEqual(world.uses_left("ore", 100), 2)

    def test_duplicate_request_blocked_even_for_other_target(self):
        world = World(per_player_max=9, node_uses=3)
        world.register("a", 0)
        world.register("b", 0)
        self.assertTrue(world.harvest("r-1", "p", "a", 0))
        self.assertFalse(world.harvest("r-1", "q", "b", 0))
        self.assertEqual(world.uses_left("b", 0), 3)

    def test_failed_harvest_request_can_be_retried(self):
        world = World(per_player_max=1, node_uses=5)
        world.register("ore", 0)
        self.assertTrue(world.harvest("r-1", "p", "ore", 0))
        self.assertFalse(world.harvest("r-2", "p", "ore", 500))
        self.assertTrue(world.harvest("r-2", "p", "ore", 1000))


class InvariantTest(unittest.TestCase):
    def test_uses_always_in_range_and_replay_deterministic(self):
        params = dict(refresh_ms=7, per_player_max=2, node_uses=3)

        def run():
            rng = random.Random(42)
            world = World(**params)
            for node in ("a", "b", "c"):
                world.register(node, 0)
            results = []
            now = 0
            for _ in range(500):
                now += rng.randrange(0, 10)
                player = rng.choice("pq")
                node = rng.choice(("a", "b", "c"))
                results.append(world.harvest("r-%d" % rng.randrange(40),
                                             player, node, now))
                state = world.nodes[node]
                self.assertGreaterEqual(state["uses"], 0)
                self.assertLessEqual(state["uses"], world.node_uses)
                results.append(tuple(
                    sorted((n, world.uses_left(n, now)) for n in world.nodes)))
            return results

        self.assertEqual(run(), run())


class ScanCostTest(unittest.TestCase):
    def test_scanned_does_not_grow_with_node_count(self):
        world = World()
        for index in range(3000):
            world.register("n-%d" % index, 0)
        for _ in range(3000):
            world.uses_left("n-2999", 0)
        self.assertLessEqual(world.scanned_count(), 3000)

    def test_scale_100k_nodes_200k_ops(self):
        world = World(refresh_ms=1000, per_player_max=2, node_uses=4)
        node_count = 100_000
        for index in range(node_count):
            world.register("n-%d" % index, 0)
        start = time.perf_counter()
        for index in range(100_000):
            world.harvest("h-%d" % index, "p%d" % (index % 50),
                          "n-%d" % index, 0)
        for index in range(100_000):
            world.uses_left("n-%d" % index, 0)
        elapsed = time.perf_counter() - start
        self.assertLessEqual(world.scanned_count(), 200_000)
        self.assertLess(elapsed, 10.0)


class CliSampleTest(unittest.TestCase):
    def _run(self, sample):
        buf = io.StringIO()
        with redirect_stdout(buf):
            cli.main(["--sample", sample])
        return buf.getvalue().strip()

    def test_samples_match_contract(self):
        self.assertEqual(self._run("refresh"), "third=false uses=0 refreshed=2")
        self.assertEqual(self._run("duplicate"), "first=true second=false uses=2")
        self.assertEqual(self._run("player"),
                         "same_first=true same_second=false other=true")
        line = self._run("scan")
        self.assertTrue(line.startswith("scanned="))
        self.assertLessEqual(int(line.split("=", 1)[1]), 3000)


class ReferenceWorld:
    """独立参考实现：按周期计数，节点用量由本周期各玩家计数求和得到。"""

    def __init__(self, refresh_ms, per_player_max, node_uses):
        self.refresh_ms = refresh_ms
        self.per_player_max = per_player_max
        self.node_uses = node_uses
        self.ready_at = {}
        self.picks = {}
        self.handled = set()

    def register(self, node_id, ready_at=0):
        self.ready_at[node_id] = ready_at

    def _cycle(self, node_id, now_ms):
        return (now_ms - self.ready_at[node_id]) // self.refresh_ms

    def _node_total(self, node_id, cycle):
        return sum(count for (node, cc, _player), count in self.picks.items()
                   if node == node_id and cc == cycle)

    def harvest(self, request_id, player, node_id, now_ms):
        if node_id not in self.ready_at:
            raise GatherError("没有这个采集点：%s" % node_id)
        if request_id in self.handled:
            return False
        cycle = self._cycle(node_id, now_ms)
        player_key = (node_id, cycle, player)
        player_count = self.picks.get(player_key, 0)
        if player_count >= self.per_player_max:
            return False
        if self._node_total(node_id, cycle) >= self.node_uses:
            return False
        self.picks[player_key] = player_count + 1
        self.handled.add(request_id)
        return True

    def uses_left(self, node_id, now_ms):
        if node_id not in self.ready_at:
            return 0
        cycle = self._cycle(node_id, now_ms)
        left = self.node_uses - self._node_total(node_id, cycle)
        return max(0, left)


class DifferentialTest(unittest.TestCase):
    def test_random_sequences_match_reference(self):
        rng = random.Random(20260930)
        for case in range(200):
            refresh_ms = rng.choice((1, 3, 7, 1000))
            per_player_max = rng.choice((1, 2, 3))
            node_uses = rng.choice((1, 2, 3, 5))
            world = World(refresh_ms, per_player_max, node_uses)
            ref = ReferenceWorld(refresh_ms, per_player_max, node_uses)
            node_ids = ["n-%d" % i for i in range(rng.randrange(1, 6))]
            for node_id in node_ids:
                world.register(node_id, 0)
                ref.register(node_id, 0)
            players = ["p-%d" % i for i in range(rng.randrange(1, 4))]
            request_pool = []
            now_ms = 0
            for _ in range(rng.randrange(80, 200)):
                now_ms += rng.randrange(0, refresh_ms * 2 + 2)
                node_id = rng.choice(node_ids)
                player = rng.choice(players)
                if request_pool and rng.random() < 0.3:
                    request_id = rng.choice(request_pool)
                else:
                    request_id = "r-%d-%d" % (case, len(request_pool))
                    request_pool.append(request_id)
                got = world.harvest(request_id, player, node_id, now_ms)
                want = ref.harvest(request_id, player, node_id, now_ms)
                self.assertEqual(got, want,
                                 "case %d harvest mismatch: %s" % (case, request_id))
                for check_node in node_ids:
                    self.assertEqual(world.uses_left(check_node, now_ms),
                                     ref.uses_left(check_node, now_ms),
                                     "case %d uses mismatch on %s at %d"
                                     % (case, check_node, now_ms))
                state = world.nodes[node_id]
                self.assertGreaterEqual(state["uses"], 0)
                self.assertLessEqual(state["uses"], node_uses)


if __name__ == "__main__":
    unittest.main()
