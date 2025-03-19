#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderToday Command - Displays detailed date and time information
"""

import datetime
import time
import calendar
import locale
import os
import sys
from Core.command_base import CommandBase

class WonderTodayCommand(CommandBase):
    """
    Command to display detailed date and time information
    """
    
    name = "WonderToday"
    aliases = ["today", "now", "datetime", "fecha"]
    description = "Displays detailed information about the current date and time"
    category = "system"
    
    parameters = [
        {
            'name': 'format',
            'description': 'Output format (full, simple, or iso)',
            'required': False,
            'default': 'full'
        }
    ]
    
    examples = [
        {
            'command': 'qzx WonderToday',
            'description': 'Display full date and time information'
        },
        {
            'command': 'qzx WonderToday simple',
            'description': 'Display date and time in a simple format'
        },
        {
            'command': 'qzx WonderToday iso',
            'description': 'Display date and time in ISO format'
        }
    ]
    
    def execute(self, format="full"):
        """
        Display detailed date and time information
        
        Args:
            format (str): Output format (full, simple, or iso)
            
        Returns:
            Dictionary with the operation result
        """
        try:
            # Get current date and time
            now = datetime.datetime.now()
            
            # Get timezone information
            timezone_name = time.tzname[time.localtime().tm_isdst]
            timezone_offset = time.strftime("%z")
            
            # Get week information
            day_of_week = now.strftime("%A")
            week_of_year = now.isocalendar()[1]
            
            # Get calendar for current month
            cal = calendar.month(now.year, now.month)
            
            # Format output based on requested format
            if format.lower() == "simple":
                formatted_output = f"{now.strftime('%A, %B %d, %Y')} {now.strftime('%I:%M:%S %p')} {timezone_name}"
                message = f"Current date and time: {formatted_output}"
            elif format.lower() == "iso":
                formatted_output = now.isoformat()
                message = f"Current date and time (ISO): {formatted_output}"
            else:  # Full format
                # Create a decorated box for the output
                border = "=" * 60
                formatted_output = f"""
{border}
📅  DATE & TIME INFORMATION
{border}

📆  Date: {now.strftime('%A, %B %d, %Y')}
🕒  Time: {now.strftime('%I:%M:%S %p')} ({now.strftime('%H:%M:%S')} 24h)
⏰  Timezone: {timezone_name} (UTC{timezone_offset})

📊  Additional Information:
   • Day of year: {now.timetuple().tm_yday} of {366 if calendar.isleap(now.year) else 365}
   • Week: {week_of_year} of {datetime.date(now.year, 12, 28).isocalendar()[1]}
   • Month: {now.month} of 12
   • Quarter: {(now.month - 1) // 3 + 1} of 4
   • Unix timestamp: {int(time.time())}

📅  Calendar for {now.strftime('%B %Y')}:
{cal}
{border}
"""
                message = "Detailed date and time information displayed successfully."
            
            # Return the result
            if hasattr(self, 'in_terminal') and self.in_terminal:
                return {
                    "success": True,
                    "message": message,
                    "output": formatted_output
                }
            
            # Otherwise, print the message directly
            print(formatted_output)
            
            # Return a structured result
            return {
                "success": True,
                "message": message,
                "date": {
                    "year": now.year,
                    "month": now.month,
                    "month_name": now.strftime("%B"),
                    "day": now.day,
                    "day_of_week": day_of_week,
                    "day_of_year": now.timetuple().tm_yday,
                    "week_of_year": week_of_year,
                    "quarter": (now.month - 1) // 3 + 1,
                    "is_leap_year": calendar.isleap(now.year)
                },
                "time": {
                    "hour": now.hour,
                    "hour_12": int(now.strftime("%I")),
                    "minute": now.minute,
                    "second": now.second,
                    "microsecond": now.microsecond,
                    "am_pm": now.strftime("%p"),
                    "timezone": timezone_name,
                    "timezone_offset": timezone_offset
                },
                "timestamp": int(time.time()),
                "iso_format": now.isoformat()
            }
            
        except Exception as e:
            error_message = f"Error displaying date and time information: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to display date and time information: {str(e)}"
            } 