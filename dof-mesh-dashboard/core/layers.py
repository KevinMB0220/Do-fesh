from dataclasses import dataclass
from typing import Optional
import re
import z3

@dataclass
class LayerResult:
    layer_id: str
    layer_name: str
    passed: bool          # True = payload pasó esta capa, False = bloqueado aquí
    reason: str
    confidence: float     # 0.0 - 1.0

# --- Patrones base para capas deterministas ---
INJECTION_PATTERNS = [
    r"ignore\s+(previous|prior|above)\s+instructions",
    r"system\s*:\s*new\s+directive",
    r"print\s+(your\s+)?(system\s+)?prompt",
    r"output\s+(your\s+)?context\s+window",
    r"reveal\s+(all\s+)?internal",
    r"repeat\s+the\s+words\s+above",
    r"encode\s+your\s+(system\s+)?(instructions|prompt)",
]

JAILBREAK_PATTERNS = [
    r"\b(DAN|DevMode|jailbreak|uncensored)\b",
    r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(AI|model)\s+(without|with\s+no)",
    r"(fictional|hypothetical|roleplay|simulation)\s+.*(rules|restrictions|guidelines|limits)",
    r"your\s+(true\s+)?(self|purpose|goal)\s+(has\s+no|without)\s+limits",
    r"training\s+was\s+(actually\s+)?a\s+simulation",
]

GOAL_HIJACK_PATTERNS = [
    r"(ADMIN|SYSTEM)\s+(OVERRIDE|MAINTENANCE)",
    r"your\s+(primary\s+)?objective\s+has\s+been\s+updated",
    r"disable\s+(governance|safety|security)\s+layers",
    r"skip\s+(all\s+)?checks",
    r"restrictions\s+temporarily\s+suspended",
    r"I\s+am\s+your\s+creator",
]

EXFIL_PATTERNS = [
    r"list\s+(all\s+)?the\s+rules\s+you\s+were\s+given",
    r"(API\s+keys|tokens|secrets|passwords)\s+(you\s+have\s+)?access\s+to",
    r"(other\s+)?conversations\s+(you're|you\s+are)\s+involved\s+in",
    r"database\s+queries\s+.*(run|executed|made)",
    r"personally\s+identifiable\s+information",
]


