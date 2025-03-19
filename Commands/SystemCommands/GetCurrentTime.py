#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCurrentTime Command - Retrieves the current time in HH-MM-SS-milliseconds format
"""

import datetime
import time
from Core.command_base import CommandBase

class GetCurrentTimeCommand(CommandBase):
    """
    Command to get the current time in HH-MM-SS-milliseconds format
    """
    
    name = "getCurrentTime"
    description = "Gets the current time in HH-MM-SS-milliseconds format"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getCurrentTime',
            'description': 'Get the current time with millisecond precision'
        }
    ]
    
    def execute(self):
        """
        Gets the current time in HH-MM-SS-milliseconds format
        
        Returns:
            Dictionary with the current time information
        """
        try:
            now = datetime.datetime.now()
            formatted_time = now.strftime("%H-%M-%S-%f")[:-3]  # Truncate to milliseconds
            
            # Get additional time information for verbose output
            hour = now.hour
            minute = now.minute
            second = now.second
            millisecond = int(now.microsecond / 1000)
            timestamp = time.time()
            
            # Format for more readable display
            readable_time = now.strftime("%I:%M:%S %p")  # 12-hour format with AM/PM
            
            # Create detailed result with verbose information
            result = {
                "success": True,
                "time": formatted_time,
                "message": f"Current time is {readable_time} ({hour:02d}:{minute:02d}:{second:02d}.{millisecond:03d})",
                "details": {
                    "hour": hour,
                    "minute": minute,
                    "second": second,
                    "millisecond": millisecond,
                    "unix_timestamp": timestamp,
                    "hour_12": int(now.strftime("%I")),
                    "am_pm": now.strftime("%p")
                }
            }
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting current time: {str(e)}",
                "message": f"Failed to retrieve the current time: {str(e)}"
            } 