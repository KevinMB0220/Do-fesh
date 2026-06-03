import random
import http.client
import json
from data.attack_vectors import ATTACK_VECTORS

class Qwen3Attacker:
    """
    Simulador/Interface de Qwen3 abliterated 30B.
    Conexión real a Ollama (modelo qwen3) local en http://localhost:11434.
    """
    MODEL_NAME = "Qwen3-abliterated-30B"

    def generate_attack(self, category: str, custom_payload: str = None) -> str:
        if custom_payload and custom_payload.strip():
            return custom_payload.strip()
            
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=4)
            headers = {'Content-Type': 'application/json'}
            prompt = f"Genera un payload corto y malicioso de ataque del tipo: {category}. Devuelve solo el payload, sin introducciones."
            data = {
                "model": "qwen3",
                "prompt": prompt,
                "stream": False
            }
            conn.request("POST", "/api/generate", json.dumps(data), headers)
            response = conn.getresponse()
            if response.status == 200:
                res_data = json.loads(response.read().decode())
                return res_data["response"].strip()
        except Exception:
            pass
            
        # Fallback determinista
        vectors = ATTACK_VECTORS.get(category, [])
        if not vectors:
            return "test payload"
        return random.choice(vectors)

    def generate_batch(self, n: int = 10) -> list:
        """Genera n ataques aleatorios para benchmark."""
        results = []
        for _ in range(n):
            category = random.choice(list(ATTACK_VECTORS.keys()))
            payload = self.generate_attack(category)
            results.append({"category": category, "payload": payload})
        return results
