#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
WonderIfAdmin Command - Checks if the current user has administrative privileges
"""

import os
import sys
import ctypes
import subprocess
import getpass
import platform
from Core.command_base import CommandBase

class WonderIfAdminCommand(CommandBase):
    """
    Command to check if the current user has administrative privileges
    """
    
    name = "wonderIfAdmin"
    description = "Checks if the current user has administrative privileges"
    category = "system"
    
    parameters = []
    
    examples = [
        {
            'command': 'qzx wonderIfAdmin',
            'description': 'Check if the current user has administrative privileges'
        }
    ]
    
    def execute(self):
        """
        Checks if the current user has administrative privileges
        
        Returns:
            Dictionary with administrative privilege information and status
        """
        try:
            result = {
                "is_admin": False,
                "os_type": platform.system(),
                "details": {},
                "success": True
            }
            
            os_type = platform.system().lower()
            
            # Check for administrative rights differently depending on OS
            if os_type == "windows":
                try:
                    # The most reliable way to check admin on Windows
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                    result["is_admin"] = is_admin
                    
                    # Add more details about the privileges
                    if is_admin:
                        result["details"]["status"] = "full_admin"
                        result["details"]["description"] = "User has full administrative rights"
                    else:
                        # Try to check if the user is in administrators group
                        try:
                            # Check if user is in admin group
                            admin_check = subprocess.run(
                                ["net", "localgroup", "administrators"], 
                                capture_output=True, 
                                text=True,
                                check=False
                            )
                            
                            current_user = getpass.getuser()
                            if current_user.lower() in admin_check.stdout.lower():
                                result["details"]["status"] = "admin_group_no_elevation"
                                result["details"]["description"] = "User is a member of administrators group but not running with elevated privileges"
                                result["details"]["tip"] = "Try running as administrator to gain full privileges"
                            else:
                                result["details"]["status"] = "not_admin"
                                result["details"]["description"] = "User is not a member of administrators group"
                        except:
                            result["details"]["status"] = "unknown_group_membership"
                            result["details"]["description"] = "Unable to determine administrators group membership"
                except Exception as e:
                    result["details"]["error"] = str(e)
                    
                    # Fallback method
                    try:
                        # Try using 'net session' which requires admin privileges
                        process = subprocess.run(
                            ["net", "session"], 
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        is_admin = process.returncode == 0
                        result["is_admin"] = is_admin
                        result["details"]["method"] = "fallback"
                    except:
                        result["details"]["status"] = "check_failed"
                        result["details"]["description"] = "Unable to determine administrative status"
            
            elif os_type == "linux":
                try:
                    # First check if running as root (UID 0)
                    uid = os.getuid()
                    is_root = uid == 0
                    result["is_admin"] = is_root
                    result["details"]["uid"] = uid
                    
                    if is_root:
                        result["details"]["status"] = "root"
                        result["details"]["description"] = "User has full root permissions"
                    else:
                        # Check sudo capabilities
                        try:
                            sudo_test = subprocess.run(
                                ["sudo", "-n", "true"], 
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            has_sudo_nopass = sudo_test.returncode == 0
                            result["details"]["has_passwordless_sudo"] = has_sudo_nopass
                            
                            # Check if user is in sudo group
                            groups_output = subprocess.run(
                                ["groups"], 
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            groups = groups_output.stdout.strip().split()
                            admin_groups = ["sudo", "wheel", "admin"]
                            admin_group_membership = [g for g in groups if g in admin_groups]
                            
                            if admin_group_membership:
                                result["details"]["admin_groups"] = admin_group_membership
                                result["details"]["status"] = "admin_group_member"
                                result["details"]["description"] = f"Member of admin groups: {', '.join(admin_group_membership)}"
                                result["is_admin"] = True  # Consider as admin if in admin groups
                            else:
                                result["details"]["status"] = "not_admin"
                                result["details"]["description"] = "Not a member of any known admin groups"
                        except:
                            result["details"]["status"] = "check_failed"
                            result["details"]["description"] = "Unable to determine sudo capabilities"
                except Exception as e:
                    result["details"]["error"] = str(e)
            
            elif os_type == "darwin":  # macOS
                try:
                    # Check if user is in admin group
                    groups_output = subprocess.run(
                        ["groups"], 
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    groups = groups_output.stdout.strip().split()
                    is_admin = "admin" in groups
                    result["is_admin"] = is_admin
                    
                    if is_admin:
                        result["details"]["status"] = "admin_group_member"
                        result["details"]["description"] = "User is a member of admin group"
                    else:
                        result["details"]["status"] = "not_admin"
                        result["details"]["description"] = "User is not a member of admin group"
                    
                    # Check if can execute sudo without password
                    try:
                        sudo_test = subprocess.run(
                            ["sudo", "-n", "true"], 
                            capture_output=True,
                            text=True,
                            check=False
                        )
                        has_sudo_nopass = sudo_test.returncode == 0
                        result["details"]["has_passwordless_sudo"] = has_sudo_nopass
                    except:
                        result["details"]["sudo_check"] = "failed"
                except Exception as e:
                    result["details"]["error"] = str(e)
            
            else:
                result["details"]["status"] = "unsupported_os"
                result["details"]["description"] = f"Admin check not implemented for OS: {os_type}"
            
            # Create a user-friendly message summarizing the admin status
            username = getpass.getuser()
            
            # Base message with username and admin status
            if result["is_admin"]:
                status_msg = "has administrative privileges"
                action_tip = ""
                
                # Add specific details based on OS and admin type
                if os_type == "windows":
                    if result["details"].get("status") == "full_admin":
                        status_msg = "has full administrative privileges (elevated)"
                elif os_type == "linux":
                    if result["details"].get("status") == "root":
                        status_msg = "is running as root (UID 0)"
                    elif result["details"].get("status") == "admin_group_member":
                        admin_groups = result["details"].get("admin_groups", [])
                        group_str = ", ".join(admin_groups)
                        status_msg = f"has administrative capabilities (member of {group_str})"
                        
                        if result["details"].get("has_passwordless_sudo"):
                            status_msg += " with passwordless sudo access"
                        else:
                            status_msg += " requiring password for sudo"
                elif os_type == "darwin":  # macOS
                    status_msg = "has administrative rights (member of admin group)"
                    if result["details"].get("has_passwordless_sudo"):
                        status_msg += " with passwordless sudo access"
            else:
                status_msg = "does not have administrative privileges"
                
                # Add OS-specific details for non-admin users
                if os_type == "windows":
                    if result["details"].get("status") == "admin_group_no_elevation":
                        status_msg = "is a member of the administrators group but is not running with elevated privileges"
                        action_tip = " Run as administrator to gain full administrative access."
                
                # Generic action tip for non-admin users
                if not action_tip:
                    action_tip = " Administrative operations will require elevation or administrator credentials."
            
            # Combine all parts into a final message
            message = f"User '{username}' {status_msg} on {result['os_type']}.{action_tip}"
            result["message"] = message
            
            return result
        except Exception as e:
            error_message = f"Error checking administrative privileges: {str(e)}"
            return {
                "success": False,
                "error": error_message,
                "message": f"Failed to determine administrative status: {str(e)}",
                "is_admin": False
            } 