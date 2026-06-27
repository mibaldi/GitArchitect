"""Generic, type-driven JSON codec for the domain dataclasses.

Serialization walks any dataclass into plain JSON values; deserialization uses
the target type's annotations to rebuild the exact dataclasses, enums, tuples
and sets. This avoids hand-written mappers per model while staying strict about
the reconstructed types.
"""

from __future__ import annotations

import dataclasses
import enum
import functools
import types
import typing
from typing import Any


def to_jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in obj]
    return obj


def from_jsonable(target: Any, data: Any) -> Any:
    target = _unwrap_optional(target)
    if data is None:
        return None
    if dataclasses.is_dataclass(target) and isinstance(target, type):
        hints = _hints(target)
        kwargs = {
            f.name: from_jsonable(hints[f.name], data[f.name])
            for f in dataclasses.fields(target)
            if f.name in data
        }
        return target(**kwargs)
    if isinstance(target, type) and issubclass(target, enum.Enum):
        return target(data)

    origin = typing.get_origin(target)
    if origin in (list, set, frozenset):
        (elem,) = typing.get_args(target) or (Any,)
        return origin(from_jsonable(elem, item) for item in data)
    if origin is tuple:
        args = typing.get_args(target)
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(from_jsonable(args[0], item) for item in data)
        return tuple(from_jsonable(arg, item) for arg, item in zip(args, data, strict=False))
    if origin is dict:
        args = typing.get_args(target) or (str, Any)
        _, value_type = args
        return {key: from_jsonable(value_type, value) for key, value in data.items()}
    return data


def _unwrap_optional(target: Any) -> Any:
    origin = typing.get_origin(target)
    if origin is typing.Union or origin is types.UnionType:
        non_none = [arg for arg in typing.get_args(target) if arg is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return target


@functools.cache
def _hints(target: type) -> dict[str, Any]:
    return typing.get_type_hints(target)
