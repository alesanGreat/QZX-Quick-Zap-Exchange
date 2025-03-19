#!/usr/bin/env python
# -*- coding: utf-8 -*-

from Commands.FileCommands.FindFiles import FindFilesCommand

def main():
    # Crear una instancia del comando
    find_command = FindFilesCommand()
    
    # Ejecutar el comando con parámetros simples
    search_path = "test-data/godot"
    pattern = "*.py"
    
    # Opción de imprimir el patrón para depuración
    print(f"Buscando archivos que coincidan con el patrón '{pattern}' en '{search_path}'")
    
    # Ejecutar el comando con seguimiento detallado
    result_dict = find_command.execute(
        search_path=search_path,
        pattern=pattern,
        recursive="-r",
        format="detailed"
    )
    
    # Verificar si la operación fue exitosa
    if result_dict.get("success", False):
        # Obtener los resultados
        results = result_dict.get("results", [])
        
        # Imprimir resultados
        print(f"Resultados encontrados: {len(results)}")
        
        # Mostrar los primeros 10 resultados si hay muchos
        max_display = 10
        for i, item in enumerate(results[:max_display]):
            print(f"{i+1}. {item}")
        
        if len(results) > max_display:
            print(f"... y {len(results) - max_display} más")
            
        # Imprimir estadísticas
        print(f"Tamaño total: {result_dict.get('total_size_readable', '0 B')}")
    else:
        # Si hay error, mostrarlo
        print(f"Error: {result_dict.get('error', 'Error desconocido')}")

if __name__ == "__main__":
    main() 