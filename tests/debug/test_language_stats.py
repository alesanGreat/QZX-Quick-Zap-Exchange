#!/usr/bin/env python
# -*- coding: utf-8 -*-

from Commands.FileCommands.GetProgrammingLanguageStatsFromFile import GetProgrammingLanguageStatsFromFileCommand

def main():
    try:
        cmd = GetProgrammingLanguageStatsFromFileCommand()
        
        # Analizar solo los archivos de primer nivel para ser más rápido
        print("ANÁLISIS BÁSICO DE GODOT:")
        result = cmd.execute('/app/test-data/godot/*', False, None, None)
        
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