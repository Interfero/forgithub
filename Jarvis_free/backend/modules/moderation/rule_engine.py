"""
Слой 1: детерминированные правила (regex + внешний список мата).
Консервативный режим: WARN только при явных шаблонах и (опционально) обращении к Jarvis.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from modules.moderation.text_normalize import collapse_spaced_letters, normalize_for_rules
from modules.moderation.types import ModerationAction, RuleEngineResult

_log = logging.getLogger("jarvis.moderation.rules")

_ACTION_RANK = {"OK": 0, "WARN": 1, "BLOCK": 2}


def _config_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config"


def _data_dir() -> Path:
    from modules.app_paths import user_data_dir

    return user_data_dir()


def _resolve_file(path: str) -> Path:
    p = Path(path)
    if p.is_file():
        return p
    for base in (_data_dir(), Path(__file__).resolve().parent.parent.parent / "data"):
        candidate = base / path
        if candidate.is_file():
            return candidate
    return _data_dir() / path


def _builtin_config() -> dict[str, Any]:
    """Встроенный конфиг, если YAML недоступен."""
    return {
        "settings": {
            "ml_threshold": 0.85,
            "ml_enabled": False,
            "warn_requires_jarvis_address": True,
        },
        "rules": [
            {
                "name": "direct_threat",
                "patterns": [
                    "чтобы ты сдох",
                    "чтоб ты сдох",
                    "сдохни",
                    "умри",
                ],
                "action": "BLOCK",
                "requires_jarvis_address": False,
                "response": "Угроза в сообщении. Диалог остановлен.",
            },
            {
                "name": "go_away_obscene",
                "patterns": [
                    "(пошел|пошёл|иди) на (хуй|хер)",
                    "заткнись",
                    "иди нахуй",
                ],
                "action": "WARN",
                "requires_jarvis_address": True,
                "response": "Шеф, такой тон ко мне недопустим.",
            },
            {
                "name": "obscene_lexicon",
                "file": "profanity_list.txt",
                "action": "WARN",
                "requires_jarvis_address": True,
                "response": "Без грубости в мой адрес.",
            },
            {
                "name": "jarvis_insult_explicit",
                "patterns": [
                    "ты (чучело|дебил|идиот|кретин|урод|тупой|тупая)",
                    "тупой (бот|jarvis|джарвис)",
                ],
                "action": "WARN",
                "requires_jarvis_address": True,
                "response": "Это оскорбление в мой адрес.",
            },
        ],
    }


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        _log.warning("PyYAML не установлен — встроенный конфиг модерации.")
        return _builtin_config()
    if not path.is_file():
        return _builtin_config()
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or not data.get("rules"):
        return _builtin_config()
    return data


@dataclass
class _CompiledRule:
    name: str
    action: ModerationAction
    response: str | None
    requires_jarvis: bool
    patterns: list[re.Pattern[str]]
    words: list[str]


class ModerationRuleEngine:
    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or (_config_dir() / "moderation_rules.yaml")
        self._settings: dict[str, Any] = {}
        self._compiled: list[_CompiledRule] = []
        self.reload()

    def reload(self) -> None:
        cfg = _load_yaml(self._config_path)
        self._settings = dict(cfg.get("settings") or {})
        self._compiled = []
        default_requires = bool(self._settings.get("warn_requires_jarvis_address", True))

        for rule in list(cfg.get("rules") or []):
            name = str(rule.get("name") or "rule")
            action = str(rule.get("action") or "WARN").upper()
            if action not in ("OK", "WARN", "BLOCK"):
                action = "WARN"
            response = rule.get("response")
            if isinstance(response, str):
                response = response.strip()
            else:
                response = None
            requires = bool(rule.get("requires_jarvis_address", default_requires))
            patterns: list[re.Pattern[str]] = []
            words: list[str] = []

            for raw in rule.get("patterns") or []:
                pat = str(raw).strip()
                if not pat:
                    continue
                try:
                    patterns.append(re.compile(pat, re.I | re.UNICODE))
                except re.error:
                    _log.warning("moderation: неверный regex %s в %s", pat, name)

            file_ref = rule.get("file")
            if file_ref:
                path = _resolve_file(str(file_ref))
                if path.is_file():
                    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        words.append(normalize_for_rules(line))
                else:
                    _log.warning("moderation: файл списка не найден: %s", path)

            if patterns or words:
                self._compiled.append(
                    _CompiledRule(
                        name=name,
                        action=action,
                        response=response,
                        requires_jarvis=requires,
                        patterns=patterns,
                        words=words,
                    )
                )

    @property
    def settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def evaluate(
        self,
        text: str,
        *,
        jarvis_directed: bool,
    ) -> RuleEngineResult:
        raw = (text or "").strip()
        if len(raw) < 2:
            return RuleEngineResult(False, "OK")

        norm = normalize_for_rules(collapse_spaced_letters(raw))
        best_action: ModerationAction = "OK"
        best_response: str | None = None
        best_rule: str | None = None

        for rule in self._compiled:
            if rule.requires_jarvis and not jarvis_directed:
                continue
            matched = False
            if rule.words:
                matched = any(
                    re.search(rf"(?<![а-яa-z]){re.escape(w)}(?![а-яa-z])", norm)
                    for w in rule.words
                    if len(w) >= 3
                )
            if not matched and rule.patterns:
                matched = any(p.search(norm) for p in rule.patterns)
            if not matched:
                continue
            if _ACTION_RANK[rule.action] > _ACTION_RANK[best_action]:
                best_action = rule.action
                best_response = rule.response
                best_rule = rule.name

        if best_action == "OK":
            return RuleEngineResult(False, "OK")
        return RuleEngineResult(
            True,
            best_action,
            response=best_response,
            rule_name=best_rule,
        )
