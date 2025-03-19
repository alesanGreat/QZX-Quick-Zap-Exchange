#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCPULoad Command - Retrieves information about CPU usage
"""

import psutil
from Core.command_base import CommandBase

class GetCPULoadCommand(CommandBase):
    """
    Command to get CPU load information
    """
    
    name = "getCPULoad"
    description = "Gets information about current CPU usage"
    category = "system"
    
    parameters = [
        {
            'name': 'interval',
            'description': 'Time interval (in seconds) to calculate CPU usage',
            'required': False,
            'default': 1
        }
    ]
    
    examples = [
        {
            'command': 'qzx getCPULoad',
            'description': 'Get CPU usage information with 1-second interval'
        },
        {
            'command': 'qzx getCPULoad 0.5',
            'description': 'Get CPU usage information with 0.5-second interval'
        }
    ]
    
    def execute(self, interval=1):
        """
        Gets CPU load information
        
        Args:
            interval (float, optional): Time interval (in seconds) to calculate CPU usage.
                                       Defaults to 1 second.
            
        Returns:
            Dictionary with CPU load information
        """
        try:
            # Convert interval to float
            try:
                interval = float(interval)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Error: interval must be a number, got '{interval}'",
                    "message": f"Failed to get CPU information: interval must be a number, got '{interval}'"
                }
            
            # Get overall CPU usage
            cpu_percent = psutil.cpu_percent(interval=interval)
            
            # Get per-core usage (without additional delay)
            per_cpu_percent = psutil.cpu_percent(interval=0.0, percpu=True)
            
            # Prepare the output
            result = {
                "success": True,
                "overall_percent": cpu_percent,
                "per_core": []
            }
            
            # Add per-core information
            for i, percent in enumerate(per_cpu_percent):
                result["per_core"].append({
                    "core": i + 1,  # 1-based indexing for user readability
                    "percent": percent
                })
            
            result["cores_count"] = len(per_cpu_percent)
            
            # Try to get frequency information
            try:
                cpu_freq = psutil.cpu_freq(percpu=False)
                if cpu_freq:
                    freq_info = {}
                    if hasattr(cpu_freq, "current") and cpu_freq.current:
                        freq_info["current_mhz"] = cpu_freq.current
                    if hasattr(cpu_freq, "min") and cpu_freq.min:
                        freq_info["min_mhz"] = cpu_freq.min
                    if hasattr(cpu_freq, "max") and cpu_freq.max:
                        freq_info["max_mhz"] = cpu_freq.max
                    
                    if freq_info:
                        result["frequency"] = freq_info
                
                # Try to get per-core frequency
                try:
                    per_core_freq = psutil.cpu_freq(percpu=True)
                    if per_core_freq:
                        core_freqs = []
                        for i, freq in enumerate(per_core_freq):
                            if hasattr(freq, "current") and freq.current:
                                core_freqs.append({
                                    "core": i + 1,
                                    "current_mhz": freq.current
                                })
                        
                        if core_freqs:
                            result["per_core_frequency"] = core_freqs
                except:
                    pass  # Skip if per-core frequency is not available
            except:
                pass  # Skip if frequency information is not available
            
            # Get CPU load averages (on Unix systems)
            try:
                load_avg = psutil.getloadavg()
                result["load_average"] = {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                }
            except:
                pass  # Skip on Windows or if not available
            
            # Get CPU times
            try:
                cpu_times = psutil.cpu_times_percent()
                times_dict = {}
                
                # Convert named tuple to dictionary
                if hasattr(cpu_times, "user"):
                    times_dict["user"] = cpu_times.user
                if hasattr(cpu_times, "system"):
                    times_dict["system"] = cpu_times.system
                if hasattr(cpu_times, "idle"):
                    times_dict["idle"] = cpu_times.idle
                if hasattr(cpu_times, "nice") and hasattr(cpu_times, "nice") is not None:
                    times_dict["nice"] = cpu_times.nice
                if hasattr(cpu_times, "iowait") and hasattr(cpu_times, "iowait") is not None:
                    times_dict["iowait"] = cpu_times.iowait
                
                if times_dict:
                    result["times_percent"] = times_dict
            except:
                pass  # Skip if CPU times are not available
            
            # Create a detailed message with CPU information
            cores_text = f"{result['cores_count']} cores" if "cores_count" in result else "multiple cores"
            freq_text = ""
            if "frequency" in result and "current_mhz" in result["frequency"]:
                freq_text = f" running at {result['frequency']['current_mhz']:.0f} MHz"
            
            # Detailed verbose message
            result["message"] = (
                f"CPU usage: {cpu_percent:.1f}% overall across {cores_text}{freq_text}. "
                f"Measured over {interval} second{'' if interval == 1 else 's'}."
            )
            
            # If we have load averages, add them to the message
            if "load_average" in result:
                load_msg = (
                    f"Load averages: "
                    f"{result['load_average']['1min']:.2f} (1m), "
                    f"{result['load_average']['5min']:.2f} (5m), "
                    f"{result['load_average']['15min']:.2f} (15m)."
                )
                result["message"] += " " + load_msg
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting CPU load information: {str(e)}",
                "message": f"Failed to retrieve CPU information: {str(e)}"
            } 