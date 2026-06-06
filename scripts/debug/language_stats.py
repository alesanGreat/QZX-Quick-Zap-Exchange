#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.commands.file.get_programming_language_stats_from_file import GetProgrammingLanguageStatsFromFileCommand

def main():
    try:
        cmd = GetProgrammingLanguageStatsFromFileCommand()
        
        # Analizar solo los archivos de primer nivel para ser más rápido
        print("ANÁLISIS BÁSICO DE GODOT:")
        result = cmd.execute('/app/artifacts/tests/data/godot/*', False, None, None)
        
        if not result['success']:
            print(f"Error: {result.get('message', 'Error desconocido')}")
            return
            
        # Mostrar información básica
        files_count = len(result.get('files', []))
        print(f"Archivos encontrados: {files_count}")
        
        # Mostrar los lenguajes encontrados
        if 'aggregated_stats' in result and 'language_distribution' in result['aggregated_stats']:
            langs = result['aggregated_stats']['language_distribution']
            print("\nLENGUAJES:")
            for lang, count in langs.items():
                print(f"{lang}: {count}")
                
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    main() 