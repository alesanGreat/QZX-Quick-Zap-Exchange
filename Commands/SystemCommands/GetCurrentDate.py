#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GetCurrentDate Command - Retrieves the current date in YYYY-MM-DD format
"""

import datetime
from Core.command_base import CommandBase

class GetCurrentDateCommand(CommandBase):
    """
    Command to get the current date in YYYY-MM-DD format
    """
    
    name = "getCurrentDate"
    description = "Gets the current date in YYYY-MM-DD format"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx getCurrentDate',
            'description': 'Get the current date in the format YYYY-MM-DD'
        }
    ]
    
    def execute(self):
        """
        Gets the current date in YYYY-MM-DD format
        
        Returns:
            Dictionary with the current date information
        """
        try:
            today = datetime.datetime.now()
            formatted_date = today.strftime("%Y-%m-%d")
            
            # Get additional date information for verbose output
            year = today.year
            month = today.month
            month_name = today.strftime("%B")
            day = today.day
            day_of_week = today.strftime("%A")
            day_of_year = today.timetuple().tm_yday
            week_of_year = today.isocalendar()[1]
            
            # Create detailed result with verbose information
            result = {
                "success": True,
                "date": formatted_date,
                "message": f"Current date is {day_of_week}, {month_name} {day}, {year} (ISO format: {formatted_date})",
                "details": {
                    "year": year,
                    "month": month,
                    "month_name": month_name,
                    "day": day,
                    "day_of_week": day_of_week,
                    "day_of_year": day_of_year,
                    "week_of_year": week_of_year
                }
            }
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": f"Error getting current date: {str(e)}",
                "message": f"Failed to retrieve the current date: {str(e)}"
            } 