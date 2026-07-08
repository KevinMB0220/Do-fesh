import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from secopsentinel.normalize import SecopNormalizer

class TestSecopNormalizer(unittest.TestCase):
    def setUp(self):
        self.safe_fields = [
            "id_contrato",
            "nombre_entidad",
            "proveedor_adjudicado",
            "valor_del_contrato",
            "urlproceso"
        ]
        
    def test_clean_row_removes_unsafe_fields(self):
        normalizer = SecopNormalizer(self.safe_fields, Path("/tmp"))
        row = {
            "id_contrato": "C-1234",
            "nombre_entidad": "Alcaldia de Medellin",
            "proveedor_adjudicado": "Proveedor XYZ",
            "valor_del_contrato": "600000000",
            "urlproceso": "http://secop.gov.co/123",
            "cuenta_bancaria_supervisor": "123-456-789", # unsafe
            "cedula_representante": "10203040" # unsafe
        }
        
        clean = normalizer.clean_row(row, "test_file.csv")
        
        self.assertIn("id_contrato", clean)
        self.assertIn("nombre_entidad", clean)
        self.assertNotIn("cuenta_bancaria_supervisor", clean)
        self.assertNotIn("cedula_representante", clean)
        self.assertEqual(clean["fuente_archivo"], "test_file.csv")

    def test_deduplication_keeps_highest_value(self):
        with TemporaryDirectory() as tmpdir:
            normalized_dir = Path(tmpdir) / "normalized"
            normalizer = SecopNormalizer(self.safe_fields, normalized_dir)
            
            # Create a mock raw CSV file
            raw_file = Path(tmpdir) / "secop_raw.csv"
            with raw_file.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=self.safe_fields + ["cuenta_bancaria"])
                writer.writeheader()
                # Two records with same id_contrato but different values
                writer.writerow({
                    "id_contrato": "C-DEDUP",
                    "nombre_entidad": "Entidad A",
                    "proveedor_adjudicado": "Proveedor B",
                    "valor_del_contrato": "100000000",
                    "urlproceso": "http://secop.gov.co/1",
                    "cuenta_bancaria": "123"
                })
                writer.writerow({
                    "id_contrato": "C-DEDUP",
                    "nombre_entidad": "Entidad A",
                    "proveedor_adjudicado": "Proveedor B",
                    "valor_del_contrato": "500000000", # Higher value
                    "urlproceso": "http://secop.gov.co/1",
                    "cuenta_bancaria": "456"
                })
            
            output_csv, metrics = normalizer.normalize([raw_file], "test_normalized.csv")
            
            self.assertEqual(metrics["total_unique_contracts"], 1)
            self.assertEqual(metrics["total_contract_value"], 500000000.0)
            
            # Read normalized file and check row value
            with output_csv.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["valor_del_contrato"], "500000000")
                self.assertNotIn("cuenta_bancaria", rows[0])

if __name__ == "__main__":
    unittest.main()
