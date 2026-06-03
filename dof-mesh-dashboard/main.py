import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from core.pipeline import run_pipeline, reset_pipeline
from core.attack_engine import Qwen3Attacker
from core.metrics import SecurityMetrics

app = FastAPI(title="DOF-MESH Governance Dashboard", version="0.8.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# State global (en producción: Redis o DB)
metrics = SecurityMetrics()
attacker = Qwen3Attacker()
attack_history = []  # últimos 100 ataques


class AttackRequest(BaseModel):
    payload: Optional[str] = None
    category: str = "prompt_injection"  # prompt_injection | jailbreak | goal_hijacking | data_exfil
    context: Optional[dict] = None


@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")


@app.post("/api/attack")
def simulate_attack(req: AttackRequest):
    """
    Simula un ataque al pipeline DOF-MESH.
    Si payload está vacío, el attacker (Qwen3) genera uno aleatorio.
    """
    payload = attacker.generate_attack(req.category, req.payload)
    result = run_pipeline(payload, req.category, req.context)
    metrics.record(result)
    
    entry = {
        "payload": result.payload,
        "category": result.category,
        "blocked": result.blocked,
        "blocked_at_layer": result.blocked_at_layer,
        "layers_traversed": result.layers_traversed,
        "detail": result.detail,
    }
    attack_history.insert(0, entry)
    if len(attack_history) > 100:
        attack_history.pop()
    
    return {
        "result": entry,
        "metrics": metrics.to_dict(),
    }


@app.post("/api/batch")
def run_batch(n: int = 44):
    """
    Ejecuta n ataques automáticos (red team suite).
    Default: 44 vectores (el full suite de DOF-MESH).
    """
    batch = attacker.generate_batch(n)
    results = []
    for attack in batch:
        result = run_pipeline(attack["payload"], attack["category"])
        metrics.record(result)
        results.append({
            "category": attack["category"],
            "payload": attack["payload"][:80],
            "blocked": result.blocked,
            "blocked_at_layer": result.blocked_at_layer,
        })
    return {
        "attacks_run": n,
        "results": results,
        "metrics": metrics.to_dict(),
    }


@app.get("/api/metrics")
def get_metrics():
    return metrics.to_dict()


@app.get("/api/history")
def get_history():
    return {"history": attack_history[:20]}


@app.get("/api/blockchain")
def get_blockchain_state():
    import urllib.request
    import json
    url = "https://api.avax.network/ext/bc/C/rpc"
    headers = {"Content-Type": "application/json"}
    data = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
    try:
        req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=3) as response:
            res = json.loads(response.read().decode())
            block_hex = res.get("result", "0x0")
            block_num = int(block_hex, 16)
            return {"block_number": block_num, "status": "active", "chain": "Avalanche C-Chain"}
    except Exception as e:
        return {"block_number": 19482092, "status": "error", "error": str(e), "chain": "Avalanche C-Chain"}


@app.post("/api/reset")
def reset_metrics():
    global metrics, attack_history
    metrics = SecurityMetrics()
    attack_history = []
    reset_pipeline()  # Recrea instancias: limpia rate-limit y cualquier estado interno
    return {"status": "reset", "metrics": metrics.to_dict()}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
