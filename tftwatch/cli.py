"""TFTwatch CLI -- Phase 0 lobby scouting.

Examples:
  python -m tftwatch.cli scout "Name#NA1" "Other#EUW"
  python -m tftwatch.cli scout --from-lobby "Me#NA1"     (experimental)
  python -m tftwatch.cli scout "Name#NA1" --matches 25 --platform euw1 --region europe
"""
import os
import sys
import argparse

from dotenv import load_dotenv

from .riot_client import RiotClient, RiotError
from .scout import scout_riot_id, scout_puuid, ScoutReport


def _print_report(r: ScoutReport) -> None:
    print("=" * 64)
    print(f"  {r.riot_id}    [{r.rank}]")
    if r.error:
        print(f"  !! {r.error}")
        print()
        return
    print(f"  Set {r.set_number} | {r.games_analyzed} recent games analyzed")
    print("-" * 64)

    p = r.prediction
    if p:
        conf = f"{p.get('confidence', 0) * 100:.0f}%"
        print(f"  PREDICTION -> {p.get('comp', '?')}   (confidence {conf})")
        print(f"               {p.get('signal', '')}")
        if p.get("carries"):
            print(f"               likely carries: {', '.join(p['carries'])}")
        if p.get("avg_placement"):
            print(f"               avg placement on it: {p['avg_placement']:.1f}")
        # Trait tendency is often the strongest real signal -> headline it.
        if r.top_traits:
            t = r.top_traits[0]
            if r.games_analyzed and t["count"] / r.games_analyzed >= 0.35:
                print(f"               GO-TO TRAIT: {t['name']} "
                      f"({t['count']}/{r.games_analyzed} games, avg {t['avg']:.1f})")
    print()
    print("  Most-played comps:")
    for s in r.top_comps:
        carries = ", ".join(sorted(s.carries)[:3])
        print(f"    - {s.label:<28} x{s.count:<2}  avg {s.avg_placement:.1f}"
              + (f"  [{carries}]" if carries else ""))

    if r.top_traits:
        print("\n  Trait tendencies:")
        for t in r.top_traits:
            print(f"    - {t['name']:<24} {t['count']}/{r.games_analyzed} games  avg {t['avg']:.1f}")
    if r.top_carries:
        print("\n  Favorite carries:")
        for u in r.top_carries:
            print(f"    - {u['name']:<24} {u['count']}/{r.games_analyzed} games  avg {u['avg']:.1f}")
    print()


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="tftwatch", description="TFT lobby scouting")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scout", help="scout one or more opponents")
    sc.add_argument("riot_ids", nargs="*", help="opponents as Name#TAG")
    sc.add_argument("--from-lobby", metavar="ME#TAG",
                    help="EXPERIMENTAL: auto-pull your current game's roster")
    sc.add_argument("--matches", type=int, default=15, help="recent games per player")
    sc.add_argument("--platform", default=os.getenv("TFT_PLATFORM", "na1"))
    sc.add_argument("--region", default=os.getenv("TFT_REGION", "americas"))

    rm = sub.add_parser("remind", help="beep/popup every few seconds to scout (no key needed)")
    rm.add_argument("--interval", type=int, default=40, help="seconds between nudges")
    rm.add_argument("--no-sound", action="store_true")
    rm.add_argument("--no-popup", action="store_true", help="console-only, no window")

    args = parser.parse_args(argv)

    if args.cmd == "remind":
        from .reminder import run as run_reminder
        return run_reminder(args.interval, sound=not args.no_sound, popup=not args.no_popup)

    try:
        client = RiotClient(os.getenv("RIOT_API_KEY", ""),
                            platform=args.platform, region=args.region)
    except RiotError as e:
        print(f"Setup error: {e}", file=sys.stderr)
        return 1

    reports: list[ScoutReport] = []

    if args.from_lobby:
        try:
            name, tag = args.from_lobby.split("#", 1)
            me = client.account_by_riot_id(name.strip(), tag.strip())
        except (ValueError, RiotError) as e:
            print(f"Could not resolve {args.from_lobby}: {e}", file=sys.stderr)
            return 1
        puuids = client.active_lobby_puuids(me["puuid"])
        if not puuids:
            print("No active lobby found (are you in a game?). "
                  "Falling back: pass Riot IDs manually.", file=sys.stderr)
            return 1
        print(f"Found {len(puuids)} players in your lobby. Scouting...\n")
        for i, pu in enumerate(puuids):
            tag = "YOU" if pu == me["puuid"] else f"Opponent {i + 1}"
            reports.append(scout_puuid(client, pu, tag, args.matches))
    else:
        if not args.riot_ids:
            print("Pass at least one Name#TAG, or use --from-lobby.", file=sys.stderr)
            return 1
        for rid in args.riot_ids:
            reports.append(scout_riot_id(client, rid, args.matches))

    print()
    for r in reports:
        _print_report(r)

    # Lobby-level synthesis: what's contested (the cross-opponent edge).
    predicted = [r.prediction.get("comp") for r in reports
                 if r.prediction and not r.error and r.prediction.get("comp") != "Unknown"]
    contested = {c: predicted.count(c) for c in set(predicted) if predicted.count(c) >= 2}
    if contested:
        print("=" * 64)
        print("  LOBBY READ -- contested lines (avoid / they fight for units):")
        for comp, n in sorted(contested.items(), key=lambda x: -x[1]):
            print(f"    * {comp}: {n} players likely forcing it")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
