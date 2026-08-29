import asyncio
import sys
from pathlib import Path
import unittest

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parents[1] / "docker" / "gateway"))
from json_guard import JsonRepairError, validate_or_repair


class Result(BaseModel):
    value: int


class JsonGuardTest(unittest.TestCase):
    def test_valid_json_never_regenerates(self):
        async def regenerate(_: str) -> str:
            raise AssertionError("repair must not be called")

        self.assertEqual(asyncio.run(validate_or_repair('{"value": 7}', Result, regenerate)), {"value": 7})

    def test_invalid_json_repairs_once(self):
        calls = 0

        async def regenerate(_: str) -> str:
            nonlocal calls
            calls += 1
            return '{"value": 9}'

        self.assertEqual(asyncio.run(validate_or_repair('{broken', Result, regenerate)), {"value": 9})
        self.assertEqual(calls, 1)

    def test_invalid_json_fails_after_single_repair(self):
        async def regenerate(_: str) -> str:
            return "still invalid"

        with self.assertRaises(JsonRepairError):
            asyncio.run(validate_or_repair('{broken', Result, regenerate))
