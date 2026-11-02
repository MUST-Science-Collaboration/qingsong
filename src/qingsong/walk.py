"""Walk records for localized texts and references."""

import types
import typing
from collections.abc import Iterator

from pydantic import BaseModel

from qingsong import ids
from qingsong.schema import LocalizedText


def is_localized(annotation: object) -> bool:
    if annotation == LocalizedText:
        return True
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        return any(is_localized(argument) for argument in typing.get_args(annotation))
    return False


def localized_texts(model: BaseModel, path: str = "") -> Iterator[tuple[str, dict[str, str]]]:
    """Yield (field path, {language: text}) for every localized text inside a model."""
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        here = f"{path}.{name}" if path else name
        if value is None:
            continue
        if is_localized(field.annotation) and isinstance(value, dict):
            yield here, value
        else:
            yield from nested_texts(value, here)


def nested_texts(value: object, path: str) -> Iterator[tuple[str, dict[str, str]]]:
    if isinstance(value, BaseModel):
        yield from localized_texts(value, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if (
                isinstance(item, dict)
                and item
                and all(isinstance(text, str) for text in item.values())
            ):
                yield f"{path}[{index}]", item
            else:
                yield from nested_texts(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from nested_texts(item, f"{path}.{key}")


def text_references(model: BaseModel) -> Iterator[tuple[str, str, str | None]]:
    """Yield (field path, target ID, section key) for every [[…]] reference in localized texts."""
    for path, texts in localized_texts(model):
        for text in texts.values():
            for target, key in ids.references_in_text(text):
                yield path, target, key
