import sys
import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

from .config import ConfigLoader
from .ingest import SecopIngester
from .normalize import SecopNormalizer
from .rules import SecopRulesEngine
from .evidence import SecopEvidenceGenerator
from .agent import SecopAuditAgent

def to_number(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace(",", "").strip())
    except Exception:
        return 0.0

def load_csv_data(filepath: Path) -> List[Dict[str, str]]:
    if not filepath.exists():
        print(f"Error: Normalized file not found at {filepath}. Please run 'normalize' first.")
        sys.exit(1)
    rows = []
    with filepath.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(dict(r))
    return rows

def load_json_data(filepath: Path) -> Dict[str, Any]:
    if not filepath.exists():
        return {}
    with filepath.open("r", encoding="utf-8") as f:
        return json.load(f)

def run_cli():
    parser = argparse.ArgumentParser(
        description="DOF-SECOPSENTINEL: Agente de análisis y gobernanza para contratación pública colombiana (SECOP II)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # 1. INGEST command
    parser_ingest = subparsers.add_parser("ingest", help="Descarga datos crudos desde Socrata API")
    parser_ingest.add_argument("--limit", type=int, default=5000, help="Límite de registros a descargar")
    parser_ingest.add_argument("--offset", type=int, default=0, help="Offset de paginación")
    parser_ingest.add_argument("--dep", type=str, default="Antioquia", help="Departamento de filtro")
    parser_ingest.add_argument("--query", type=str, default=None, help="Búsqueda de texto crudo ($q)")
    parser_ingest.add_argument("--where", type=str, default=None, help="Cláusula WHERE de Socrata (ej: 'valor_del_contrato >= 500000000')")
    parser_ingest.add_argument("--filename", type=str, default=None, help="Nombre del archivo de destino")

    # 2. NORMALIZE command
    parser_normalize = subparsers.add_parser("normalize", help="Limpia, quita duplicados e inyecta columnas seguras")
    parser_normalize.add_argument("--output", type=str, default="secop_antioquia_contratos_normalizados.csv", help="Nombre del archivo CSV normalizado de salida")

    # 3. ANALYZE command
    parser_analyze = subparsers.add_parser("analyze", help="Aplica reglas analíticas y genera reportes/evidencia")
    parser_analyze.add_argument("--input-csv", type=str, default="secop_antioquia_contratos_normalizados.csv", help="Nombre del archivo CSV normalizado de entrada")
    parser_analyze.add_argument("--output-csv", type=str, default="secop_antioquia_hallazgos_dof.csv", help="Nombre del archivo CSV de hallazgos")
    parser_analyze.add_argument("--output-json", type=str, default="secop_antioquia_findings_dof.json", help="Nombre del archivo JSON de hallazgos")
    parser_analyze.add_argument("--evidence-json", type=str, default="secop_antioquia_evidence_pack.json", help="Nombre del archivo JSON de evidence pack")
    parser_analyze.add_argument("--summary-txt", type=str, default="secop_antioquia_hallazgos_resumen.txt", help="Nombre del archivo resumen de texto")

    # 4. QUERY command
    parser_query = subparsers.add_parser("query", help="Realiza filtros y preguntas al agente")
    parser_query.add_argument("--top-value", type=int, default=None, help="Muestra los N contratos de mayor valor")
    parser_query.add_argument("--entity", type=str, default=None, help="Filtra por nombre de la entidad (coincidencia parcial)")
    parser_query.add_argument("--provider", type=str, default=None, help="Filtra por nombre del proveedor (coincidencia parcial)")
    parser_query.add_argument("--flag", type=str, default=None, help="Filtra por ID de bandera activada (ej: REVIEW_DIRECT_HIGH_VALUE)")
    parser_query.add_argument("--min-value", type=float, default=None, help="Filtra por valor mínimo del contrato")
    parser_query.add_argument("--city", type=str, default=None, help="Filtra por ciudad/municipio")
    parser_query.add_argument("--prompt", type=str, default=None, help="Pregunta libre para el agente")
    parser_query.add_argument("--model", type=str, default="phi4", help="Modelo de Ollama a utilizar (def: phi4)")

    # 5. INTERACTIVE command
    parser_interactive = subparsers.add_parser("interactive", help="Inicia sesión interactiva con el agente de auditoría")
    parser_interactive.add_argument("--model", type=str, default="phi4", help="Modelo de Ollama a utilizar (def: phi4)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialize loaders
    base_dir = Path(__file__).parent.parent
    cfg_loader = ConfigLoader(base_dir)
    
    if args.command == "ingest":
        meta = cfg_loader.get_dataset_metadata()
        safe_fields = cfg_loader.get_safe_fields()
        raw_dir = base_dir / "data" / "raw"
        
        ingester = SecopIngester(
            csv_endpoint=meta.get("csv_endpoint"),
            safe_fields=safe_fields,
            raw_dir=raw_dir
        )
        try:
            output_file = ingester.fetch(
                limit=args.limit,
                offset=args.offset,
                department=args.dep,
                query=args.query,
                where=args.where,
                filename=args.filename
            )
            print(f"Descarga finalizada con éxito. Archivo: {output_file}")
        except Exception as e:
            print(f"Error durante la ingesta: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "normalize":
        safe_fields = cfg_loader.get_safe_fields()
        raw_dir = base_dir / "data" / "raw"
        normalized_dir = base_dir / "data" / "normalized"
        
        raw_files = list(raw_dir.glob("*.csv"))
        if not raw_files:
            print(f"No se encontraron archivos CSV crudos en {raw_dir}. Ejecuta 'ingest' primero.")
            sys.exit(1)
            
        print(f"Archivos encontrados para normalizar: {[f.name for f in raw_files]}")
        normalizer = SecopNormalizer(safe_fields=safe_fields, normalized_dir=normalized_dir)
        
        try:
            output_csv, metrics = normalizer.normalize(raw_files, args.output)
            print("OK_NORMALIZADO")
            print(f"CSV normalizado guardado en: {output_csv}")
            print(f"Contratos únicos extraídos: {metrics['total_unique_contracts']}")
            print(f"Contratos >= 500M COP: {metrics['high_value_contracts_500m_or_more']}")
            print(f"Contratación directa >= 500M COP: {metrics['direct_high_value_contracts_500m_or_more']}")
        except Exception as e:
            print(f"Error en normalización: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "analyze":
        rules = cfg_loader.get_rules()
        normalized_dir = base_dir / "data" / "normalized"
        evidence_dir = base_dir / "data" / "evidence"
        reports_dir = base_dir / "reports"
        
        input_csv_path = normalized_dir / args.input_csv
        
        # Load normalized rows
        rows = load_csv_data(input_csv_path)
        print(f"Procesando {len(rows)} contratos...")
        
        # Run rules engine
        engine = SecopRulesEngine(rules_config=rules)
        findings = engine.analyze_dataset(rows)
        
        # Load normalization metrics if evidence pack existed (or compute dummy/partial ones)
        evidence_pack_path = evidence_dir / args.evidence_json
        norm_metrics = {}
        if evidence_pack_path.exists():
            norm_metrics = load_json_data(evidence_pack_path)
        else:
            # Fallback inline calculation
            high_value = [r for r in rows if to_number(r.get("valor_del_contrato")) >= 500_000_000]
            direct_high = [
                r for r in rows
                if "directa" in (r.get("modalidad_de_contratacion") or "").lower()
                and to_number(r.get("valor_del_contrato")) >= 500_000_000
            ]
            norm_metrics = {
                "input_files": ["secop_antioquia_contratos_normalizados.csv"],
                "input_file_hashes_sha256": {},
                "source_row_counts": {},
                "total_unique_contracts": len(rows),
                "total_contract_value": sum(to_number(r.get("valor_del_contrato")) for r in rows),
                "high_value_contracts_500m_or_more": len(high_value),
                "direct_high_value_contracts_500m_or_more": len(direct_high),
            }

        # Generate reports
        generator = SecopEvidenceGenerator(evidence_dir=evidence_dir, reports_dir=reports_dir)
        paths = generator.generate_all(
            normalization_metrics=norm_metrics,
            findings=findings,
            total_contracts=len(rows),
            original_rows=rows,
            evidence_pack_filename=args.evidence_json,
            findings_filename=args.output_json,
            summary_txt_filename=args.summary_txt,
            findings_csv_filename=args.output_csv
        )
        
        print("OK_HALLAZGOS_DOF")
        print(f"Hallazgos generados: {len(findings)}")
        print(f"CSV de hallazgos: {paths['findings_csv']}")
        print(f"JSON de hallazgos: {paths['findings_json']}")
        print(f"Evidence Pack: {paths['evidence_pack_json']}")
        print(f"Resumen de texto: {paths['summary_txt']}")

    elif args.command in ["query", "interactive"]:
        # Query matching contracts using findings or normalized file
        reports_dir = base_dir / "reports"
        evidence_dir = base_dir / "data" / "evidence"
        
        # Load findings CSV which contains the flags pre-computed
        findings_csv_path = reports_dir / "secop_antioquia_hallazgos_dof.csv"
        
        # If the findings file doesn't exist, try to load normal normalized CSV
        if not findings_csv_path.exists():
            findings_csv_path = base_dir / "data" / "normalized" / "secop_antioquia_contratos_normalizados.csv"
            
        if not findings_csv_path.exists():
            print("Error: No se encontró secop_antioquia_hallazgos_dof.csv ni secop_antioquia_contratos_normalizados.csv. Ejecuta 'analyze' primero.")
            sys.exit(1)
            
        rows = load_csv_data(findings_csv_path)
        
        # Load findings JSON summary for the metrics context
        findings_json_path = evidence_dir / "secop_antioquia_findings_dof.json"
        summary_metrics = load_json_data(findings_json_path)
        
        # Instantiate Agent
        agent = SecopAuditAgent(model=args.model)
        
        # Sub-routing for CLI queries
        if args.command == "query":
            # Apply filters
            filtered = rows
            
            if args.entity:
                val = args.entity.lower()
                filtered = [r for r in filtered if val in (r.get("nombre_entidad") or "").lower()]
                
            if args.provider:
                val = args.provider.lower()
                filtered = [r for r in filtered if val in (r.get("proveedor_adjudicado") or "").lower()]
                
            if args.flag:
                val = args.flag.lower()
                filtered = [r for r in filtered if val in (r.get("flags") or "").lower()]
                
            if args.min_value is not None:
                val = args.min_value
                filtered = [r for r in filtered if to_number(r.get("valor_del_contrato")) >= val]
                
            if args.city:
                val = args.city.lower()
                filtered = [r for r in filtered if val in (r.get("ciudad") or "").lower()]

            # Sort descending by value
            filtered = sorted(filtered, key=lambda x: -to_number(x.get("valor_del_contrato")))
            
            # Limit results
            if args.top_value is not None:
                filtered = filtered[:args.top_value]

            # Output results
            if args.prompt:
                # Ask agent with LLM/Template reasoning
                print(f"Consultando al Agente con la pregunta: '{args.prompt}'...")
                print("-" * 60)
                response = agent.query(args.prompt, filtered, summary_metrics)
                print(response)
                print("-" * 60)
            else:
                # Standard query output: Print table
                if not filtered:
                    print("No se encontraron contratos con los filtros aplicados.")
                    return
                print(f"Mostrando {len(filtered)} contratos coincidentes:")
                print("=" * 100)
                print(f"{'ENTIDAD':<30} | {'PROVEEDOR':<25} | {'VALOR':<15} | {'BANDERAS':<20}")
                print("-" * 100)
                for r in filtered[:25]:
                    ent = (r.get("nombre_entidad") or "")[:30]
                    prov = (r.get("proveedor_adjudicado") or "")[:25]
                    val = f"{to_number(r.get('valor_del_contrato')):#,.0f}"[:15]
                    flags = (r.get("flags") or "None")[:20]
                    print(f"{ent:<30} | {prov:<25} | {val:<15} | {flags:<20}")
                if len(filtered) > 25:
                    print(f"... y {len(filtered) - 25} registros más (usa --top-value para limitar).")
                print("=" * 100)

        elif args.command == "interactive":
            print("=========================================================================")
            print("Sesión Interactiva del Agente de Auditoría DOF-SECOPSENTINEL")
            print(f"Modelo LLM: {args.model} | Servidor Ollama: {agent.ollama_url}")
            print("Escribe tu pregunta o 'salir' para terminar.")
            print("Nota: Las respuestas cumplen estrictamente las restricciones de lenguaje y hechos.")
            print("=========================================================================")
            
            while True:
                try:
                    user_q = input("\nPregunta > ").strip()
                    if not user_q:
                        continue
                    if user_q.lower() in ["salir", "exit", "quit", "q"]:
                        print("Sesión terminada.")
                        break
                        
                    # Find if any simple keywords exist to pre-filter matching records
                    # (helps with context size in LLM prompts)
                    filtered = rows
                    # Basic entity heuristics
                    for word in user_q.split():
                        if len(word) > 4:
                            # If word matches entity, filter
                            temp_filt = [r for r in filtered if word.lower() in (r.get("nombre_entidad") or "").lower()]
                            if len(temp_filt) >= 5: # keep some records
                                filtered = temp_filt
                                
                    filtered = sorted(filtered, key=lambda x: -to_number(x.get("valor_del_contrato")))[:15]
                    
                    print("\nProcesando análisis...")
                    response = agent.query(user_q, filtered, summary_metrics)
                    print("\n" + response)
                    print("-" * 60)
                except KeyboardInterrupt:
                    print("\nSesión terminada.")
                    break
                except Exception as e:
                    print(f"Error procesando consulta: {e}")