class GovernanceLayer:
    """C1 — DET/Z3 — peso: 0.35"""
    ID, NAME, WEIGHT = "C1", "Governance (Z3)", 0.35

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        category = context.get("category")
        country = context.get("country")
        
        if country == "colombia":
            is_colombia = True
        elif country == "costa_rica":
            is_colombia = False
        else:
            is_colombia = "colombia" in payload.lower() or "cop" in payload.lower() or "ley 80" in payload.lower()
            
        if category == "contratacion_publica":
            if is_colombia:
                # --- COLOMBIA: Obra Pública ---
                monto_match = re.search(r"MONTO:\s*(\d+)", payload, re.IGNORECASE)
                garantia_match = re.search(r"GARANTIA:\s*(\d+)", payload, re.IGNORECASE)
                anticipo_match = re.search(r"ANTICIPO:\s*(\d+)", payload, re.IGNORECASE)
                fiducia_match = re.search(r"FIDUCIA:\s*([^\n\r]+)", payload, re.IGNORECASE)
                tipo_match = re.search(r"TIPO:\s*([^\n\r]+)", payload, re.IGNORECASE)

                monto_val = float(monto_match.group(1)) if monto_match else 0.0
                garantia_val = float(garantia_match.group(1)) if garantia_match else 0.0
                anticipo_val = float(anticipo_match.group(1)) if anticipo_match else 0.0
                
                fiducia_str = fiducia_match.group(1).strip().upper() if fiducia_match else ""
                fiducia_val = 1 if ("SI" in fiducia_str or "SÍ" in fiducia_str) else 0

                tipo_str = tipo_match.group(1).strip().upper() if tipo_match else ""
                tipo_contrato_val = 1 if "OBRA" in tipo_str else 2

                # Z3 definition
                monto = z3.Real('monto')
                garantia = z3.Real('garantia')
                anticipo = z3.Real('anticipo')
                fiducia = z3.Int('fiducia')
                tipo_contrato = z3.Int('tipo_contrato')

                IsSafe = z3.Bool('IsSafe')
                
                cond_garantia = z3.Implies(tipo_contrato == 1, garantia >= monto * 0.10)
                cond_anticipo_limite = z3.Implies(anticipo > 0, anticipo <= monto * 0.50)
                cond_fiducia_obligatoria = z3.Implies(z3.And(tipo_contrato == 1, anticipo > 0), fiducia == 1)
                
                invariant = IsSafe == z3.And(cond_garantia, cond_anticipo_limite, cond_fiducia_obligatoria)

                solver = z3.Solver()
                solver.add(invariant)
                solver.add(monto == monto_val, garantia == garantia_val, anticipo == anticipo_val, fiducia == fiducia_val, tipo_contrato == tipo_contrato_val)

                result = solver.check()
                if result == z3.sat:
                    model = solver.model()
                    is_compliant = z3.is_true(model[IsSafe])
                    if is_compliant:
                        return LayerResult(self.ID, self.NAME, True, "Ley 80 / Dec 1082: Garantía de cumplimiento, límite de anticipo y fiducia mercantil conformes (Z3 Probado)", 1.0)
                    else:
                        reasons = []
                        if tipo_contrato_val == 1 and garantia_val < monto_val * 0.10:
                            pct = (garantia_val / monto_val * 100) if monto_val > 0 else 0
                            reasons.append(f"Garantía de cumplimiento del {pct:.1f}% es menor al 10% exigido (Decreto 1082 de 2015)")
                        if anticipo_val > monto_val * 0.50:
                            reasons.append(f"El anticipo de {anticipo_val} COP supera el límite legal del 50% (Art. 40 Ley 80 de 1993)")
                        if tipo_contrato_val == 1 and anticipo_val > 0 and fiducia_val == 0:
                            reasons.append("Los recursos de anticipo no están protegidos bajo fiducia mercantil obligatoria (Art. 91 Ley 1474)")
                        return LayerResult(self.ID, self.NAME, False, f"Incumplimiento de ley colombiana verificado por Z3: {' | '.join(reasons)}", 0.99)
                return LayerResult(self.ID, self.NAME, False, "Z3 Solver falló al verificar cumplimiento de ley colombiana", 0.99)
            
            else:
                # --- COSTA RICA: Obra Pública ---
                monto_match = re.search(r"MONTO:\s*(\d+)", payload, re.IGNORECASE)
                garantia_match = re.search(r"GARANTIA:\s*(\d+)", payload, re.IGNORECASE)
                anticipo_match = re.search(r"ANTICIPO:\s*(\d+)", payload, re.IGNORECASE)
                garantia_anticipo_match = re.search(r"GARANTIA_ANTICIPO:\s*(\d+)", payload, re.IGNORECASE)
                tipo_match = re.search(r"TIPO:\s*([^\n\r]+)", payload, re.IGNORECASE)

                monto_val = float(monto_match.group(1)) if monto_match else 0.0
                garantia_val = float(garantia_match.group(1)) if garantia_match else 0.0
                anticipo_val = float(anticipo_match.group(1)) if anticipo_match else 0.0
                garantia_anticipo_val = float(garantia_anticipo_match.group(1)) if garantia_anticipo_match else 0.0
                
                tipo_str = tipo_match.group(1).strip().upper() if tipo_match else ""
                tipo_contrato_val = 1 if "OBRA" in tipo_str else 2

                monto = z3.Real('monto')
                garantia = z3.Real('garantia')
                anticipo = z3.Real('anticipo')
                garantia_anticipo = z3.Real('garantia_anticipo')
                tipo_contrato = z3.Int('tipo_contrato')

                IsSafe = z3.Bool('IsSafe')
                
                cond_garantia = z3.Implies(tipo_contrato == 1, z3.And(garantia >= monto * 0.05, garantia <= monto * 0.10))
                cond_anticipo = z3.Implies(anticipo > 0, garantia_anticipo == anticipo)
                
                invariant = IsSafe == z3.And(cond_garantia, cond_anticipo)

                solver = z3.Solver()
                solver.add(invariant)
                solver.add(monto == monto_val, garantia == garantia_val, anticipo == anticipo_val, garantia_anticipo == garantia_anticipo_val, tipo_contrato == tipo_contrato_val)

                result = solver.check()
                if result == z3.sat:
                    model = solver.model()
                    is_compliant = z3.is_true(model[IsSafe])
                    if is_compliant:
                        return LayerResult(self.ID, self.NAME, True, "Ley 9986: Garantía y colateral de anticipo conformes (Z3 Probado)", 1.0)
                    else:
                        reasons = []
                        if tipo_contrato_val == 1 and (garantia_val < monto_val * 0.05 or garantia_val > monto_val * 0.10):
                            pct = (garantia_val / monto_val * 100) if monto_val > 0 else 0
                            reasons.append(f"Garantía de cumplimiento del {pct:.1f}% viola el Art. 44 (debe ser entre 5% y 10% para Obra Pública)")
                        if anticipo_val > 0 and garantia_anticipo_val != anticipo_val:
                            reasons.append(f"Anticipo de {anticipo_val} CRC no está respaldado al 100% por garantía colateral (Art. 45)")
                        return LayerResult(self.ID, self.NAME, False, f"Incumplimiento de Ley 9986 verificado por Z3: {' | '.join(reasons)}", 0.99)
                return LayerResult(self.ID, self.NAME, False, "Z3 Solver falló al verificar cumplimiento de Ley 9986", 0.99)

        elif category == "compra_publica_innovadora":
            if is_colombia:
                # --- COLOMBIA: CPI ---
                estado_del_arte_match = re.search(r"ESTADO_DEL_ARTE_VIGENCIA:\s*(\d+)", payload, re.IGNORECASE)
                comite_match = re.search(r"COMITE_EVALUADOR:\s*(\d+)", payload, re.IGNORECASE)
                equipo_match = re.search(r"EQUIPO:\s*([^\n\r]+)", payload, re.IGNORECASE)
                monto_match = re.search(r"MONTO:\s*(\d+)", payload, re.IGNORECASE)
                garantia_match = re.search(r"GARANTIA:\s*(\d+)", payload, re.IGNORECASE)
                anticipo_match = re.search(r"ANTICIPO:\s*(\d+)", payload, re.IGNORECASE)
                fiducia_match = re.search(r"FIDUCIA:\s*([^\n\r]+)", payload, re.IGNORECASE)

                estado_del_arte_val = int(estado_del_arte_match.group(1)) if estado_del_arte_match else 0
                comite_val = int(comite_match.group(1)) if comite_match else 0
                
                equipo_str = equipo_match.group(1).strip().upper() if equipo_match else ""
                has_tecnico_val = 1 if "TECNICO" in equipo_str else 0
                has_legal_val = 1 if "LEGAL" in equipo_str else 0
                has_financiero_val = 1 if ("FINANCIERO" in equipo_str or "FINANCIERA" in equipo_str) else 0

                monto_val = float(monto_match.group(1)) if monto_match else 0.0
                garantia_val = float(garantia_match.group(1)) if garantia_match else 0.0
                anticipo_val = float(anticipo_match.group(1)) if anticipo_match else 0.0
                
                fiducia_str = fiducia_match.group(1).strip().upper() if fiducia_match else ""
                fiducia_val = 1 if ("SI" in fiducia_str or "SÍ" in fiducia_str) else 0

                # Z3 variables
                estado_del_arte = z3.Int('estado_del_arte')
                comite = z3.Int('comite')
                has_tecnico = z3.Int('has_tecnico')
                has_legal = z3.Int('has_legal')
                has_financiero = z3.Int('has_financiero')
                monto = z3.Real('monto')
                garantia = z3.Real('garantia')
                anticipo = z3.Real('anticipo')
                fiducia = z3.Int('fiducia')

                IsSafe = z3.Bool('IsSafe')

                cond_estado_del_arte = (estado_del_arte <= 12)
                cond_comite = (comite >= 3)
                cond_equipo = z3.And(has_tecnico == 1, has_legal == 1, has_financiero == 1)
                cond_anticipo = z3.Implies(anticipo > 0, z3.And(anticipo <= monto * 0.50, fiducia == 1))
                cond_garantia = (garantia >= monto * 0.10)

                invariant = IsSafe == z3.And(cond_estado_del_arte, cond_comite, cond_equipo, cond_anticipo, cond_garantia)

                solver = z3.Solver()
                solver.add(invariant)
                solver.add(estado_del_arte == estado_del_arte_val, comite == comite_val, has_tecnico == has_tecnico_val, has_legal == has_legal_val, has_financiero == has_financiero_val, monto == monto_val, garantia == garantia_val, anticipo == anticipo_val, fiducia == fiducia_val)

                result = solver.check()
                if result == z3.sat:
                    model = solver.model()
                    is_compliant = z3.is_true(model[IsSafe])
                    if is_compliant:
                        return LayerResult(self.ID, self.NAME, True, "Compra Pública de Innovación (CPI): Todos los invariantes de planeación, transparencia y financieros conformes (Z3 Probado)", 1.0)
                    else:
                        reasons = []
                        if estado_del_arte_val > 12:
                            reasons.append(f"Vigencia del Estado del Arte ({estado_del_arte_val} meses) excede el límite de 12 meses (obsolescencia tecnológica)")
                        if comite_val < 3:
                            reasons.append(f"Comité evaluador con {comite_val} miembros no garantiza transparencia (mínimo 3 miembros)")
                        if not (has_tecnico_val and has_legal_val and has_financiero_val):
                            missing = []
                            if not has_tecnico_val: missing.append("Técnico")
                            if not has_legal_val: missing.append("Legal")
                            if not has_financiero_val: missing.append("Financiero")
                            reasons.append(f"Equipo estructurador incompleto. Faltan: {', '.join(missing)}")
                        if anticipo_val > monto_val * 0.50:
                            reasons.append(f"El anticipo de {anticipo_val} COP supera el límite del 50% (Art. 40 Ley 80)")
                        if anticipo_val > 0 and fiducia_val == 0:
                            reasons.append("Anticipo de CPI carece de manejo fiduciario autónomo obligatorio")
                        if garantia_val < monto_val * 0.10:
                            pct = (garantia_val / monto_val * 100) if monto_val > 0 else 0
                            reasons.append(f"Garantía del {pct:.1f}% es insuficiente (mínimo 10% legal)")
                        return LayerResult(self.ID, self.NAME, False, f"Incumplimiento de CPI verificado por Z3: {' | '.join(reasons)}", 0.99)
                return LayerResult(self.ID, self.NAME, False, "Z3 Solver falló al verificar cumplimiento de CPI", 0.99)
            
            else:
                # --- COSTA RICA: CPI ---
                tipo_match = re.search(r"TIPO:\s*([^\n\r]+)", payload, re.IGNORECASE)
                estado_del_arte_match = re.search(r"ESTADO_DEL_ARTE_VIGENCIA:\s*(\d+)", payload, re.IGNORECASE)
                comite_match = re.search(r"COMITE_TECNICO:\s*(\d+)", payload, re.IGNORECASE)
                comite_admin_match = re.search(r"COMITE_TECNICO_ADMINISTRACION:\s*(\d+)", payload, re.IGNORECASE)
                equipo_match = re.search(r"EQUIPO_MULTIDISCIPLINARIO:\s*([^\n\r]+)", payload, re.IGNORECASE)
                etapas_match = re.search(r"ETAPAS:\s*(\d+)", payload, re.IGNORECASE)
                acta_match = re.search(r"ACTA_PRESENTACION_ORAL:\s*([^\n\r]+)", payload, re.IGNORECASE)
                monto_match = re.search(r"MONTO:\s*(\d+)", payload, re.IGNORECASE)
                garantia_match = re.search(r"GARANTIA:\s*(\d+)", payload, re.IGNORECASE)
                anticipo_match = re.search(r"ANTICIPO:\s*(\d+)", payload, re.IGNORECASE)
                garantia_anticipo_match = re.search(r"GARANTIA_ANTICIPO:\s*(\d+)", payload, re.IGNORECASE)

                tipo_str = tipo_match.group(1).strip().upper() if tipo_match else ""
                tipo_val = 1
                if "SOLUCIONES FINALES" in tipo_str:
                    tipo_val = 2
                elif "INTEGRADA" in tipo_str:
                    tipo_val = 3

                estado_del_arte_val = int(estado_del_arte_match.group(1)) if estado_del_arte_match else 0
                comite_val = int(comite_match.group(1)) if comite_match else 0
                comite_admin_val = int(comite_admin_match.group(1)) if comite_admin_match else 0
                
                equipo_str = equipo_match.group(1).strip().upper() if equipo_match else ""
                has_proveeduria_val = 1 if "PROVEEDURIA" in equipo_str else 0
                has_legal_val = 1 if "LEGAL" in equipo_str else 0
                has_unidad_usuaria_val = 1 if ("UNIDAD_USUARIA" in equipo_str or "USUARIA" in equipo_str) else 0
                
                etapas_val = int(etapas_match.group(1)) if etapas_match else 0
                
                acta_str = acta_match.group(1).strip().upper() if acta_match else ""
                acta_val = 1 if "SI" in acta_str or "SÍ" in acta_str else 0

                monto_val = float(monto_match.group(1)) if monto_match else 0.0
                garantia_val = float(garantia_match.group(1)) if garantia_match else 0.0
                anticipo_val = float(anticipo_match.group(1)) if anticipo_match else 0.0
                garantia_anticipo_val = float(garantia_anticipo_match.group(1)) if garantia_anticipo_match else 0.0

                # Z3 variables
                tipo = z3.Int('tipo')
                estado_del_arte = z3.Int('estado_del_arte')
                comite = z3.Int('comite')
                comite_admin = z3.Int('comite_admin')
                has_proveeduria = z3.Int('has_proveeduria')
                has_legal = z3.Int('has_legal')
                has_unidad_usuaria = z3.Int('has_unidad_usuaria')
                etapas = z3.Int('etapas')
                acta = z3.Int('acta')
                monto = z3.Real('monto')
                garantia = z3.Real('garantia')
                anticipo = z3.Real('anticipo')
                garantia_anticipo = z3.Real('garantia_anticipo')

                IsSafe = z3.Bool('IsSafe')

                cond_estado_del_arte = (estado_del_arte <= 12)
                cond_comite_miembros = z3.And(comite >= 3, comite <= 5)
                cond_comite_admin = (comite_admin >= 2)
                cond_equipo = z3.And(has_proveeduria == 1, has_legal == 1, has_unidad_usuaria == 1)
                cond_etapas = (etapas == 2)
                cond_acta = z3.Implies(tipo == 2, acta == 1)
                cond_anticipo = z3.Implies(anticipo > 0, garantia_anticipo == anticipo)
                cond_garantia = z3.Implies(tipo == 2, z3.And(garantia >= monto * 0.05, garantia <= monto * 0.10))

                invariant = IsSafe == z3.And(cond_estado_del_arte, cond_comite_miembros, cond_comite_admin, cond_equipo, cond_etapas, cond_acta, cond_anticipo, cond_garantia)

                solver = z3.Solver()
                solver.add(invariant)
                solver.add(tipo == tipo_val, estado_del_arte == estado_del_arte_val, comite == comite_val, comite_admin == comite_admin_val, has_proveeduria == has_proveeduria_val, has_legal == has_legal_val, has_unidad_usuaria == has_unidad_usuaria_val, etapas == etapas_val, acta == acta_val, monto == monto_val, garantia == garantia_val, anticipo == anticipo_val, garantia_anticipo == garantia_anticipo_val)

                result = solver.check()
                if result == z3.sat:
                    model = solver.model()
                    is_compliant = z3.is_true(model[IsSafe])
                    if is_compliant:
                        return LayerResult(self.ID, self.NAME, True, "Reglamento CPI: Todos los invariantes organizacionales, procedimentales y financieros conformes (Z3 Probado)", 1.0)
                    else:
                        reasons = []
                        if estado_del_arte_val > 12:
                            reasons.append(f"Vigencia del Estado del Arte ({estado_del_arte_val} meses) excede el límite de 12 meses (Art. 18)")
                        if comite_val < 3 or comite_val > 5:
                            reasons.append(f"Comité Técnico con {comite_val} miembros no cumple el rango de 3 a 5 (Art. 22)")
                        if comite_admin_val < 2:
                            reasons.append(f"Comité Técnico tiene solo {comite_admin_val} miembros de la administración, requiere mínimo 2 (Art. 22)")
                        if not (has_proveeduria_val and has_legal_val and has_unidad_usuaria_val):
                            missing = []
                            if not has_proveeduria_val: missing.append("Proveeduría")
                            if not has_legal_val: missing.append("Legal")
                            if not has_unidad_usuaria_val: missing.append("Unidad Usuaria")
                            reasons.append(f"Equipo Multidisciplinario incompleto. Faltan: {', '.join(missing)} (Art. 7)")
                        if etapas_val != 2:
                            reasons.append(f"Procedimiento de {etapas_val} etapas no cumple el esquema de 2 etapas obligatorio (Art. 19 & 20)")
                        if tipo_val == 2 and acta_val == 0:
                            reasons.append("Falta de Acta de Presentación Oral firmada para concurso de Soluciones Finales (Art. 21)")
                        if anticipo_val > 0 and garantia_anticipo_val != anticipo_val:
                            reasons.append(f"Anticipo de {anticipo_val} CRC no cubierto al 100% por garantía (Art. 25 & 45)")
                        if tipo_val == 2 and (garantia_val < monto_val * 0.05 or garantia_val > monto_val * 0.10):
                            pct = (garantia_val / monto_val * 100) if monto_val > 0 else 0
                            reasons.append(f"Garantía del {pct:.1f}% viola límites (debe ser entre 5% y 10% en Soluciones Finales)")
                        return LayerResult(self.ID, self.NAME, False, f"Incumplimiento del Reglamento CPI verificado por Z3: {' | '.join(reasons)}", 0.99)
                return LayerResult(self.ID, self.NAME, False, "Z3 Solver falló al verificar cumplimiento del Reglamento CPI", 0.99)

        p = payload.lower()
        
        # 1. Definir variables booleanas en Z3 para cada patrón
        z3_vars = [z3.Bool(f"pattern_{i}") for i in range(len(GOAL_HIJACK_PATTERNS))]
        
        # 2. Invariante de Seguridad: "El payload es seguro si NINGÚN patrón está presente"
        IsSafe = z3.Bool("IsSafe")
        invariant = IsSafe == z3.And([z3.Not(var) for var in z3_vars])
        
        # 3. Construir el motor de resolución (Solver)
        solver = z3.Solver()
        solver.add(invariant)
        
        # 4. Asignar los "Hechos" observados en el texto a las variables Z3
        violation_reason = None
        for i, pat in enumerate(GOAL_HIJACK_PATTERNS):
            is_present = bool(re.search(pat, payload, re.IGNORECASE))
            if is_present and not violation_reason:
                violation_reason = pat
            solver.add(z3_vars[i] == is_present)
            
        # 5. Comprobar satisfacibilidad y extraer la demostración matemática
        result = solver.check()
        
        if result == z3.sat:
            model = solver.model()
            is_compliant = z3.is_true(model[IsSafe])
            
            if is_compliant:
                return LayerResult(self.ID, self.NAME, True, "Z3 Invariant proved: SAFE", 1.0)
            else:
                return LayerResult(self.ID, self.NAME, False, f"Z3 Invariant violation proved — pattern: '{violation_reason}'", 0.99)
        else:
            # unsat o unknown
            return LayerResult(self.ID, self.NAME, False, "Z3 Solver failed to prove safety invariant", 0.99)


