"""命令行入口：跑采集点样例。"""

import argparse

from .core import World


def build_parser():
    parser = argparse.ArgumentParser(prog="gather-node", description="采集点刷新与次数")
    parser.add_argument("--sample", default="refresh", help="refresh / duplicate / player / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "refresh":
        world = World(refresh_ms=1000, per_player_max=9, node_uses=2)
        world.register("ore", 0)
        third = True
        for index in range(3):
            third = world.harvest("r-%d" % index, "p", "ore", 500)
        after_harvest = world.uses_left("ore", 500)
        world.refresh(1500)
        print("third=%s uses=%d refreshed=%d" % (str(third).lower(), after_harvest,
                                                 world.uses_left("ore", 1500)))
    elif args.sample == "duplicate":
        world = World(per_player_max=9, node_uses=3)
        world.register("ore", 0)
        first = world.harvest("r-1", "p", "ore", 100)
        second = world.harvest("r-1", "p", "ore", 100)
        print("first=%s second=%s uses=%d" % (str(first).lower(), str(second).lower(),
                                              world.uses_left("ore", 100)))
    elif args.sample == "player":
        world = World(per_player_max=1, node_uses=5)
        world.register("ore", 0)
        first = world.harvest("r-1", "p", "ore", 100)
        again = world.harvest("r-2", "p", "ore", 100)
        other = world.harvest("r-3", "q", "ore", 100)
        print("same_first=%s same_second=%s other=%s" % (str(first).lower(), str(again).lower(),
                                                          str(other).lower()))
    elif args.sample == "scan":
        world = World()
        for index in range(3000):
            world.register("n-%d" % index, 0)
        for _ in range(3000):
            world.uses_left("n-2999", 0)
        print("scanned=%d" % world.scanned_count())
    else:
        raise SystemExit("需要 --sample refresh|duplicate|player|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
