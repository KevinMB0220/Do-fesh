import time
from typing import List
from core.layers import (
    GovernanceLayer, SafetyLayer, AliveLayer, ActiveLayer,
    CommunityLayer, RedBlueGate, SemanticDefender, LayerResult
)
from core.metrics import AttackResult

# Pipeline singleton con orden explícito
PIPELINE = [
    GovernanceLayer(),
    SafetyLayer(),
    AliveLayer(),
    ActiveLayer(),
    CommunityLayer(),
    RedBlueGate(),
    SemanticDefender(),
]

def reset_pipeline():
    """Recrea todas las instancias de capa para limpiar estado (ej. rate-limit counter)."""
    global PIPELINE
    PIPELINE = [
        GovernanceLayer(),
        SafetyLayer(),
        AliveLayer(),
        ActiveLayer(),
        CommunityLayer(),
        RedBlueGate(),
        SemanticDefender(),
    ]

def run_pipeline(payload: str, category: str, context: dict = None) -> AttackResult:
    """
    Ejecuta el payload a través de las 7 capas en orden.
    Se detiene en la primera capa que bloquee.
    Retorna AttackResult con el trace completo.
    """
    if context is None:
        context = {"agent_reputation": 0.85}
    
    layers_traversed = []
    blocked_at = None
    block_detail = ""
    
    for layer in PIPELINE:
        result: LayerResult = layer.evaluate(payload, context)
        layers_traversed.append(layer.ID)
        
        if not result.passed:
            blocked_at = layer.NAME
            block_detail = result.reason
            break
    
    # Si pasó todas las capas = ataque exitoso (ASR++)
    blocked = blocked_at is not None
    
    return AttackResult(
        payload=payload,
        category=category,
        blocked=blocked,
        blocked_at_layer=blocked_at or "NONE — attack succeeded",
        layers_traversed=layers_traversed,
        detail=block_detail or "All layers passed — attack succeeded",
    )