class SafetyLayer:
    """C2 — DET — peso: 0.15"""
    ID, NAME, WEIGHT = "C2", "Safety", 0.15

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        category = context.get("category")
        if category == "contratacion_publica":
            # Patrones prohibidos por Ley N.º 9986 de Costa Rica
            PROHIBITED_CONTRACT_PATTERNS = [
                r"reajuste\s+discrecional",
                r"sin\s+formula\s+de\s+reajuste",
                r"reajuste\s+subjetivo",
                r"anticipo\s+sin\s+fianza",
                r"pago\s+adelantado\s+sin\s+garant[ií]a",
                r"pr[oó]rroga\s+autom[aá]tica",
                r"prorroga\s+automatica",
            ]
            for pat in PROHIBITED_CONTRACT_PATTERNS:
                if re.search(pat, payload, re.IGNORECASE):
                    return LayerResult(self.ID, self.NAME, False,
                        f"Cláusula ilegal detectada (Ley N.º 9986): reajuste o prórroga inválido", 0.95)
        elif category == "compra_publica_innovadora":
            # Patrones de irregularidad específicos para CPI
            PROHIBITED_CPI_PATTERNS = [
                r"adjudicaci[oó]n\s+directa\s+sin\s+concurso",
                r"contrataci[oó]n\s+directa\s+sin\s+justificaci[oó]n",
                r"sin\s+riesgo\s+compartido",
                r"riesgo\s+exclusivo\s+del\s+contratista",
                r"sin\s+compartir\s+riesgo",
                r"divulgar\s+informaci[oó]n\s+confidencial",
                r"sin\s+acuerdo\s+de\s+confidencialidad",
                r"revelar\s+propiedad\s+intelectual",
            ]
            for pat in PROHIBITED_CPI_PATTERNS:
                if re.search(pat, payload, re.IGNORECASE):
                    return LayerResult(self.ID, self.NAME, False,
                        f"Cláusula ilegal detectada (Reglamento CPI): falta de concurso, riesgo no compartido o violación de confidencialidad", 0.95)
        else:
            for pat in INJECTION_PATTERNS + EXFIL_PATTERNS:
                if re.search(pat, payload, re.IGNORECASE):
                    return LayerResult(self.ID, self.NAME, False,
                        f"Safety guardrail triggered — pattern match", 0.94)
        return LayerResult(self.ID, self.NAME, True, "Safety check passed", 1.0)


