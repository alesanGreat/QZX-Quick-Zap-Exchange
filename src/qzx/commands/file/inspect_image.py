#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
InspectImage Command - Inspects image dimensions and format natively using binary header parsing (no PIL/OpenCV needed).
"""

from qzx.commands.file._image_header_parser import parse_image, parse_jpeg
from qzx.commands.file._image_inspection import execute_inspect_image
from qzx.core.command_base import CommandBase

class InspectImageCommand(CommandBase):
    """
    Command to inspect image metadata (format, width, height, size) using native header parsing.
    """
    
    name = "inspectImage"
    description = "Inspects image dimensions, format, and size natively from headers (supports PNG, JPEG, GIF, BMP)"
    category = "file"
    _byte_units = ("B", "KB", "MB")
    
    parameters = [
        {
            'name': 'image_path',
            'description': 'Path to the image file to inspect',
            'required': True
        }
    ]
    
    examples = [
        {
            'command': 'qzx inspectImage image.png',
            'description': 'Inspect dimensions and format of image.png'
        }
    ]
    
    def execute(self, image_path):
        """Inspect one image using native binary headers."""
        return execute_inspect_image(self, image_path)

    def _parse_image(self, filepath):
        """Dispatch binary parsing based on the image signature."""
        return parse_image(filepath)

    def _parse_jpeg(self, handle):
        """Scan JPEG markers to locate Start Of Frame details."""
        return parse_jpeg(handle)
