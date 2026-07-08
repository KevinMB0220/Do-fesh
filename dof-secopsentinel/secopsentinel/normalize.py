import csv
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Tuple

class SecopNormalizer:
    def __init__(self, safe_fields: List[str], normalized_dir: Path):
        self.safe_fields = safe_fields
        self.normalized_dir = Path(normalized_dir)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def to_number(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            # Remove commas and strip whitespace
            clean_val = str(value).replace(",", "").strip()
            return float(clean_val)
        except Exception:
            return 0.0

    def clean_row(self, row: Dict[str, str], filename: str) -> Dict[str, str]:
        """Filters out non-safe fields, strips values, and appends the source filename."""
        clean = {}
        for field in self.safe_fields:
            if field == "fuente_archivo":
                continue
            val = row.get(field, "")
            clean[field] = str(val or "").strip()
        clean["fuente_archivo"] = filename
        return clean

    def normalize(self, input_files: List[Path], output_filename: str = "secop_contratos_normalizados.csv") -> Tuple[Path, Dict[str, Any]]:
        """
        Processes a list of raw CSV files: sanitizes them, removes duplicates, and outputs
        a single normalized CSV file.
        """
        rows_by_id = {}
        source_counts = {}
        file_hashes = {}

        for filepath in sorted(input_files):
            if not filepath.exists():
                print(f"Warning: File {filepath} does not exist. Skipping.")
                continue

            file_hashes[filepath.name] = self.sha256_file(filepath)
            
            # Socrata UTF-8 files often contain BOM, open with utf-8-sig
            with filepath.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                count = 0

                for row in reader:
                    count += 1
                    contract_id = row.get("id_contrato", "").strip()

                    # Fallback ID generation if missing
                    if not contract_id:
                        contract_id = hashlib.sha256(
                            json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
                        ).hexdigest()[:24]

                    clean_data = self.clean_row(row, filepath.name)

                    # Deduplication strategy: keep the one with higher contract value
                    existing = rows_by_id.get(contract_id)
                    if existing is None or self.to_number(clean_data.get("valor_del_contrato")) > self.to_number(existing.get("valor_del_contrato")):
                        rows_by_id[contract_id] = clean_data

                source_counts[filepath.name] = count

        normalized_rows = list(rows_by_id.values())
        output_csv = self.normalized_dir / output_filename
        
        # Write normalized fields to CSV
        with output_csv.open("w", encoding="utf-8", newline="") as f:
            # Ensure "fuente_archivo" is in headers if not already
            headers = self.safe_fields.copy()
            if "fuente_archivo" not in headers:
                headers.append("fuente_archivo")
                
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(normalized_rows)

        # Compute summary metrics for the normalizer run
        total_value = sum(self.to_number(r.get("valor_del_contrato")) for r in normalized_rows)
        high_value = [r for r in normalized_rows if self.to_number(r.get("valor_del_contrato")) >= 500_000_000]
        direct_high = [
            r for r in normalized_rows
            if "directa" in (r.get("modalidad_de_contratacion") or "").lower()
            and self.to_number(r.get("valor_del_contrato")) >= 500_000_000
        ]

        metrics = {
            "input_files": [f.name for f in input_files],
            "input_file_hashes_sha256": file_hashes,
            "source_row_counts": source_counts,
            "total_unique_contracts": len(normalized_rows),
            "total_contract_value": total_value,
            "high_value_contracts_500m_or_more": len(high_value),
            "direct_high_value_contracts_500m_or_more": len(direct_high),
        }

        return output_csv, metrics
