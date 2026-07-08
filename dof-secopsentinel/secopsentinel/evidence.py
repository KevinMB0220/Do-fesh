import csv
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import List, Dict, Any

class SecopEvidenceGenerator:
    def __init__(self, evidence_dir: Path, reports_dir: Path):
        self.evidence_dir = Path(evidence_dir)
        self.reports_dir = Path(reports_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def to_number(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            return float(str(value).replace(",", "").strip())
        except Exception:
            return 0.0

    def generate_all(self, 
                     normalization_metrics: Dict[str, Any], 
                     findings: List[Dict[str, Any]], 
                     total_contracts: int,
                     original_rows: List[Dict[str, Any]],
                     evidence_pack_filename: str = "secop_evidence_pack.json",
                     findings_filename: str = "secop_findings_dof.json",
                     summary_txt_filename: str = "secop_hallazgos_resumen.txt",
                     findings_csv_filename: str = "secop_hallazgos_dof.csv") -> Dict[str, Path]:
        """
        Generates and saves the evidence pack JSON, findings summary JSON, text summary, and findings CSV.
        """
        generated_time = datetime.now().isoformat(timespec="seconds")
        
        # 1. Save findings CSV in reports
        output_csv = self.reports_dir / findings_csv_filename
        fieldnames = list(findings[0].keys()) if findings else []
        with output_csv.open("w", encoding="utf-8", newline="") as f:
            if fieldnames:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(findings)

        # Count frequencies for summary
        all_flags = []
        for f in findings:
            all_flags.extend(f["flags"].split("|"))
        flag_counts = dict(Counter(all_flags))

        review_count = sum(1 for f in findings if f["risk_level"] == "REVIEW")
        block_count = sum(1 for f in findings if f["risk_level"] == "BLOCK")

        dof_limits = [
            "Las banderas son criterios de priorización, no conclusiones de irregularidad o delito.",
            "Cada caso debe verificarse manualmente en el expediente SECOP usando urlproceso.",
            "El análisis usa únicamente columnas no sensibles seleccionadas para el piloto.",
            "Los datos dependen de la calidad, completitud y actualización de Datos Abiertos Colombia."
        ]

        # 2. Build and save findings JSON
        findings_summary = {
            "generated_at": generated_time,
            "total_contracts_analyzed": total_contracts,
            "total_findings": len(findings),
            "review_findings": review_count,
            "block_findings": block_count,
            "flag_counts": flag_counts,
            "top_20_findings_by_value": findings[:20],
            "dof_interpretation_limits": dof_limits
        }
        
        output_findings_json = self.evidence_dir / findings_filename
        with output_findings_json.open("w", encoding="utf-8") as f:
            json.dump(findings_summary, f, ensure_ascii=False, indent=2)

        # 3. Build and save evidence pack JSON
        # Top counters for normalization context
        by_entity = Counter(r["nombre_entidad"] for r in original_rows if r.get("nombre_entidad"))
        by_provider = Counter(r["proveedor_adjudicado"] for r in original_rows if r.get("proveedor_adjudicado"))
        by_modality = Counter(r["modalidad_de_contratacion"] for r in original_rows if r.get("modalidad_de_contratacion"))

        evidence_pack = {
            "generated_at": generated_time,
            "input_files": normalization_metrics.get("input_files", []),
            "input_file_hashes_sha256": normalization_metrics.get("input_file_hashes_sha256", {}),
            "source_row_counts": normalization_metrics.get("source_row_counts", {}),
            "total_unique_contracts": total_contracts,
            "total_contract_value": normalization_metrics.get("total_contract_value", 0.0),
            "high_value_contracts_500m_or_more": normalization_metrics.get("high_value_contracts_500m_or_more", 0),
            "direct_high_value_contracts_500m_or_more": normalization_metrics.get("direct_high_value_contracts_500m_or_more", 0),
            "top_entities": by_entity.most_common(20),
            "top_providers": by_provider.most_common(20),
            "modalities": by_modality.most_common(),
            "dof_limits": dof_limits
        }

        output_evidence_json = self.evidence_dir / evidence_pack_filename
        with output_evidence_json.open("w", encoding="utf-8") as f:
            json.dump(evidence_pack, f, ensure_ascii=False, indent=2)

        # 4. Generate text summary report
        output_txt = self.reports_dir / summary_txt_filename
        with output_txt.open("w", encoding="utf-8") as f:
            f.write("RESUMEN HALLAZGOS DOF-SECOP II\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Generado: {generated_time}\n")
            f.write(f"Contratos analizados: {total_contracts}\n")
            f.write(f"Hallazgos totales: {len(findings)}\n")
            f.write(f"Hallazgos REVIEW: {review_count}\n")
            f.write(f"Hallazgos BLOCK: {block_count}\n\n")
            
            f.write("CONTEO POR BANDERA:\n")
            for flag, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
                f.write(f"- {flag}: {count}\n")
            f.write("\n")

            f.write("TOP 10 HALLAZGOS POR VALOR:\n")
            for i, find in enumerate(findings[:10]):
                val_formatted = f"{self.to_number(find['valor_del_contrato']):,.0f} COP"
                f.write(f"{i+1}. {find['nombre_entidad']} | {find['proveedor_adjudicado']} | {val_formatted} | {find['flags']} | {find['urlproceso']}\n")
            f.write("\n")

            f.write("LÍMITES DE INTERPRETACIÓN DOF:\n")
            for limit in dof_limits:
                f.write(f"- {limit}\n")

        return {
            "findings_csv": output_csv,
            "findings_json": output_findings_json,
            "evidence_pack_json": output_evidence_json,
            "summary_txt": output_txt
        }
