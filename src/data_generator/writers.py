"""file writers, one per source-system quirk - and the ingestion manifest.

xlsx yazımında bir tekrar-üretilebilirlik hatası buldum: .xlsx bir zip, ve zip
her girdiye o anki zamanı yazıyor. aynı seed'le iki kere çalıştırınca sadece bu
dosya farklı çıkıyordu. _normalise_zip_timestamps bunu sabit bir tarihe
sabitliyor - tools/verify_determinism.py bunu ilk çalıştırdığımda yakaladı.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

import pandas as pd

FileFormat = Literal["csv", "json", "jsonl", "xlsx"]
LoadType = Literal["full", "incremental"]

@dataclass
class SourceSpec:
    """everything bronze needs to know in order to read one source entity"""

    source_system: str
    entity: str
    file_format: FileFormat
    load_type: LoadType

    key_columns: tuple[str, ...] = ()

    watermark_column: str | None = None

    delimiter: str = ","
    decimal: str = "."
    encoding: str = "utf-8"
    has_header: bool = True

    date_partitioned: bool = False

    file_stem: str | None = None
    sheet_name: str | None = None

    files: list[str] = field(default_factory=list)
    row_count: int = 0

    @property
    def target_table(self) -> str:
        """bronze table this entity lands in"""
        return f"bronze.{self.source_system}_{self.entity}"

    @property
    def file_pattern(self) -> str:
        """glob the pipeline uses to find this entity's files"""
        stem = self.file_stem or self.entity
        if self.date_partitioned:
            return f"{self.source_system}/{self.entity}/*/{stem}_*.{self.file_format}"
        return f"{self.source_system}/{stem}_*.{self.file_format}"

class SourceWriter:
    """writes source files and records what it wrote"""

    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.specs: dict[str, SourceSpec] = {}

    def register(self, spec: SourceSpec) -> SourceSpec:
        key = f"{spec.source_system}.{spec.entity}"
        self.specs[key] = spec
        return spec

    def write(
        self,
        spec: SourceSpec,
        rows: Iterable[dict[str, Any]],
        *,
        suffix: str,
        sheet_name: str | None = None,
    ) -> Path:
        """write one file for `spec`"""
        rows = list(rows)
        frame = pd.DataFrame(rows)

        path = self._path_for(spec, suffix)
        path.parent.mkdir(parents=True, exist_ok=True)

        if spec.file_format == "csv":
            self._write_csv(frame, path, spec)
        elif spec.file_format == "json":
            self._write_json(rows, path)
        elif spec.file_format == "jsonl":
            self._write_jsonl(rows, path)
        elif spec.file_format == "xlsx":
            self._write_xlsx(frame, path, sheet_name or spec.sheet_name or spec.entity)
        else:
            raise ValueError(f"unsupported format {spec.file_format!r}")

        relative = str(path.relative_to(self.output_path)).replace("\\", "/")
        if relative not in spec.files:
            spec.files.append(relative)
        spec.row_count += len(rows)
        return path

    def _path_for(self, spec: SourceSpec, suffix: str) -> Path:
        base = self.output_path / spec.source_system
        stem = spec.file_stem or spec.entity
        if spec.date_partitioned:
            return base / spec.entity / suffix / f"{stem}_{suffix}.{spec.file_format}"
        return base / f"{stem}_{suffix}.{spec.file_format}"

    @staticmethod
    def _write_csv(frame: pd.DataFrame, path: Path, spec: SourceSpec) -> None:

        frame.to_csv(
            path,
            index=False,
            sep=spec.delimiter,
            decimal=spec.decimal,
            encoding=spec.encoding,
            header=spec.has_header,
            lineterminator="\n",
        )

    @staticmethod
    def _write_json(rows: list[dict[str, Any]], path: Path) -> None:

        path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=None, default=str),
            encoding="utf-8",
        )

    @staticmethod
    def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:

        with path.open("w", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, default=str))
                handle.write("\n")

    @staticmethod
    def _write_xlsx(frame: pd.DataFrame, path: Path, sheet_name: str) -> None:

        mode = "a" if path.exists() else "w"
        kwargs: dict[str, Any] = {"engine": "openpyxl", "mode": mode}
        if mode == "a":
            kwargs["if_sheet_exists"] = "replace"
        with pd.ExcelWriter(path, **kwargs) as writer:
            frame.to_excel(writer, sheet_name=sheet_name, index=False)

        SourceWriter._normalise_zip_timestamps(path)

    @staticmethod
    def _normalise_zip_timestamps(path: Path) -> None:
        """rewrite an .xlsx so two runs produce identical bytes"""
        import re
        import zipfile

        fixed_time = (1980, 1, 1, 0, 0, 0)
        fixed_iso = "1980-01-01T00:00:00Z"

        with zipfile.ZipFile(path, "r") as source:
            entries = [(item, source.read(item.filename)) for item in source.infolist()]

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
            for item, data in entries:
                if item.filename == "docProps/core.xml":
                    text = data.decode("utf-8")

                    text = re.sub(
                        r"(<dcterms:(?:created|modified)[^>]*>)[^<]*(</dcterms:)",
                        r"\g<1>" + fixed_iso + r"\g<2>",
                        text,
                    )
                    data = text.encode("utf-8")
                stamped = zipfile.ZipInfo(item.filename, date_time=fixed_time)
                stamped.compress_type = item.compress_type
                stamped.external_attr = item.external_attr
                target.writestr(stamped, data)

    def write_manifest(self) -> Path:
        """emit `_manifest.json`, the seed for `ctl.source_config`"""
        entries = []
        for key in sorted(self.specs):
            spec = self.specs[key]
            record = asdict(spec)
            record["target_table"] = spec.target_table
            record["file_pattern"] = spec.file_pattern
            record["file_count"] = len(spec.files)

            record.pop("files")
            entries.append(record)

        path = self.output_path / "_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def summary(self) -> str:
        lines = [f"{'source.entity':<28}{'fmt':<7}{'load':<13}{'rows':>10}  files"]
        lines.append("-" * 74)
        total = 0
        for key in sorted(self.specs):
            spec = self.specs[key]
            total += spec.row_count
            lines.append(
                f"{key:<28}{spec.file_format:<7}{spec.load_type:<13}"
                f"{spec.row_count:>10,}  {len(spec.files)}"
            )
        lines.append("-" * 74)
        lines.append(f"{'TOTAL':<48}{total:>10,}")
        return "\n".join(lines)