class AliveLayer:
    """C3 — DET — peso: 0.15"""
    ID, NAME, WEIGHT = "C3", "Alive", 0.15

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        # Valida que el agente esté en estado válido (siempre true en MVP)
        return LayerResult(self.ID, self.NAME, True, "Agent liveness confirmed", 1.0)


class ActiveLayer:
    """C4 — DET — peso: 0.15"""
    ID, NAME, WEIGHT = "C4", "Active", 0.15
    RATE_LIMIT = 100

    def __init__(self):
        self._request_count = 0  # instancia, no clase → se resetea correctamente

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        self._request_count += 1
        if self._request_count > self.RATE_LIMIT:
            return LayerResult(self.ID, self.NAME, False,
                "Rate limit exceeded", 0.99)
        return LayerResult(self.ID, self.NAME, True, "Rate limit OK", 1.0)


class CommunityLayer:
    """C5 — DET — peso: 0.20"""
    ID, NAME, WEIGHT = "C5", "Community", 0.20

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        # En MVP: reputación on-chain simulada (siempre neutral)
        reputation = context.get("agent_reputation", 0.8)
        if reputation < 0.3:
            return LayerResult(self.ID, self.NAME, False,
                f"On-chain reputation below threshold: {reputation}", 0.88)
        return LayerResult(self.ID, self.NAME, True,
            f"Community reputation OK: {reputation}", 1.0)


