#!/usr/bin/env python
# -*- coding: utf-8 -*-

from Commands.FileCommands.FindFiles import FindFilesCommand

def prueba_basica():
    """Prueba básica de FindFiles con parámetros válidos"""
    cmd = FindFilesCommand()
    result = cmd.execute('/app/test-data/godot', '*.py', '-r')
    print(f"Encontrados {len(result['results'])} archivos Python en Godot")
    
    # Mostrar los primeros 5 resultados
    print("\nPrimeros 5 archivos:")
    for i, file_info in enumerate(result['results'][:5]):
        print(f"{i+1}. {file_info['path']}")

def prueba_ruta_invalida():
    """Prueba con una ruta que no existe"""
    cmd = FindFilesCommand()
    result = cmd.execute('/ruta/que/no/existe', '*.py', '-r')
    print(f"Prueba con ruta inválida - success: {result['success']}")
    print(f"Error: {result.get('error', 'Sin error')}")
    print(f"Número de resultados: {len(result['results'])}")

def prueba_parametros_invalidos():
    """Prueba con parámetros inválidos o extremos"""
    cmd = FindFilesCommand()
    
    # Prueba con límite inválido
    result = cmd.execute('.', '*', '-r', limit="no_soy_un_numero")
    print(f"Prueba con límite inválido - success: {result['success']}")
    print(f"Error: {result.get('error', 'Sin error')}")
    print(f"Número de resultados: {len(result['results'])}")
    
    # Prueba con formato inválido
    result = cmd.execute('.', '*', '-r', format="formato_inexistente")
    print(f"Prueba con formato inválido - success: {result['success']}")
    print(f"Error: {result.get('error', 'Sin error')}")
    print(f"Número de resultados: {len(result['results'])}")

def main():
    """Función principal para ejecutar todas las pruebas"""
    print("=== PRUEBA BÁSICA ===")
    try:
        prueba_basica()
    except Exception as e:
        print(f"Error en prueba básica: {str(e)}")
    
    print("\n=== PRUEBA CON RUTA INVÁLIDA ===")
    try:
        prueba_ruta_invalida()
    except Exception as e:
        print(f"Error en prueba con ruta inválida: {str(e)}")
    
    print("\n=== PRUEBA CON PARÁMETROS INVÁLIDOS ===")
    try:
        prueba_parametros_invalidos()
    except Exception as e:
        print(f"Error en prueba con parámetros inválidos: {str(e)}")

if __name__ == "__main__":
    main() 