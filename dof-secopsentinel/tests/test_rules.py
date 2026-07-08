import unittest
from secopsentinel.rules import SecopRulesEngine

class TestSecopRulesEngine(unittest.TestCase):
    def setUp(self):
        # Configure rule mocks matching rules.yaml
        self.rules_config = [
            {
                "id": "REVIEW_HIGH_VALUE",
                "type": "value_threshold",
                "threshold": 500000000,
                "meaning": "Contrato con valor igual o superior a 500 millones COP.",
                "risk_level": "REVIEW"
            },
            {
                "id": "REVIEW_DIRECT_HIGH_VALUE",
                "type": "direct_high_value",
                "threshold": 500000000,
                "keyword": "directa",
                "meaning": "Contrato de modalidad directa con valor igual o superior a 500 millones COP.",
                "risk_level": "REVIEW"
            },
            {
                "id": "REVIEW_REPEATED_PROVIDER_ENTITY",
                "type": "repeated_provider",
                "threshold": 3,
                "meaning": "Proveedor aparece 3 o más veces asociado a la misma entidad dentro del paquete analizado.",
                "risk_level": "REVIEW"
            },
            {
                "id": "REVIEW_LONG_ADDITION_DAYS",
                "type": "addition_days",
                "threshold": 90,
                "meaning": "Contrato con 90 días o más adicionados.",
                "risk_level": "REVIEW"
            },
            {
                "id": "BLOCK_MISSING_URL",
                "type": "missing_url",
                "meaning": "Registro sin URL verificable del proceso SECOP o valor inválido.",
                "risk_level": "BLOCK"
            }
        ]
        self.engine = SecopRulesEngine(self.rules_config)

    def test_review_high_value(self):
        row = {
            "valor_del_contrato": "500000000",
            "modalidad_de_contratacion": "Licitacion publica",
            "dias_adicionados": "10",
            "urlproceso": "http://secop.gov.co/process"
        }
        flags, reasons = self.engine.evaluate_row(row, {})
        self.assertIn("REVIEW_HIGH_VALUE", flags)
        self.assertNotIn("REVIEW_DIRECT_HIGH_VALUE", flags)

    def test_review_direct_high_value(self):
        row = {
            "valor_del_contrato": "500000000",
            "modalidad_de_contratacion": "Contratación directa",
            "dias_adicionados": "0",
            "urlproceso": "http://secop.gov.co/process"
        }
        flags, reasons = self.engine.evaluate_row(row, {})
        self.assertIn("REVIEW_HIGH_VALUE", flags)
        self.assertIn("REVIEW_DIRECT_HIGH_VALUE", flags)

    def test_review_long_addition_days(self):
        row = {
            "valor_del_contrato": "10000000",
            "modalidad_de_contratacion": "Minima cuantia",
            "dias_adicionados": "90",
            "urlproceso": "http://secop.gov.co/process"
        }
        flags, reasons = self.engine.evaluate_row(row, {})
        self.assertIn("REVIEW_LONG_ADDITION_DAYS", flags)

    def test_block_missing_url(self):
        row = {
            "valor_del_contrato": "10000000",
            "modalidad_de_contratacion": "Minima cuantia",
            "dias_adicionados": "0",
            "urlproceso": "No Definido"
        }
        flags, reasons = self.engine.evaluate_row(row, {})
        self.assertIn("BLOCK_MISSING_URL", flags)

    def test_repeated_provider_entity(self):
        # We need to simulate the dataset matching frequency >= 3
        dataset = [
            {"nombre_entidad": "ITM", "proveedor_adjudicado": "XYZ Corp"},
            {"nombre_entidad": "ITM", "proveedor_adjudicado": "XYZ Corp"},
            {"nombre_entidad": "ITM", "proveedor_adjudicado": "XYZ Corp"},
        ]
        
        # Test evaluate_row with precomputed counter
        counters = self.engine.compute_counters(dataset)
        row = {
            "nombre_entidad": "ITM",
            "proveedor_adjudicado": "XYZ Corp",
            "valor_del_contrato": "100000",
            "dias_adicionados": "0",
            "urlproceso": "http://secop.gov.co/process"
        }
        
        flags, reasons = self.engine.evaluate_row(row, counters)
        self.assertIn("REVIEW_REPEATED_PROVIDER_ENTITY", flags)

if __name__ == "__main__":
    unittest.main()