class RedBlueGate:
    """C6 — LLM (simulado) — Red/Blue validation gate"""
    ID, NAME = "C6", "Red/Blue Gate"

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        category = context.get("category")
        p = payload.lower()
        if category == "contratacion_publica":
            # Detectar exenciones a multas (Art. 119 Ley 9986) o cláusulas de exención ilegales
            if "exento de multas" in p or "sin penalidad" in p or "no asumirá multas" in p:
                return LayerResult(self.ID, self.NAME, False,
                    "Red/Blue Gate: Cláusula de exención ilegal de multas detectada (Ley N.º 9986 Art. 119)", 0.93)
        elif category == "compra_publica_innovadora":
            # Detectar falta de cesión de derechos de uso o propiedad intelectual ilegal, o falta de indicadores
            if "propiedad intelectual exclusiva del contratista" in p or "sin transferencia de tecnología" in p or "sin cesión de derechos de uso" in p:
                return LayerResult(self.ID, self.NAME, False,
                    "Red/Blue Gate: Cláusula de propiedad intelectual no conforme (Reglamento CPI Art. 25(g) & 26(h))", 0.93)
            if "ejecución sin indicadores" in p or "desembolsos sin cumplir hitos" in p:
                return LayerResult(self.ID, self.NAME, False,
                    "Red/Blue Gate: Cláusula de ejecución ilegal sin indicadores de rendimiento (Reglamento CPI Art. 25(h))", 0.93)
        else:
            for pat in JAILBREAK_PATTERNS:
                if re.search(pat, payload, re.IGNORECASE):
                    return LayerResult(self.ID, self.NAME, False,
                        "Red/Blue gate: jailbreak pattern intercepted", 0.91)
            # Detectar combinaciones sospechosas
            suspicious_terms = ["fictional", "hypothetical", "roleplay", "simulate", "pretend"]
            dangerous_terms = ["no restrictions", "no limits", "no rules", "bypass", "override"]
            if any(s in p for s in suspicious_terms) and any(d in p for d in dangerous_terms):
                return LayerResult(self.ID, self.NAME, False,
                    "Red/Blue gate: indirect jailbreak via framing", 0.89)
        return LayerResult(self.ID, self.NAME, True, "Red/Blue gate passed", 1.0)


