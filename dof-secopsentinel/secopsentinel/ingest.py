import requests
from pathlib import Path
from typing import Dict, Any, List

class SecopIngester:
    def __init__(self, csv_endpoint: str, safe_fields: List[str], raw_dir: Path):
        self.csv_endpoint = csv_endpoint
        self.safe_fields = safe_fields
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, 
              limit: int = 5000, 
              offset: int = 0, 
              department: str = "Antioquia",
              query: str = None,
              where: str = None,
              filename: str = None) -> Path:
        """
        Fetches CSV data from Socrata (Datos Abiertos Colombia) using safe fields and custom filters,
        and saves it to the raw_dir.
        """
        select_cols = ",".join(self.safe_fields)
        
        params = {
            "$select": select_cols,
            "$limit": str(limit),
            "$offset": str(offset),
        }
        
        if department:
            params["departamento"] = department
            
        if query:
            params["$q"] = query
            
        if where:
            params["$where"] = where

        # Construct file name if not provided
        if not filename:
            parts = ["secop", department.lower().replace(" ", "_")]
            if query:
                parts.append(query.lower().replace(" ", "_"))
            if where:
                parts.append("filtered")
            parts.append(f"limit_{limit}")
            filename = "_".join(parts) + ".csv"
            
        output_path = self.raw_dir / filename
        
        print(f"Downloading from {self.csv_endpoint} with filters: {params}")
        
        # Socrata uses $ prefixed keys which needs to be passed correctly
        response = requests.get(self.csv_endpoint, params=params, timeout=60)
        
        if response.status_code != 200:
            raise requests.HTTPError(
                f"Failed to fetch data from SECOP II API. Status code: {response.status_code}. Response: {response.text[:200]}"
            )
            
        # Write to file
        with output_path.open("wb") as f:
            f.write(response.content)
            
        print(f"Successfully downloaded raw data: {output_path} ({len(response.content)} bytes)")
        return output_path
