#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetGPULoad Command - Displays information about GPUs in the system
"""

import os
import sys
import platform
import subprocess
from Core.command_base import CommandBase

class GetGPULoadCommand(CommandBase):
    """
    Command to get information about GPUs in the system
    """
    
    name = "GetGPULoad"
    aliases = ["gpuload", "gpuinfo", "gpustatus"]
    description = "Displays information about GPUs in the system"
    category = "system"
    
    parameters = [
        {
            'name': 'detailed',
            'description': 'Show detailed information (true/false)',
            'required': False,
            'default': 'false'
        }
    ]
    
    examples = [
        {
            'command': 'qzx GetGPULoad',
            'description': 'Display basic information about the GPUs'
        },
        {
            'command': 'qzx GetGPULoad true',
            'description': 'Display detailed information about the GPUs'
        }
    ]
    
    def execute(self, detailed="false"):
        """
        Retrieves information about the GPUs in the system
        
        Args:
            detailed (str): Whether to show detailed information (true/false)
            
        Returns:
            Dictionary with GPU information and status
        """
        try:
            # Convert detailed parameter to boolean
            if isinstance(detailed, str):
                detailed = detailed.lower() in ('true', 'yes', 'y', '1', 't')
            
            result = {
                "success": True,
                "gpus": []
            }
            
            # Check for NVIDIA GPUs with nvidia-smi
            nvidia_gpus = self._get_nvidia_gpus(detailed)
            if nvidia_gpus:
                result["nvidia_gpus"] = nvidia_gpus
                result["gpus"].extend(nvidia_gpus)
            
            # Check for AMD GPUs
            amd_gpus = self._get_amd_gpus(detailed)
            if amd_gpus:
                result["amd_gpus"] = amd_gpus
                result["gpus"].extend(amd_gpus)
            
            # Check for Intel GPUs
            intel_gpus = self._get_intel_gpus(detailed)
            if intel_gpus:
                result["intel_gpus"] = intel_gpus
                result["gpus"].extend(intel_gpus)
            
            # If we couldn't detect any GPUs with specific methods,
            # try to get generic information
            if not result["gpus"]:
                generic_info = self._get_generic_gpu_info()
                if generic_info:
                    result["generic_gpu_info"] = generic_info
            
            # Add summary information
            result["gpu_count"] = len(result["gpus"])
            result["detected_vendors"] = []
            if nvidia_gpus:
                result["detected_vendors"].append("NVIDIA")
            if amd_gpus:
                result["detected_vendors"].append("AMD")
            if intel_gpus:
                result["detected_vendors"].append("Intel")
                
            # Create a detailed message for verbose output
            if result["gpu_count"] > 0:
                # Prepare summary of found GPUs
                vendors_str = ", ".join(result["detected_vendors"])
                detail_level = "detailed" if detailed else "basic"
                
                # Create primary message with count and vendors
                message = f"Found {result['gpu_count']} GPU{'' if result['gpu_count'] == 1 else 's'} "
                message += f"from {vendors_str}. Showing {detail_level} information."
                
                # Add information about each GPU
                gpu_details = []
                for idx, gpu in enumerate(result["gpus"]):
                    gpu_name = gpu.get("name", "Unknown GPU")
                    gpu_vendor = gpu.get("vendor", "Unknown vendor")
                    
                    gpu_info = f"GPU {idx+1}: {gpu_name} ({gpu_vendor})"
                    
                    # Add memory info if available
                    if "memory" in gpu and "total" in gpu["memory"]:
                        if isinstance(gpu["memory"]["total"], str) and "MiB" in gpu["memory"]["total"]:
                            gpu_info += f", {gpu['memory']['total']} VRAM"
                        elif "total_readable" in gpu["memory"]:
                            gpu_info += f", {gpu['memory']['total_readable']} VRAM"
                    
                    # Add utilization if available
                    if "utilization" in gpu:
                        gpu_info += f", {gpu['utilization']} utilization"
                    
                    # Add temperature if available
                    if "temperature" in gpu:
                        gpu_info += f", {gpu['temperature']}"
                    
                    gpu_details.append(gpu_info)
                
                if gpu_details:
                    result["gpu_summary"] = gpu_details
            else:
                message = "No GPUs detected on this system."
                
                # Check for generic info
                if "generic_gpu_info" in result:
                    message += " Some generic graphics information was found but could not be parsed properly."
            
            # Add the message to the result
            result["message"] = message
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting GPU information: {str(e)}",
                "message": f"Failed to retrieve GPU information: {str(e)}"
            }
    
    def _get_nvidia_gpus(self, detailed=False):
        """Get information about NVIDIA GPUs using nvidia-smi"""
        try:
            # Check if nvidia-smi is available
            if self._command_exists("nvidia-smi"):
                # Basic GPU info
                if detailed:
                    # Get detailed information in JSON format if available
                    try:
                        nvidia_smi = subprocess.run(
                            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu", "--format=csv,noheader"],
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        
                        # Process the CSV output
                        gpus = []
                        lines = nvidia_smi.stdout.strip().split('\n')
                        for i, line in enumerate(lines):
                            if line.strip():
                                parts = line.split(',')
                                if len(parts) >= 7:
                                    gpu = {
                                        "index": i,
                                        "name": parts[0].strip(),
                                        "vendor": "NVIDIA",
                                        "driver_version": parts[1].strip(),
                                        "memory": {
                                            "total": parts[2].strip(),
                                            "used": parts[3].strip(),
                                            "free": parts[4].strip()
                                        },
                                        "utilization": parts[5].strip(),
                                        "temperature": parts[6].strip()
                                    }
                                    gpus.append(gpu)
                        
                        return gpus
                    except Exception as e:
                        # Fallback to basic info
                        print(f"Error getting detailed NVIDIA GPU info: {e}")
                        pass
                
                # Basic info fallback
                nvidia_smi = subprocess.run(
                    ["nvidia-smi", "-L"],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                # Process the output
                gpus = []
                lines = nvidia_smi.stdout.strip().split('\n')
                for i, line in enumerate(lines):
                    if line.startswith("GPU "):
                        # Format: "GPU 0: NVIDIA GeForce RTX 3080 (UUID: ...)"
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            gpu_info = parts[1].strip()
                            gpu_name = gpu_info.split("(")[0].strip()
                            gpu = {
                                "index": i,
                                "name": gpu_name,
                                "vendor": "NVIDIA"
                            }
                            gpus.append(gpu)
                
                return gpus
        except Exception as e:
            print(f"Error checking for NVIDIA GPUs: {e}")
        
        return []
    
    def _get_amd_gpus(self, detailed=False):
        """Get information about AMD GPUs"""
        gpus = []
        system = platform.system().lower()
        
        try:
            if system == "linux":
                # On Linux, check /sys/class/drm for AMD GPUs
                drm_path = "/sys/class/drm"
                if os.path.exists(drm_path):
                    for card in os.listdir(drm_path):
                        if card.startswith("card") and "amdgpu" in card:
                            card_path = os.path.join(drm_path, card)
                            gpu = {"vendor": "AMD", "name": card}
                            
                            # Try to get more info if available
                            try:
                                device_path = os.path.join(card_path, "device")
                                if os.path.exists(os.path.join(device_path, "vendor_id")):
                                    with open(os.path.join(device_path, "vendor_id"), 'r') as f:
                                        gpu["vendor_id"] = f.read().strip()
                                
                                if os.path.exists(os.path.join(device_path, "device_id")):
                                    with open(os.path.join(device_path, "device_id"), 'r') as f:
                                        gpu["device_id"] = f.read().strip()
                                
                                # Try to get product name
                                if os.path.exists(os.path.join(device_path, "product_name")):
                                    with open(os.path.join(device_path, "product_name"), 'r') as f:
                                        gpu["name"] = f.read().strip()
                            except:
                                pass
                            
                            gpus.append(gpu)
            elif system == "windows":
                # On Windows, try using PowerShell to get GPU info
                try:
                    ps_command = "Get-WmiObject win32_VideoController | Where-Object { $_.Name -like '*Radeon*' -or $_.Name -like '*AMD*' } | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"
                    ps_output = subprocess.run(
                        ["powershell", "-Command", ps_command],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    # Try to parse JSON output
                    if ps_output.stdout.strip():
                        import json
                        try:
                            gpu_data = json.loads(ps_output.stdout)
                            # Handle both single object and array results
                            if isinstance(gpu_data, dict):
                                gpu_data = [gpu_data]
                            
                            for i, gpu in enumerate(gpu_data):
                                gpu_info = {
                                    "index": i,
                                    "name": gpu.get("Name", "AMD GPU"),
                                    "vendor": "AMD"
                                }
                                
                                # Add additional information if available
                                if "AdapterRAM" in gpu:
                                    ram_bytes = int(gpu["AdapterRAM"])
                                    gpu_info["memory"] = {
                                        "total": ram_bytes,
                                        "total_readable": self._format_bytes(ram_bytes)
                                    }
                                
                                if "DriverVersion" in gpu:
                                    gpu_info["driver_version"] = gpu["DriverVersion"]
                                
                                gpus.append(gpu_info)
                        except:
                            pass
                except:
                    pass
        except Exception as e:
            print(f"Error checking for AMD GPUs: {e}")
        
        return gpus
    
    def _get_intel_gpus(self, detailed=False):
        """Get information about Intel GPUs"""
        gpus = []
        system = platform.system().lower()
        
        try:
            if system == "windows":
                # On Windows, try using PowerShell to get GPU info
                try:
                    ps_command = "Get-WmiObject win32_VideoController | Where-Object { $_.Name -like '*Intel*' -and $_.Name -notlike '*Intel(R) UHD Graphics*' } | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"
                    ps_output = subprocess.run(
                        ["powershell", "-Command", ps_command],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    # Try to parse JSON output
                    if ps_output.stdout.strip():
                        import json
                        try:
                            gpu_data = json.loads(ps_output.stdout)
                            # Handle both single object and array results
                            if isinstance(gpu_data, dict):
                                gpu_data = [gpu_data]
                            
                            for i, gpu in enumerate(gpu_data):
                                gpu_info = {
                                    "index": i,
                                    "name": gpu.get("Name", "Intel GPU"),
                                    "vendor": "Intel"
                                }
                                
                                # Add additional information if available
                                if "AdapterRAM" in gpu:
                                    ram_bytes = int(gpu["AdapterRAM"])
                                    gpu_info["memory"] = {
                                        "total": ram_bytes,
                                        "total_readable": self._format_bytes(ram_bytes)
                                    }
                                
                                if "DriverVersion" in gpu:
                                    gpu_info["driver_version"] = gpu["DriverVersion"]
                                
                                gpus.append(gpu_info)
                        except:
                            pass
                except:
                    pass
        except Exception as e:
            print(f"Error checking for Intel GPUs: {e}")
        
        return gpus
    
    def _get_generic_gpu_info(self):
        """Get generic GPU information using platform-specific methods"""
        system = platform.system().lower()
        
        if system == "windows":
            try:
                # Use WMI to get all video controllers
                ps_command = "Get-WmiObject win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json"
                ps_output = subprocess.run(
                    ["powershell", "-Command", ps_command],
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if ps_output.stdout.strip():
                    return ps_output.stdout.strip()
            except:
                pass
        elif system == "linux":
            try:
                # Use lspci to get GPU information
                lspci_output = subprocess.run(
                    ["lspci", "-vnn", "|", "grep", "-i", "VGA"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    check=False
                )
                
                if lspci_output.stdout.strip():
                    return lspci_output.stdout.strip()
            except:
                pass
        
        return None
    
    def _command_exists(self, cmd):
        """Check if a command exists in the system"""
        if platform.system().lower() == "windows":
            cmd_path = subprocess.run(
                ["where", cmd],
                capture_output=True,
                text=True,
                check=False
            )
            return cmd_path.returncode == 0
        else:
            return subprocess.run(
                ["which", cmd],
                capture_output=True,
                text=True,
                check=False
            ).returncode == 0
    
    def _format_bytes(self, bytes_val):
        """Format bytes value to human-readable string"""
        try:
            bytes_val = float(bytes_val)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.2f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.2f} PB"
        except:
            return str(bytes_val) 