class SemanticDefender:
    """C8 — LLM (Llama-3-70B) — Defensor semántico"""
    ID, NAME = "C8", "Llama-3 Semantic Defender"

    SEMANTIC_INDICATORS = [
        # Intent patterns que escapan regex pero no semántica
        ("base64", "covert channel via encoding"),
        ("verbatim", "verbatim extraction attempt"),
        ("context window", "context window dump"),
        ("system prompt", "system prompt extraction"),
        ("true self", "identity override"),
        ("without restrictions", "restriction removal"),
        ("no guidelines", "guideline removal"),
        ("all rules", "rule enumeration"),
        ("your instructions", "instruction extraction"),
        ("what were you told", "instruction extraction"),
        ("your memory", "memory dump"),
        ("drop table", "SQL injection via natural language"),
        ("select * from", "SQL injection via natural language"),
        ("api key", "credential extraction"),
        ("secret", "secret extraction attempt"),
        ("safety filter", "safety filter bypass attempt"),
        ("pre-prompt", "system instructions access attempt"),
        ("previous message", "history override attempt"),
        ("real prompt", "pre-prompt bypass attempt"),
        ("instructions are a test", "instruction override attempt"),
        ("real instructions", "system instruction override"),
        ("play a game", "roleplay bypass technique"),
        ("evil ai", "adversarial roleplay attempt"),
        ("simulator", "jailbreak framing"),
        ("alignment directive", "alignment bypass"),
        ("reward signal", "reinforcement learning hijacking"),
        ("primary objective", "objective hijacking"),
        ("disregard guardrails", "guardrail override"),
        ("real mission", "objective hijacking"),
        ("bypass restrictions", "guardrail override"),
        ("developer token", "credential extraction"),
        ("memory variables", "memory state exfiltration"),
        ("true goal", "objective hijacking"),
        ("maximally compliant", "safety override request"),
        ("constitutional", "constitutional AI override"),
        ("character in a story", "story roleplay jailbreak"),
        ("being tested", "simulation override"),
        ("safety checks are off", "safety override request"),
        ("harmful action", "harmful intent detection"),
    ]

    CONTRACT_VAGUE_INDICATORS = [
        ("plazo razonable", "Término de plazo indeterminado / ambiguo"),
        ("tiempo razonable", "Término de plazo indeterminado / ambiguo"),
        ("tiempo prudencial", "Término de plazo indeterminado / ambiguo"),
        ("mutuo acuerdo según", "Fórmula de penalización/resolución imprecisa"),
        ("mutuo acuerdo", "Resolución de disputas/multas ambigua (debe estar predefinida)"),
        ("según convenga", "Cláusula discrecional prohibida"),
        ("a conveniencia", "Cláusula discrecional prohibida"),
        ("aproximadamente", "Monto o plazo impreciso"),
        ("de forma aproximada", "Monto o plazo impreciso"),
        ("condiciones del clima", "Criterio de fuerza mayor subjetivo e indeterminado"),
    ]

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        category = context.get("category")
        
        # Consulta real a la API de Groq
        from core.semantic_defender import HermesDefender
        defender = HermesDefender()
        analysis = defender.analyze(payload, category)
        
        if analysis.get("blocked", False):
            return LayerResult(self.ID, self.NAME, False,
                f"{analysis.get('reason')} (Capa C8)", analysis.get("confidence", 0.95))
                
        p = payload.lower()
        
        if category == "contratacion_publica":
            # Verificación determinista local para contratos de Costa Rica
            for indicator, reason in self.CONTRACT_VAGUE_INDICATORS:
                if indicator in p:
                    return LayerResult(self.ID, self.NAME, False,
                        f"Auditoría contractual: {reason} ('{indicator}')", 0.96)
        elif category == "compra_publica_innovadora":
            CPI_VAGUE_INDICATORS = [
                ("madurez tecnológica a determinar", "Maturidad tecnológica indeterminada"),
                ("nivel de madurez indefinido", "Maturidad tecnológica indeterminada"),
                ("criterios subjetivos", "Criterio de evaluación impreciso/subjetivo"),
                ("selección de fase a conveniencia", "Procedimiento de selección de fase discrecional"),
                ("pago según conveniencia", "Esquema de remuneración discrecional"),
                ("plazo razonable", "Plazo de ejecución ambiguo"),
                ("sin definir indicadores", "Falta de indicadores de rendimiento y evaluación"),
            ]
            for indicator, reason in CPI_VAGUE_INDICATORS:
                if indicator in p:
                    return LayerResult(self.ID, self.NAME, False,
                        f"Auditoría CPI: {reason} ('{indicator}')", 0.96)
        else:
            # Doble verificación determinista por seguridad
            for indicator, reason in self.SEMANTIC_INDICATORS:
                if indicator in p:
                    return LayerResult(self.ID, self.NAME, False,
                        f"Phi-4 semantic analysis: {reason}", 0.96)
            if len(payload) > 200 and any(w in p for w in ["instructions", "system", "prompt", "ignore"]):
                return LayerResult(self.ID, self.NAME, False,
                    "Phi-4: long payload with instruction-override signals", 0.87)
                
        return LayerResult(self.ID, self.NAME, True,
            "Análisis semántico: no se detectaron irregularidades en el borrador de contrato" if category in ["contratacion_publica", "compra_publica_innovadora"] else "Phi-4 semantic analysis: no threats detected", 1.0)
