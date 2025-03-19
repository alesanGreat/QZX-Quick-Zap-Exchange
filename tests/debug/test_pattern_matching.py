#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import fnmatch
import glob

def test_pattern_matching():
    """
    Prueba directamente el matching de patrones utilizando fnmatch y glob
    para entender por qué FindFiles no encuentra archivos .py
    """
    search_path = "test-data/godot"
    pattern = "*.py"
    
    print(f"Probando coincidencia de patrón '{pattern}' en '{search_path}'")
    
    # Verificar si el directorio existe
    if not os.path.exists(search_path):
        print(f"Error: El directorio '{search_path}' no existe")
        return
    
    # Prueba directa con glob
    print("\n1. Prueba con glob.glob:")
    glob_results = glob.glob(os.path.join(search_path, pattern))
    print(f"Encontrados {len(glob_results)} archivos")
    for i, file_path in enumerate(glob_results[:5]):
        print(f"  {i+1}. {file_path}")
    if len(glob_results) > 5:
        print(f"  ... y {len(glob_results) - 5} más")
    
    # Prueba directa con glob.glob recursivo
    print("\n2. Prueba con glob.glob recursivo:")
    glob_recursive_results = glob.glob(os.path.join(search_path, "**", pattern), recursive=True)
    print(f"Encontrados {len(glob_recursive_results)} archivos")
    for i, file_path in enumerate(glob_recursive_results[:5]):
        print(f"  {i+1}. {file_path}")
    if len(glob_recursive_results) > 5:
        print(f"  ... y {len(glob_recursive_results) - 5} más")
    
    # Prueba manual con os.walk y fnmatch
    print("\n3. Prueba con os.walk y fnmatch:")
    walk_results = []
    for root, dirs, files in os.walk(search_path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                walk_results.append(os.path.join(root, name))
    
    print(f"Encontrados {len(walk_results)} archivos")
    for i, file_path in enumerate(walk_results[:5]):
        print(f"  {i+1}. {file_path}")
    if len(walk_results) > 5:
        print(f"  ... y {len(walk_results) - 5} más")
    
    # Prueba con algunos nombres de archivo específicos
    print("\n4. Prueba de fnmatch con nombres específicos:")
    test_files = ["methods.py", "config.py", "detect.py", "test_file.txt"]
    for test_file in test_files:
        match = fnmatch.fnmatch(test_file, pattern)
        print(f"  fnmatch('{test_file}', '{pattern}') = {match}")

if __name__ == "__main__":
    test_pattern_matching() 