from collections import Counter
from typing import List, Dict, Any, Tuple

class SecopRulesEngine:
    def __init__(self, rules_config: List[Dict[str, Any]]):
        self.rules_config = rules_config
        # Quick lookup for rule structures by ID
        self.rule_by_id = {r["id"]: r for r in rules_config}

    @staticmethod
    def to_number(value: Any) -> float:
        try:
            if value is None or value == "":
                return 0.0
            return float(str(value).replace(",", "").strip())
        except Exception:
            return 0.0

    def compute_counters(self, rows: List[Dict[str, str]]) -> Dict[Tuple[str, str], int]:
        """Calculates frequency of entity-provider pairs in the dataset."""
        return Counter(
            (
                (r.get("nombre_entidad") or "").strip(),
                (r.get("proveedor_adjudicado") or "").strip()
            )
            for r in rows
            if r.get("nombre_entidad") and r.get("proveedor_adjudicado")
        )

    def evaluate_row(self, row: Dict[str, str], pair_counter: Dict[Tuple[str, str], int]) -> Tuple[List[str], List[str]]:
        """
        Evaluates a single contract row against the loaded rules config.
        Returns a tuple of (activated_flag_ids, explanations).
        """
        flags = []
        reasons = []

        valor = self.to_number(row.get("valor_del_contrato"))
        dias_adicionados = self.to_number(row.get("dias_adicionados"))
        modalidad = (row.get("modalidad_de_contratacion") or "").lower()
        entidad = (row.get("nombre_entidad") or "").strip()
        proveedor = (row.get("proveedor_adjudicado") or "").strip()
        url = (row.get("urlproceso") or "").strip()

        # Rule 1: REVIEW_HIGH_VALUE
        rule_cfg = self.rule_by_id.get("REVIEW_HIGH_VALUE")
        if rule_cfg and valor >= rule_cfg.get("threshold", 500000000):
            flags.append("REVIEW_HIGH_VALUE")
            reasons.append(rule_cfg["meaning"])

        # Rule 2: REVIEW_DIRECT_HIGH_VALUE
        rule_cfg = self.rule_by_id.get("REVIEW_DIRECT_HIGH_VALUE")
        if rule_cfg:
            kw = rule_cfg.get("keyword", "directa").lower()
            threshold = rule_cfg.get("threshold", 500000000)
            if kw in modalidad and valor >= threshold:
                flags.append("REVIEW_DIRECT_HIGH_VALUE")
                reasons.append(rule_cfg["meaning"])

        # Rule 3: REVIEW_REPEATED_PROVIDER_ENTITY
        rule_cfg = self.rule_by_id.get("REVIEW_REPEATED_PROVIDER_ENTITY")
        if rule_cfg:
            threshold = rule_cfg.get("threshold", 3)
            if pair_counter.get((entidad, proveedor), 0) >= threshold:
                flags.append("REVIEW_REPEATED_PROVIDER_ENTITY")
                reasons.append(rule_cfg["meaning"])

        # Rule 4: REVIEW_LONG_ADDITION_DAYS
        rule_cfg = self.rule_by_id.get("REVIEW_LONG_ADDITION_DAYS")
        if rule_cfg and dias_adicionados >= rule_cfg.get("threshold", 90):
            flags.append("REVIEW_LONG_ADDITION_DAYS")
            reasons.append(rule_cfg["meaning"])

        # Rule 5: BLOCK_MISSING_URL
        rule_cfg = self.rule_by_id.get("BLOCK_MISSING_URL")
        if rule_cfg:
            is_empty_or_invalid = not url or url.lower() in ["no definido", "sin descripcion", "sin descripción", "no aplica"]
            if is_empty_or_invalid:
                flags.append("BLOCK_MISSING_URL")
                reasons.append(rule_cfg["meaning"])

        return flags, reasons

    def analyze_dataset(self, rows: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Runs evaluations on all rows, building findings records for contracts with activated flags.
        """
        pair_counter = self.compute_counters(rows)
        findings = []

        for r in rows:
            flags, reasons = self.evaluate_row(r, pair_counter)
            
            if flags:
                risk_level = "BLOCK" if any(f.startswith("BLOCK") for f in flags) else "REVIEW"
                finding_item = {
                    "risk_level": risk_level,
                    "flags": "|".join(flags),
                    "reasons": " ".join(reasons),
                    "nombre_entidad": r.get("nombre_entidad", ""),
                    "departamento": r.get("departamento", ""),
                    "ciudad": r.get("ciudad", ""),
                    "sector": r.get("sector", ""),
                    "id_contrato": r.get("id_contrato", ""),
                    "referencia_del_contrato": r.get("referencia_del_contrato", ""),
                    "estado_contrato": r.get("estado_contrato", ""),
                    "tipo_de_contrato": r.get("tipo_de_contrato", ""),
                    "modalidad_de_contratacion": r.get("modalidad_de_contratacion", ""),
                    "justificacion_modalidad_de": r.get("justificacion_modalidad_de", ""),
                    "fecha_de_firma": r.get("fecha_de_firma", ""),
                    "proveedor_adjudicado": r.get("proveedor_adjudicado", ""),
                    "codigo_proveedor": r.get("codigo_proveedor", ""),
                    "valor_del_contrato": r.get("valor_del_contrato", ""),
                    "valor_pagado": r.get("valor_pagado", ""),
                    "dias_adicionados": r.get("dias_adicionados", ""),
                    "objeto_del_contrato": r.get("objeto_del_contrato", ""),
                    "descripcion_del_proceso": r.get("descripcion_del_proceso", ""),
                    "urlproceso": r.get("urlproceso", ""),
                    "fuente_archivo": r.get("fuente_archivo", "")
                }
                findings.append(finding_item)

        # Sort findings: BLOCKS first, then by value descending, then by entity name
        findings_sorted = sorted(
            findings,
            key=lambda x: (
                x["risk_level"] != "BLOCK",
                -self.to_number(x.get("valor_del_contrato")),
                x.get("nombre_entidad", "")
            )
        )
        return findings_sorted
