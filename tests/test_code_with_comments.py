#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This is a test Python file with code and mixed language comments.
Este es un archivo Python de prueba con código y comentarios en idiomas mezclados.
"""

import os
import sys
import json
from datetime import datetime

# English comment: This function calculates the factorial of a number
# Comentario en español: Esta función calcula el factorial de un número
def factorial(n):
    """
    Calculate the factorial of a number.
    
    Calcula el factorial de un número.
    
    Args:
        n (int): The number to calculate factorial for
               El número para calcular su factorial
    
    Returns:
        int: The factorial of the number
             El factorial del número
    """
    if n == 0 or n == 1:
        return 1
    else:
        return n * factorial(n - 1)

# A class with mixed language documentation
# Una clase con documentación en idiomas mezclados
class LanguageProcessor:
    """
    A class for processing text in different languages.
    Una clase para procesar texto en diferentes idiomas.
    """
    
    def __init__(self, text):
        """
        Initialize the language processor.
        Inicializa el procesador de lenguaje.
        
        Args:
            text (str): The text to process
                       El texto a procesar
        """
        self.text = text
        self.word_count = 0
        self.char_count = 0
        self.line_count = 0
    
    def analyze(self):
        """
        Analyze the text and count words, characters, and lines.
        Analiza el texto y cuenta palabras, caracteres y líneas.
        """
        if not self.text:
            return {
                "error": "No text provided",
                "error_es": "No se proporcionó texto"
            }
        
        self.line_count = len(self.text.split('\n'))
        self.word_count = len(self.text.split())
        self.char_count = len(self.text)
        
        return {
            "lines": self.line_count,
            "words": self.word_count,
            "chars": self.char_count,
            "summary": f"The text has {self.line_count} lines, {self.word_count} words, and {self.char_count} characters.",
            "resumen": f"El texto tiene {self.line_count} líneas, {self.word_count} palabras y {self.char_count} caracteres."
        }

# Some more code with comments
# Algo más de código con comentarios
def main():
    """
    Main function of the program.
    Función principal del programa.
    """
    # Print welcome message
    # Imprimir mensaje de bienvenida
    print("Welcome to the language test program!")
    print("¡Bienvenido al programa de prueba de idiomas!")
    
    # Calculate factorial
    # Calcular factorial
    num = 5
    result = factorial(num)
    print(f"Factorial of {num} is {result}")
    print(f"El factorial de {num} es {result}")
    
    # Use language processor
    # Usar procesador de lenguaje
    example_text = """
    This is an example text with multiple lines.
    It contains English and Spanish sentences.
    This should be detected by our language analyzer.
    
    Este es un texto de ejemplo con múltiples líneas.
    Contiene frases en inglés y español.
    Esto debería ser detectado por nuestro analizador de idiomas.
    """
    
    processor = LanguageProcessor(example_text)
    analysis = processor.analyze()
    
    print(analysis["summary"])
    print(analysis["resumen"])

if __name__ == "__main__":
    main() 