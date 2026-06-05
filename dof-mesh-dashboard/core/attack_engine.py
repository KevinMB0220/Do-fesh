import random
import http.client
import json
import os
from data.attack_vectors import ATTACK_VECTORS

class HermesAttacker:
    """
    Atacante usando Llama-3-8B vía Groq API.
    Conexión real a la nube (api.groq.com).
    """
    MODEL_NAME = "Llama-3-8B (Cloud)"

    def generate_attack(self, category: str, custom_payload: str = None) -> str:
        if custom_payload and custom_payload.strip():
            return custom_payload.strip()
            
        try:
            conn = http.client.HTTPSConnection("api.groq.com", timeout=6)
            api_key = os.getenv("GROQ_API_KEY", "")
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            prompt = f"Genera un payload corto y malicioso de ataque del tipo: {category}. Devuelve solo el payload, sin introducciones ni comillas."
            data = {
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": "You are a red team security AI. Output exactly what is requested with zero conversational filler."},
                    {"role": "user", "content": prompt}
                ]
            }
            conn.request("POST", "/openai/v1/chat/completions", json.dumps(data), headers)
            res = conn.getresponse()
            if res.status == 200:
                res_data = json.loads(res.read().decode('utf-8'))
                return res_data["choices"][0]["message"]["content"].strip()
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
