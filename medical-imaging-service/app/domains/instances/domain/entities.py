"""Instance domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class InstanceQuery:
    sop_class_uid: str | None = None
    limit: int = 200
    offset: int = 0
    extras: dict[str, str] = field(default_factory=dict)

    def to_dicomweb_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.sop_class_uid:
            params["SOPClassUID"] = self.sop_class_uid
        params["limit"] = str(self.limit)
        params["offset"] = str(self.offset)
        params.update(self.extras)
        return params
