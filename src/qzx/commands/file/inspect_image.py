#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
InspectImage Command - Inspects image dimensions and format natively using binary header parsing (no PIL/OpenCV needed).
"""

import os
import sys
import struct
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qzx.core.command_base import CommandBase

class InspectImageCommand(CommandBase):
    """
    Command to inspect image metadata (format, width, height, size) using native header parsing.
    """
    
    name = "inspectImage"
    description = "Inspects image dimensions, format, and size natively from headers (supports PNG, JPEG, GIF, BMP)"
    category = "file"
    
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
        """
        Inspects an image file
        
        Args:
            image_path (str): File path
            
        Returns:
            Dictionary containing image metadata
        """
        image_path = image_path.strip()
        if not image_path:
            return {
                "success": False,
                "error": "The image_path parameter is required.",
                "message": "Image path is required."
            }
            
        abs_path = os.path.abspath(image_path)
        
        if not os.path.exists(abs_path):
            return {
                "success": False,
                "error": f"Image file '{image_path}' does not exist.",
                "message": f"Image file '{image_path}' does not exist."
            }
            
        if not os.path.isfile(abs_path):
            return {
                "success": False,
                "error": f"'{image_path}' is not a file.",
                "message": f"'{image_path}' is not a file."
            }
            
        try:
            file_size = os.path.getsize(abs_path)
            meta = self._parse_image(abs_path)
            
            if not meta:
                return {
                    "success": False,
                    "error": "Unsupported image format or corrupt header.",
                    "message": "Could not identify image format or extract dimensions from header."
                }
                
            readable_size = self._format_bytes(file_size)
            
            msg = f"Image Diagnostics for '{abs_path}':\n"
            msg += f"- Format: {meta['format']}\n"
            msg += f"- Dimensions: {meta['width']} x {meta['height']} px\n"
            msg += f"- File Size: {readable_size} ({file_size} bytes)\n"
            if "depth" in meta:
                msg += f"- Color Depth: {meta['depth']} bits"
                
            return {
                "success": True,
                "file_path": abs_path,
                "format": meta["format"],
                "width": meta["width"],
                "height": meta["height"],
                "color_depth": meta.get("depth"),
                "file_bytes": file_size,
                "file_size_readable": readable_size,
                "message": msg
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to inspect image header: {str(e)}"
            }
            
    def _parse_image(self, filepath):
        """Dispatches binary parsing based on header signature"""
        try:
            with open(filepath, "rb") as f:
                head = f.read(32)
                if len(head) < 10:
                    return None
                    
                # 1. PNG Signature
                if head.startswith(b"\x89PNG\r\n\x1a\n"):
                    # Width and height are 4-byte integers in IHDR starting at offset 16
                    width, height = struct.unpack(">II", head[16:24])
                    depth = int(head[24])
                    return {"width": width, "height": height, "format": "PNG", "depth": depth}
                    
                # 2. GIF Signature
                elif head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
                    # Width and height are 2-byte little-endian integers at offset 6
                    width, height = struct.unpack("<HH", head[6:10])
                    return {"width": width, "height": height, "format": "GIF", "depth": 8}
                    
                # 3. BMP Signature
                elif head.startswith(b"BM"):
                    # Width and height are 4-byte little-endian integers at offset 18
                    width, height = struct.unpack("<ii", head[18:26])
                    # Height can be negative in BMP, take absolute value
                    height = abs(height)
                    depth = struct.unpack("<H", head[28:30])[0]
                    return {"width": width, "height": height, "format": "BMP", "depth": depth}
                    
                # 4. JPEG Signature
                elif head.startswith(b"\xff\xd8"):
                    # Reset to start of file to scan markers
                    f.seek(0)
                    return self._parse_jpeg(f)
        except Exception:
            pass
        return None
        
    def _parse_jpeg(self, f):
        """Scans JPEG binary markers to find SOF details"""
        try:
            soi = f.read(2)
            if soi != b"\xff\xd8":
                return None
                
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    break
                    
                # Verify marker prefix
                if marker[0] != 0xff:
                    # Sync issue, find next 0xff
                    while len(marker) > 0 and marker[0] != 0xff:
                        marker = f.read(1)
                    if len(marker) == 0:
                        break
                    marker = b"\xff" + f.read(1)
                    if len(marker) < 2:
                        break
                        
                marker_type = marker[1]
                
                # Exclude markers without sizes
                if marker_type == 0xd9:  # EOI (End of Image)
                    break
                if marker_type in (0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8):  # RST / SOI
                    continue
                    
                # Read chunk length
                len_bytes = f.read(2)
                if len(len_bytes) < 2:
                    break
                length = struct.unpack(">H", len_bytes)[0]
                
                # Check for Start of Frame (SOF) marker
                # SOF0 (0xc0) to SOF15 (0xcf) except SOF4, SOF8, SOF12
                if marker_type in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                    precision = f.read(1)
                    height_bytes = f.read(2)
                    width_bytes = f.read(2)
                    components_bytes = f.read(1)
                    
                    if len(precision) < 1 or len(height_bytes) < 2 or len(width_bytes) < 2 or len(components_bytes) < 1:
                        break
                        
                    height = struct.unpack(">H", height_bytes)[0]
                    width = struct.unpack(">H", width_bytes)[0]
                    components = int(components_bytes[0])
                    return {
                        "width": width,
                        "height": height,
                        "format": "JPEG",
                        "depth": int(precision[0]) * components
                    }
                    
                # Skip the rest of the marker segment
                if length >= 2:
                    f.seek(length - 2, os.SEEK_CUR)
                else:
                    break
        except Exception:
            pass
        return None
        
    def _format_bytes(self, size):
        for unit in ['B', 'KB', 'MB']:
            if size < 1024.0 or unit == 'MB':
                break
            size /= 1024.0
        return f"{size:.2f} {unit}"
