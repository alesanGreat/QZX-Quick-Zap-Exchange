#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderContentGen Command - Uses Gemini AI to analyze and explain file contents
"""

import os
import sys
import json
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from qzx.core.command_base import CommandBase

class WonderContentGenCommand(CommandBase):
    """
    Command to analyze and explain file contents using Gemini AI
    """
    
    name = "generateContent"
    aliases = [
        "WonderContentGen",
        "explainfile",
        "aianalyze",
        "analyzeContent",
    ]
    description = "Uses Gemini AI to analyze and explain file contents"
    category = "system"
    
    parameters = [
        {
            'name': 'file_path',
            'description': 'Path to the file to analyze',
            'required': True
        },
        {
            'name': 'sample_size',
            'description': 'Number of characters to sample from beginning, middle, and end (default: 500)',
            'required': False,
            'default': 500,
            'type': 'int'
        },
        {
            'name': 'model',
            'description': 'Gemini model to use (default: auto-select from available models)',
            'required': False,
            'default': ''
        },
        {
            'name': 'custom_prompt',
            'description': 'Custom prompt to send to Gemini (default: uses internal prompt)',
            'required': False,
            'default': ''
        }
    ]
    
    examples = [
        {
            'command': 'qzx WonderContentGen "path/to/file.txt"',
            'description': 'Analyze and explain the content of file.txt using Gemini AI'
        },
        {
            'command': 'qzx WonderContentGen "path/to/file.txt" 1000',
            'description': 'Explain file content using 1000 characters from each section'
        },
        {
            'command': 'qzx WonderContentGen "path/to/file.txt" 500 "gemini-1.5-pro"',
            'description': 'Use a specific Gemini model for analysis'
        },
        {
            'command': 'qzx WonderContentGen "path/to/file.txt" 500 "" "What programming language is this?"',
            'description': 'Ask Gemini a specific question about the file content'
        }
    ]
    
    # Default models to try in order of preference
    DEFAULT_MODELS = [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-pro",
        "gemini-pro-latest"
    ]
    
    def execute(self, file_path, sample_size=500, model="", custom_prompt=""):
        """
        Analyze and explain file contents using Gemini AI
        
        Args:
            file_path (str): Path to the file to analyze
            sample_size (str): Number of characters to sample from beginning, middle, and end
            model (str): Gemini model to use (if empty, will auto-select)
            custom_prompt (str): Custom prompt to send to Gemini
            
        Returns:
            Dictionary with the operation result
        """
        try:
            if requests is None:
                return {
                    "success": False,
                    "error": "Missing optional dependency: requests",
                    "error_code": "missing_dependency",
                    "message": (
                        "generateContent requires the optional AI dependencies. "
                        "Install them explicitly with 'pip install qzx[ai]'."
                    ),
                    "details": {
                        "missing": ["requests"],
                        "remediation": "pip install qzx[ai]",
                    },
                }
                
            # Convert sample_size to integer
            try:
                sample_size = int(sample_size)
            except (TypeError, ValueError):
                sample_size = 500
                
            if sample_size < 10:
                sample_size = 500
                
            # Check if file exists
            if not os.path.isfile(file_path):
                return {
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "message": f"The file '{file_path}' does not exist or is not accessible."
                }
                
            # Get Gemini API key
            api_key = self._get_gemini_api_key()
            if not api_key:
                return {
                    "success": False,
                    "error": "Gemini API key not found",
                    "message": "GEMINI_API_TOKEN not found in environment variables or .env file. Please set it up to use this command."
                }
            
            # If user specified a model, try to use it directly
            selected_model = model
            
            # If no model was specified, get the list of available models
            # but only once instead of trying each default model
            if not selected_model:
                # Get all available models silently
                available_models = self._list_gemini_models(api_key)
                
                if not available_models:
                    return {
                        "success": False,
                        "error": "Failed to retrieve Gemini models",
                        "message": "Could not get a list of available Gemini models. Please check your API key and try again."
                    }
                
                # Try to use the default models in order of preference
                # without showing warnings for each one
                for default_model in self.DEFAULT_MODELS:
                    for model_info in available_models:
                        model_name = model_info.get('name', '').split('/')[-1]
                        if default_model == model_name:
                            selected_model = model_name
                            break
                    if selected_model:
                        break
                
                # If no default model is available, use the first one in the list
                if not selected_model and available_models:
                    selected_model = available_models[0].get('name', '').split('/')[-1]
            else:
                # Validate a requested model with the read-only models endpoint.
                # The previous implementation sent a generation request merely
                # to probe availability, which could consume quota.
                available_models = self._list_gemini_models(api_key)
                available_names = {
                    item.get("name", "").split("/")[-1]
                    for item in available_models
                }
                if selected_model not in available_names:
                    return {
                        "success": False,
                        "error": "Requested Gemini model is not available",
                        "error_code": "model_not_available",
                        "message": (
                            "Gemini model '{}' is not available for this API key."
                        ).format(selected_model),
                        "details": {
                            "requested_model": selected_model,
                            "available_models": sorted(available_names),
                        },
                    }
            
            if not selected_model:
                return {
                    "success": False,
                    "error": "No suitable model found",
                    "message": "Could not find a suitable Gemini model to use. Please specify a model name explicitly."
                }
            
            print(f"Using model: {selected_model}")
            
            print(f"Analyzing file: {file_path}")
            print(f"Extracting {sample_size} characters from beginning, middle, and end...")
                
            # Read file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    # Try with another encoding
                    with open(file_path, 'r', encoding='latin-1') as f:
                        content = f.read()
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Error reading file: {str(e)}",
                        "message": f"Could not read file '{file_path}'. It may be a binary file or use an unsupported encoding."
                    }
                    
            # Get file size and prepare samples
            file_size = len(content)
            if file_size <= sample_size * 3:
                # File is small enough to use entire content
                samples = content
                print("File is small, using entire content...")
            else:
                # Extract samples from beginning, middle, and end
                beginning = content[:sample_size]
                
                # Calculate middle position
                middle_start = (file_size // 2) - (sample_size // 2)
                middle = content[middle_start:middle_start + sample_size]
                
                # Extract end
                end = content[-sample_size:]
                
                # Combine samples
                samples = f"--- BEGINNING OF FILE ---\n{beginning}\n\n--- MIDDLE OF FILE ---\n{middle}\n\n--- END OF FILE ---\n{end}"
                
            print("Connecting to Gemini API...")
                
            # Prepare prompt
            if custom_prompt:
                prompt = custom_prompt
            else:
                prompt = """You are a helpful assistant that explains file contents. 
                
