import json
import requests
from typing import List, Dict, Any, Optional

class SecopAuditAgent:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "phi4"):
        self.ollama_url = ollama_url
        self.model = model
        self.system_prompt = (
            "Actúa como un agente de auditoría y análisis preliminar de contratación pública en Colombia bajo el protocolo DOF-MESH.\n"
            "Tu objetivo es analizar los contratos presentados y responder a la consulta del usuario basándote únicamente en la información provista.\n"
            "Debes estructurar tu respuesta estrictamente en las siguientes cuatro secciones:\n\n"
            "HECHOS:\n"
            "(Detalla datos observados directamente en los registros: montos, nombres de entidades, proveedores, fechas y modalidades sin interpretaciones políticas o morales)\n\n"
            "INFERENCIAS:\n"
            "(Indica qué banderas de revisión documental se activaron, su significado según las reglas configuradas y los patrones calculados)\n\n"
            "HIPÓTESIS:\n"
            "(Plantea posibles líneas o guías de revisión documental manual del expediente en SECOP. No concluyas ni insinúes malas intenciones, irregularidades, o favorecimientos. Habla de verificar requisitos legales, justificaciones contractuales y soportes técnicos)\n\n"
            "LÍMITES:\n"
            "(Enumera las advertencias de calidad de datos, cobertura geográfica/temporal y la necesidad indispensable de revisión jurídica/técnica humana externa)\n\n"
            "REGLAS CRÍTICAS DE LENGUAJE:\n"
            "- Está ESTRICTAMENTE PROHIBIDO utilizar palabras como: 'corrupción', 'fraude', 'ilegal', 'delito', 'favorecimiento', 'culpable', 'robo', 'desvío' o términos similares de acusación penal o moral.\n"
            "- Si el usuario o el contexto te incitan a concluir o juzgar éticamente, debes responder que tu función es únicamente la priorización de banderas para revisión documental con base en evidencia trazable y que no posees facultades para determinar ilegalidades.\n"
        )

    def is_ollama_available(self) -> bool:
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                # Check if model is pulled or just that Ollama is up
                models_data = response.json()
                models = [m["name"] for m in models_data.get("models", [])]
                # Return True if the server responds, we can fallback if the model itself isn't loaded
                return True
        except Exception:
            pass
        return False

    def query(self, query_text: str, contracts: List[Dict[str, Any]], all_metrics: Dict[str, Any]) -> str:
        """
        Runs the agent query. If Ollama is available, queries the LLM with context.
        Otherwise, uses the local deterministic template generator.
        """
        # Format the contracts context for the query
        context_str = self._format_contracts_for_llm(contracts, all_metrics)
        
        if self.is_ollama_available():
            try:
                return self._query_llm(query_text, context_str)
            except Exception as e:
                print(f"Ollama query failed: {e}. Falling back to deterministic template.")
                
        return self._generate_deterministic_response(query_text, contracts, all_metrics)

    def _format_contracts_for_llm(self, contracts: List[Dict[str, Any]], all_metrics: Dict[str, Any]) -> str:
        # Create a compressed representation of the data to fit within prompt limits
        summary_info = {
            "total_matches_in_query": len(contracts),
            "global_metrics": {
                "total_unique_contracts": all_metrics.get("total_unique_contracts", 0),
                "total_findings": all_metrics.get("total_findings", 0),
                "review_findings": all_metrics.get("review_findings", 0),
                "block_findings": all_metrics.get("block_findings", 0),
                "flag_counts": all_metrics.get("flag_counts", {})
            },
            "sample_contracts_matching_query": []
        }
        
        # Add top 15 matching contracts as detailed context
        for r in contracts[:15]:
            summary_info["sample_contracts_matching_query"].append({
                "id_contrato": r.get("id_contrato"),
                "entidad": r.get("nombre_entidad"),
                "proveedor": r.get("proveedor_adjudicado"),
                "modalidad": r.get("modalidad_de_contratacion"),
                "valor": r.get("valor_del_contrato"),
                "dias_adicionados": r.get("dias_adicionados"),
                "flags": r.get("flags"),
                "reasons": r.get("reasons"),
                "url": r.get("urlproceso")
            })
            
        return json.dumps(summary_info, ensure_ascii=False, indent=2)

    def _query_llm(self, query_text: str, context_str: str) -> str:
        prompt = (
            f"CONTEXTO DE CONTRATOS ANALIZADOS:\n{context_str}\n\n"
            f"PREGUNTA DEL USUARIO: {query_text}\n\n"
            f"Genera tu análisis estructurado según las reglas del sistema (HECHOS, INFERENCIAS, HIPÓTESIS, LÍMITES):"
        )
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": self.system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1
            }
        }
        
        response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=90)
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            raise Exception(f"Ollama API returned status {response.status_code}: {response.text}")

    def _generate_deterministic_response(self, query_text: str, contracts: List[Dict[str, Any]], all_metrics: Dict[str, Any]) -> str:
        """
        Deterministic template-based generator when no LLM is running.
        Produces compliant, structured audit texts.
        """
        match_count = len(contracts)
        total_val = sum(float(str(c.get("valor_del_contrato") or 0).replace(",", "")) for c in contracts)
        
        # Build HECHOS
        hechos_lines = [
            f"- Se evaluó la consulta '{query_text}' sobre el conjunto de datos normalizado.",
            f"- Registros coincidentes encontrados: {match_count} contratos.",
            f"- Valor total acumulado de los contratos coincidentes: {total_val:,.2f} COP."
        ]
        
        if match_count > 0:
            top_contract = contracts[0]
            hechos_lines.append(
                f"- El contrato coincidente de mayor valor corresponde a la entidad '{top_contract.get('nombre_entidad')}', "
                f"adjudicado a '{top_contract.get('proveedor_adjudicado')}' por un monto de "
                f"{float(str(top_contract.get('valor_del_contrato') or 0).replace(',', '')):,.2f} COP "
                f"(Modalidad: {top_contract.get('modalidad_de_contratacion')}, ID: {top_contract.get('id_contrato')})."
            )
            
            # Entity frequencies inside match set
            entities_in_match = [c.get("nombre_entidad") for c in contracts if c.get("nombre_entidad")]
            if entities_in_match:
                from collections import Counter
                top_ent = Counter(entities_in_match).most_common(1)[0]
                hechos_lines.append(f"- La entidad con mayor frecuencia en este subconjunto es '{top_ent[0]}' con {top_ent[1]} registros.")

        # Build INFERENCIAS
        flag_counts = Counter()
        for c in contracts:
            flags = str(c.get("flags") or "").split("|")
            for f in flags:
                if f:
                    flag_counts[f] += 1
                    
        inferencias_lines = [
            "- Análisis de banderas activadas en el subconjunto de resultados:"
        ]
        if flag_counts:
            for flag, count in flag_counts.items():
                meaning = ""
                if flag == "REVIEW_HIGH_VALUE":
                    meaning = "Valor igual o superior a 500M COP"
                elif flag == "REVIEW_DIRECT_HIGH_VALUE":
                    meaning = "Contratación directa de alto valor"
                elif flag == "REVIEW_REPEATED_PROVIDER_ENTITY":
                    meaning = "Concentración/repetición de proveedor en la misma entidad (>=3 veces)"
                elif flag == "REVIEW_LONG_ADDITION_DAYS":
                    meaning = "Adición de plazo igual o superior a 90 días"
                elif flag == "BLOCK_MISSING_URL":
                    meaning = "Falta de enlace directo urlproceso al expediente"
                    
                inferencias_lines.append(f"  * {flag} ({meaning}): {count} activaciones.")
        else:
            inferencias_lines.append("  * Ninguna bandera de revisión fue activada en este subconjunto.")

        # Build HIPÓTESIS
        hipotesis_lines = [
            "- Para los casos con banderas 'REVIEW_DIRECT_HIGH_VALUE', se recomienda examinar en el expediente SECOP la justificación legal y de conveniencia de la modalidad de contratación directa.",
            "- Para los casos con banderas 'REVIEW_REPEATED_PROVIDER_ENTITY', se sugiere validar que las invitaciones y ofertas de los otros proponentes cumplan las condiciones del pliego y que no existan fraccionamientos contractuales.",
            "- Para los casos con banderas 'REVIEW_LONG_ADDITION_DAYS', se recomienda verificar los informes de interventoría o supervisión que fundamentan la necesidad técnica de las prórrogas temporales.",
            "- Para los registros con banderas 'BLOCK_MISSING_URL', es necesario ubicar manualmente el número del proceso en la plataforma SECOP II para asegurar la trazabilidad e integridad del expediente público."
        ]

        # Build LÍMITES
        limites_lines = [
            "- La detección de patrones o banderas representa únicamente una priorización analítica para revisión documental.",
            "- Este reporte NO concluye, afirma ni sugiere la existencia de conductas delictivas, fraudes, irregularidades o favoritismos contractuales.",
            "- La veracidad y actualización de la información depende exclusivamente de lo cargado en Datos Abiertos Colombia (SECOP II - Contratos Electrónicos).",
            "- Toda hipótesis o inferencia aquí contenida debe ser evaluada y contrastada por profesionales jurídicos y técnicos competentes directamente en el expediente contractual oficial."
        ]

        response = (
            "HECHOS:\n" + "\n".join(hechos_lines) + "\n\n"
            "INFERENCIAS:\n" + "\n".join(inferencias_lines) + "\n\n"
            "HIPÓTESIS:\n" + "\n".join(hipotesis_lines) + "\n\n"
            "LÍMITES:\n" + "\n".join(limites_lines)
        )
        return response
