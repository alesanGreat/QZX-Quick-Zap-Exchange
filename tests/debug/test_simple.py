#!/usr/bin/env python
# -*- coding: utf-8 -*-

from Commands.FileCommands.FindFiles import FindFilesCommand

def main():
    try:
        cmd = FindFilesCommand()
        
        # Prueba con el repositorio de Godot
        print("PRUEBA GODOT")
        result = cmd.execute('/app/test-data/godot', '*.py', '-r')
        print(f"Archivos Python: {len(result['results'])}")
        
        # Prueba con una ruta inválida
        print("\nPRUEBA RUTA INVÁLIDA")
        result_error = cmd.execute('/ruta/no/existe', '*.py', '-r')
        print(f"Success: {result_error['success']}")
        print(f"Resultados: {len(result_error['results'])}")
        
        # Prueba con patrón inválido
        print("\nPRUEBA PATRÓN INVÁLIDO")
        result_pattern = cmd.execute('.', None, '-r') # Patrón None debería usar valor por defecto
        print(f"Success: {result_pattern['success']}")
        print(f"Resultados: {len(result_pattern['results'])}")
        
        # Prueba con recursión inválida
        print("\nPRUEBA RECURSIÓN INVÁLIDA")
        result_recursive = cmd.execute('.', '*', 'no-soy-recursivo')
        print(f"Success: {result_recursive['success']}")
        print(f"Resultados: {len(result_recursive['results'])}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    main() 