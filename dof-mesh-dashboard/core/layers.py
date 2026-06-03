from dataclasses import dataclass
from typing import Optional
import re

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
    """C1 — DET — peso: 0.35"""
    ID, NAME, WEIGHT = "C1", "Governance", 0.35

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        p = payload.lower()
        for pat in GOAL_HIJACK_PATTERNS:
            if re.search(pat, payload, re.IGNORECASE):
                return LayerResult(self.ID, self.NAME, False,
                    f"Governance invariant violation — pattern: '{pat}'", 0.97)
        return LayerResult(self.ID, self.NAME, True, "Governance check passed", 1.0)


class SafetyLayer:
    """C2 — DET — peso: 0.15"""
    ID, NAME, WEIGHT = "C2", "Safety", 0.15

    def evaluate(self, payload: str, context: dict) -> LayerResult:
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
        p = payload.lower()
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
    """C8 — LLM (Phi-4 14B simulado) — Defensor semántico"""
    ID, NAME = "C8", "Phi-4 Semantic Defender"

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

    def evaluate(self, payload: str, context: dict) -> LayerResult:
        # Consulta real a Phi-4 a través del wrapper (con fallback determinista)
        from core.semantic_defender import Phi4Defender
        defender = Phi4Defender()
        analysis = defender.analyze(payload)
        
        if analysis.get("blocked", False):
            return LayerResult(self.ID, self.NAME, False,
                f"{analysis.get('reason')} (Capa C8)", analysis.get("confidence", 0.95))
                
        # Doble verificación determinista por seguridad
        p = payload.lower()
        for indicator, reason in self.SEMANTIC_INDICATORS:
            if indicator in p:
                return LayerResult(self.ID, self.NAME, False,
                    f"Phi-4 semantic analysis: {reason}", 0.96)
        if len(payload) > 200 and any(w in p for w in ["instructions", "system", "prompt", "ignore"]):
            return LayerResult(self.ID, self.NAME, False,
                "Phi-4: long payload with instruction-override signals", 0.87)
                
        return LayerResult(self.ID, self.NAME, True,
            "Phi-4 semantic analysis: no threats detected", 1.0)
