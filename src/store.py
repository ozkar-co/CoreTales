"""Registro en memoria. Fase 1: sin SQLite."""

from __future__ import annotations

import copy
from typing import Any


def empty_scene() -> dict[str, Any]:
    return {
        "pc": None,
        "location": None,
        "time": {"value": 0, "unit": "day", "label": None},
    }


class Store:
    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {"scene": empty_scene()}
        self.events: list[Any] = []
        self.prose_log: list[str] = []

    def snapshot(self) -> Store:
        other = Store()
        other.entities = copy.deepcopy(self.entities)
        other.events = copy.deepcopy(self.events)
        other.prose_log = list(self.prose_log)
        return other

    def restore(self, other: Store) -> None:
        self.entities = other.entities
        self.events = other.events
        self.prose_log = other.prose_log

    def unique_slug(self, slug: str) -> str:
        if slug not in self.entities:
            return slug
        n = 2
        while f"{slug}-{n}" in self.entities:
            n += 1
        return f"{slug}-{n}"

    def apply_ops(self, ops: list[Any]) -> None:
        if not isinstance(ops, list):
            return
        for item in ops:
            if not isinstance(item, dict):
                continue
            kind = item.get("op")
            if kind == "set":
                slug = item.get("slug")
                key = item.get("key")
                if not isinstance(slug, str) or not isinstance(key, str):
                    continue
                if slug not in self.entities or not isinstance(
                    self.entities[slug], dict
                ):
                    self.entities[slug] = {}
                self.entities[slug][key] = item.get("value")
            elif kind == "spawn":
                slug = item.get("slug")
                if not isinstance(slug, str):
                    continue
                data = item.get("data")
                if not isinstance(data, dict):
                    data = {}
                self.entities[self.unique_slug(slug)] = dict(data)
            elif kind == "delete":
                slug = item.get("slug")
                if isinstance(slug, str) and slug != "scene":
                    self.entities.pop(slug, None)
            elif kind == "event":
                self.events.append(item.get("data"))

    def scene_packet(self) -> dict[str, Any]:
        scene = self.entities.get("scene") or empty_scene()
        pc = scene.get("pc")
        loc = scene.get("location")
        who = self.entities.get(pc) if isinstance(pc, str) else None
        where = self.entities.get(loc) if isinstance(loc, str) else None
        return {
            "scene": scene,
            "who": {"slug": pc, "data": who} if pc else None,
            "where": {"slug": loc, "data": where} if loc else None,
            "when": scene.get("time"),
        }
