"""Параметры с указанием происхождения.

Любое значение в YAML можно записать либо просто числом, либо словарём
``{value: ..., status: ..., source: ..., note: ...}``. Статусы:

* ``experimental`` — задано техзаданием конкретного эксперимента;
* ``document``     — взято из документов (диссертация, презентация, тезисы);
* ``assumption``   — расчётное допущение (обязательно попадает в отчёт);
* ``derived``      — вычислено из других параметров;
* ``unknown``      — значение не установлено (использовать нельзя без явного решения).

Загрузчик «разворачивает» такие записи в обычные значения и параллельно
собирает реестр провенанса, который сохраняется в метаданных каждого запуска.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

STATUSES = ("experimental", "document", "assumption", "derived", "unknown")


@dataclass
class ParamRecord:
    path: str
    value: Any
    status: str
    source: str = ""
    note: str = ""

    def as_dict(self) -> dict:
        return {"path": self.path, "value": self.value, "status": self.status,
                "source": self.source, "note": self.note}


@dataclass
class Provenance:
    records: list[ParamRecord] = field(default_factory=list)

    def add(self, rec: ParamRecord) -> None:
        self.records.append(rec)

    def assumptions(self) -> list[ParamRecord]:
        return [r for r in self.records if r.status in ("assumption", "unknown")]

    def as_list(self) -> list[dict]:
        return [r.as_dict() for r in self.records]


def _is_param(d: Any) -> bool:
    return isinstance(d, dict) and "value" in d and set(d) <= {"value", "status", "source", "note", "unit", "range"}


def unwrap(obj: Any, prov: Provenance | None = None, path: str = "") -> Any:
    """Рекурсивно заменить записи-параметры их значениями, собирая провенанс."""
    if _is_param(obj):
        status = obj.get("status", "document")
        if status not in STATUSES:
            raise ValueError(f"{path}: unknown status '{status}' (allowed: {STATUSES})")
        if status == "unknown" and obj["value"] is not None:
            raise ValueError(f"{path}: status 'unknown' must have value null")
        if prov is not None:
            prov.add(ParamRecord(path, obj["value"], status, obj.get("source", ""), obj.get("note", "")))
        return obj["value"]
    if isinstance(obj, dict):
        return {k: unwrap(v, prov, f"{path}.{k}" if path else k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [unwrap(v, prov, f"{path}[{i}]") for i, v in enumerate(obj)]
    return obj


def deep_merge(base: dict, override: dict) -> dict:
    """Рекурсивное слияние словарей (override имеет приоритет)."""
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and not _is_param(v):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out