I am giving you samples from a file (beginning, middle, and end sections). 
Based on these samples, explain in plain English what this file contains.

Be direct and straightforward. For example: "This file contains mostly git bash commands and some developer notes" or "This file is a Python script that processes image data."

Focus on:
1. What type of content/data the file contains
2. What the file is used for (if apparent)
3. Any notable patterns or structures in the content

Avoid unnecessary technical details unless they're essential to understanding the file. Keep your explanation concise and informative.

Here are the samples:

"""
            
            # Call Gemini API
            response = self._call_gemini_api(api_key, selected_model, prompt + samples)
            
            if not response:
                return {
                    "success": False,
                    "error": "Failed to get response from Gemini API",
                    "message": "Could not get a valid response from Gemini API. Please try again later."
                }
                
            print("Content analysis generated successfully!")
                
            # Return the result
            return {
                "success": True,
                "message": (
                    "File content analysis generated successfully using {}. "
                    "A sample of {} characters per section was sent to Gemini."
                ).format(selected_model, sample_size),
                "explanation": response,
                "file_path": file_path,
                "file_size": file_size,
                "sample_size": sample_size,
                "model_used": selected_model,
                "external_service": {
                    "provider": "Google Gemini",
                    "content_shared": True,
                    "sampled_characters_per_section": sample_size,
                },
            }
            
        except Exception as e:
            error_message = f"Error analyzing file content: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to analyze file content: {str(e)}"
            }
    
    def _get_gemini_api_key(self):
        """Get Gemini API key from environment or .env file"""
        # First try from environment
        api_key = os.environ.get('GEMINI_API_TOKEN')
        
        # If not found, try loading from .env file
        if not api_key:
            # Try from current directory
            if load_dotenv is not None and os.path.isfile('.env'):
                load_dotenv('.env')
                api_key = os.environ.get('GEMINI_API_TOKEN')
            
            # Try from project root directory
            if not api_key:
                # Get project root (relative to the packaged command module)
                project_root = Path(__file__).resolve().parents[2]
                env_path = project_root / '.env'
                
                if load_dotenv is not None and env_path.is_file():
                    load_dotenv(env_path)
                    api_key = os.environ.get('GEMINI_API_TOKEN')
        
        return api_key
    
    def _list_gemini_models(self, api_key):
        """List available Gemini models"""
        try:
            # API URL for listing models
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            
            # Make API request
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            # Check if request was successful
            if response.status_code == 200:
                # Parse response JSON
                response_json = response.json()
                
                # Extract models
                try:
                    models = response_json.get('models', [])
                    # Filter for Gemini models
                    gemini_models = [m for m in models if 'gemini' in m.get('name', '').lower()]
                    return gemini_models
                except Exception as e:
                    print(f"Error parsing models response: {str(e)}")
                    return []
            else:
                print(f"Error listing models: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Error calling list models API: {str(e)}")
            return []
    
    def _call_gemini_api(self, api_key, model, prompt):
        """Call Gemini API to generate content"""
        try:
            # Gemini API URL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            
            # Prepare request payload
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.3,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 1024
                }
            }
            
            # Make API request
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            # Check if request was successful
            if response.status_code == 200:
                # Parse response JSON
                response_json = response.json()
                
                # Extract text from response
                try:
                    text = response_json['candidates'][0]['content']['parts'][0]['text']
                    return text
                except (KeyError, IndexError) as e:
                    print(f"Error parsing Gemini API response: {str(e)}")
                    return None
            else:
                print(f"Gemini API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error calling Gemini API: {str(e)}")
            return None

    def _is_model_available(self, api_key, model):
        """Check availability without issuing a generation request."""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
            
            # Make API request
            headers = {
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return False
            requested_name = model if model.startswith("models/") else f"models/{model}"
            return any(
                item.get("name") == requested_name
                for item in response.json().get("models", [])
            )
        except Exception:
            return False 
