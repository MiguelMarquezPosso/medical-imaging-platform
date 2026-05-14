"""Series domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SeriesQuery:
    modality: str | None = None
    series_description: str | None = None
    limit: int = 100
    offset: int = 0
    extras: dict[str, str] = field(default_factory=dict)

    def to_dicomweb_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.modality:
            params["Modality"] = self.modality
        if self.series_description:
            params["SeriesDescription"] = self.series_description
        params["limit"] = str(self.limit)
        params["offset"] = str(self.offset)
        params.update(self.extras)
        return params
