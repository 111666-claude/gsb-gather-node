import unittest

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


if __name__ == "__main__":
    unittest.main()
