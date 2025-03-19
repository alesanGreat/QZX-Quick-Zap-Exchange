#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Comando CompareFiles - Compara el contenido de dos archivos
Using the centralized recursive parameter utility
"""

import os
import difflib
from Core.command_base import CommandBase
from Core.recursive_findfiles_utils import parse_recursive_parameter

class CompareFilesCommand(CommandBase):
    """
    Comando para comparar dos archivos y mostrar sus diferencias
    
    This version uses the centralized recursive parameter utility.
    """
    
    name = "compareFiles"
    description = "Compara dos archivos y muestra sus diferencias, útil para IDE"
    category = "dev"
    
    parameters = [
        {
            'name': 'file1',
            'description': 'Ruta al primer archivo',
            'required': True
        },
        {
            'name': 'file2',
            'description': 'Ruta al segundo archivo',
            'required': True
        },
        {
            'name': 'mode',
            'description': 'Modo de comparación: "full" (completo), "summary" (resumen) o "percent" (porcentaje)',
            'required': False,
            'default': 'full'
        }
    ]
    
    examples = [
        {
            'command': 'qzx compareFiles "archivo1.py" "archivo2.py"',
            'description': 'Comparar dos archivos Python y mostrar todas las diferencias'
        },
        {
            'command': 'qzx compareFiles "archivo1.txt" "archivo2.txt" "summary"',
            'description': 'Mostrar un resumen de diferencias entre dos archivos de texto'
        },
        {
            'command': 'qzx compareFiles "versión1.js" "versión2.js" "percent"',
            'description': 'Mostrar el porcentaje de similitud entre dos archivos JavaScript'
        }
    ]
    
    def execute(self, file1, file2, mode='full'):
        """
        Compara dos archivos y muestra sus diferencias
        
        Args:
            file1: Ruta al primer archivo
            file2: Ruta al segundo archivo
            mode: Modo de comparación (full, summary, percent)
            
        Returns:
            Resultado de la comparación en el formato especificado
        """
        # Verificar que los archivos existen
        if not os.path.exists(file1):
            return {
                "success": False,
                "error": f"Error: El archivo '{file1}' no existe"
            }
        if not os.path.exists(file2):
            return {
                "success": False,
                "error": f"Error: El archivo '{file2}' no existe"
            }
        
        # Verificar que son archivos (no directorios)
        if not os.path.isfile(file1):
            return {
                "success": False,
                "error": f"Error: '{file1}' no es un archivo"
            }
        if not os.path.isfile(file2):
            return {
                "success": False,
                "error": f"Error: '{file2}' no es un archivo"
            }
        
        try:
            # Leer el contenido de los archivos
            with open(file1, 'r', encoding='utf-8', errors='replace') as f:
                content1 = f.readlines()
            
            with open(file2, 'r', encoding='utf-8', errors='replace') as f:
                content2 = f.readlines()
            
            # Determinar qué tipo de comparación hacer basado en el modo
            if mode.lower() == 'full':
                result = self._compare_full(file1, file2, content1, content2)
            elif mode.lower() == 'summary':
                result = self._compare_summary(file1, file2, content1, content2)
            elif mode.lower() == 'percent':
                result = self._compare_percent(file1, file2, content1, content2)
            else:
                return {
                    "success": False,
                    "error": f"Error: Modo de comparación '{mode}' no válido. Use 'full', 'summary' o 'percent'."
                }
                
            # Formatear resultado como diccionario para consistencia
            if isinstance(result, str):
                return {
                    "success": True,
                    "file1": file1,
                    "file2": file2,
                    "mode": mode,
                    "result": result,
                    "message": f"Comparación de archivos '{file1}' y '{file2}' completada."
                }
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Error comparando archivos: {str(e)}"
            }
    
    def _compare_full(self, file1, file2, content1, content2):
        """
        Realiza una comparación completa línea por línea
        """
        diff = difflib.unified_diff(
            content1, content2,
            fromfile=file1, tofile=file2,
            lineterm=''
        )
        
        diff_text = list(diff)
        
        if not diff_text:
            return {
                "success": True,
                "file1": file1,
                "file2": file2,
                "identical": True,
                "message": f"Los archivos '{file1}' y '{file2}' son idénticos."
            }
        
        result = [f"Diferencias entre '{file1}' y '{file2}':"]
        result.extend(diff_text)
        
        # Estadísticas
        result.append("\nEstadísticas:")
        added, removed = 0, 0
        for line in diff_text:
            if line.startswith('+') and not line.startswith('+++'):
                added += 1
            elif line.startswith('-') and not line.startswith('---'):
                removed += 1
        
        result.append(f"- Líneas añadidas: {added}")
        result.append(f"- Líneas eliminadas: {removed}")
        result.append(f"- Cambios totales: {added + removed}")
        
        return {
            "success": True,
            "file1": file1,
            "file2": file2,
            "identical": False,
            "added_lines": added,
            "removed_lines": removed,
            "total_changes": added + removed,
            "diff": "\n".join(result)
        }
    
    def _compare_summary(self, file1, file2, content1, content2):
        """
        Realiza una comparación resumida mostrando solo la cantidad de diferencias
        """
        matcher = difflib.SequenceMatcher(None, content1, content2)
        
        # Obtener los bloques que coinciden
        blocks = matcher.get_matching_blocks()
        
        # Calcular estadísticas
        similarity = matcher.ratio() * 100
        total_lines1 = len(content1)
        total_lines2 = len(content2)
        
        # Contar líneas idénticas
        identical_lines = sum(block.size for block in blocks if block.size > 0)
        
        # Contar cambios
        changes = max(total_lines1, total_lines2) - identical_lines
        
        summary = [
            f"Resumen de diferencias entre '{file1}' y '{file2}':",
            f"- Similaridad: {similarity:.2f}%",
            f"- Líneas en archivo 1: {total_lines1}",
            f"- Líneas en archivo 2: {total_lines2}",
            f"- Líneas idénticas: {identical_lines}",
            f"- Cambios detectados: {changes}"
        ]
        
        return {
            "success": True,
            "file1": file1,
            "file2": file2,
            "identical": changes == 0,
            "similarity": similarity,
            "lines_file1": total_lines1,
            "lines_file2": total_lines2,
            "identical_lines": identical_lines,
            "changes": changes,
            "summary": "\n".join(summary)
        }
    
    def _compare_percent(self, file1, file2, content1, content2):
        """
        Realiza una comparación que devuelve solo el porcentaje de similitud
        """
        # Calcular la similitud usando SequenceMatcher
        matcher = difflib.SequenceMatcher(None, content1, content2)
        similarity = matcher.ratio() * 100
        
        # Si son idénticos
        identical = similarity >= 99.99
        
        return {
            "success": True,
            "file1": file1,
            "file2": file2,
            "identical": identical,
            "similarity": similarity,
            "message": f"Similitud entre '{file1}' y '{file2}': {similarity:.2f}%"
        } 