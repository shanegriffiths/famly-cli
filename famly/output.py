import dataclasses
import json


def to_jsonable(obj):
    if dataclasses.is_dataclass(obj):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    return obj


def emit(obj):
    print(json.dumps(to_jsonable(obj), indent=2, ensure_ascii=False))
