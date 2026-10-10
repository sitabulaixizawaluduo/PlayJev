"""Pacman outcome accounting through the real evaluation loop; no browser or GPU."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from playjev import play


class ClearRateTests(unittest.IsolatedAsyncioTestCase):
    async def evaluate(
        self, scenarios, *, pages=1, episodes=1, max_steps=8, game="pacman"
    ):
        class Page:
            async def reset(self, seed):
                self.initial, self.transitions = scenarios.get(seed, (1, [(1, True)]))
                self.index = 0
                return self.observation(self.initial, False)

            def observation(self, level, done):
                return {
                    "frame": b"frame",
                    "score": self.index * 10,
                    "done": done,
                    "info": {"level": level},
                }

            def step(self):
                level, done = self.transitions[
                    min(self.index, len(self.transitions) - 1)
                ]
                self.index += 1
                return self.observation(level, done)

        class Env:
            def __init__(self, game, n):
                self.pages = [Page() for _ in range(n)]
                self.actions = [
                    {"name": name} for name in ("up", "down", "left", "right")
                ]
                self.spec = {"step_frames": 6}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def reset(self, seeds):
                return [await page.reset(seed) for page, seed in zip(self.pages, seeds)]

            async def step(self, actions):
                return [page.step() for page in self.pages]

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = SimpleNamespace(
                game=game,
                pages=pages,
                seed0=100,
                policy="random",
                handover=None,
                handover_random=None,
                record=str(root / "replays"),
                episodes=episodes,
                delay=0,
                sample=False,
                skip_noop=False,
                max_steps=max_steps,
                policy_name=None,
                out=str(root / "result.json"),
            )
            with (
                patch.object(play, "VecGame", Env),
                patch.object(play, "ROOT", root),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                await play.main(args)
            result = json.loads((root / "result.json").read_text())
            replays = {
                int(path.stem.rsplit("_", 1)[1]): json.loads(path.read_text())
                for path in (root / "replays" / game).glob("*.json")
            }
            return result, replays

    async def test_clear_then_death_counts_once_and_resets_for_next_episode(self):
        result, replays = await self.evaluate(
            {100: (5, [(6, False), (7, True)]), 102: (1, [(1, True)])}, episodes=2
        )
        self.assertEqual(result["cleared_episodes"], 1)
        self.assertEqual(result["clear_rate"], 0.5)
        self.assertEqual(
            (replays[100]["start_level"], replays[100]["max_level"]), (5, 7)
        )
        self.assertTrue(replays[100]["cleared"])
        self.assertFalse(replays[100]["truncated"])
        self.assertFalse(replays[102]["cleared"])

    async def test_parallel_clear_and_cap_are_separate_outcomes(self):
        result, replays = await self.evaluate(
            {100: (1, [(2, False)]), 101: (1, [(1, False)])},
            pages=2,
            episodes=2,
            max_steps=1,
        )
        self.assertEqual(result["episodes"], 2)
        self.assertEqual(result["capped"], 2)
        self.assertEqual(result["cleared_episodes"], 1)
        self.assertEqual(result["clear_rate"], 0.5)
        self.assertTrue(replays[100]["truncated"])
        self.assertFalse(replays[101]["cleared"])

    async def test_other_game_keeps_existing_result_schema(self):
        result, replays = await self.evaluate({}, game="snake")
        self.assertNotIn("clear_rate", result)
        self.assertNotIn("cleared_episodes", result)
        self.assertNotIn("cleared", replays[100])


if __name__ == "__main__":
    unittest.main()
