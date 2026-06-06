#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tests for the InspectImage command
"""

import os
from qzx.commands.file.inspect_image import InspectImageCommand

class TestInspectImageCommand:
    """
    Tests for the InspectImage command
    """
    
    def setup_method(self):
        """Setup for each test"""
        self.command = InspectImageCommand()
        
    def test_missing_image_path(self):
        """Test calling with missing path parameter"""
        result = self.command.execute("")
        assert result["success"] is False
        assert "required" in result["error"]
        
    def test_nonexistent_image(self):
        """Test with nonexistent file path"""
        result = self.command.execute("non_existent_image_123.png")
        assert result["success"] is False
        assert "does not exist" in result["error"]
        
    def test_parse_png_headers(self, tmp_path):
        """Test parsing valid PNG headers mock"""
        png_path = tmp_path / "mock.png"
        
        # Construct raw PNG header:
        # 8 bytes signature: \x89PNG\r\n\x1a\n
        # 8 bytes chunk metadata (IHDR chunk size + IHDR chunk type)
        # 4 bytes width: 100 px -> \x00\x00\x00\x64
        # 4 bytes height: 200 px -> \x00\x00\x00\xc8
        # 1 byte bit depth: 8 -> \x08
        png_data = (
            b"\x89PNG\r\n\x1a\n" +
            b"\x00\x00\x00\x0dIHDR" +
            b"\x00\x00\x00\x64" +
            b"\x00\x00\x00\xc8" +
            b"\x08\x02\x00\x00\x00"
        )
        png_path.write_bytes(png_data)
        
        result = self.command.execute(str(png_path))
        
        assert result["success"] is True
        assert result["format"] == "PNG"
        assert result["width"] == 100
        assert result["height"] == 200
        assert result["color_depth"] == 8
        assert "100 x 200" in result["message"]
        
    def test_parse_gif_headers(self, tmp_path):
        """Test parsing valid GIF headers mock"""
        gif_path = tmp_path / "mock.gif"
        
        # Construct raw GIF89a header:
        # 6 bytes signature: GIF89a
        # 2 bytes width (little-endian): 100 px -> \x64\x00
        # 2 bytes height (little-endian): 200 px -> \xc8\x00
        gif_data = b"GIF89a\x64\x00\xc8\x00\x80\x00\x00"
        gif_path.write_bytes(gif_data)
        
        result = self.command.execute(str(gif_path))
        
        assert result["success"] is True
        assert result["format"] == "GIF"
        assert result["width"] == 100
        assert result["height"] == 200
        
    def test_parse_bmp_headers(self, tmp_path):
        """Test parsing valid BMP headers mock"""
        bmp_path = tmp_path / "mock.bmp"
        
        # Construct raw BMP header:
        # 2 bytes signature: BM
        # 16 bytes metadata (file size, reserved, offset)
        # 4 bytes width (little-endian): 100 px -> \x64\x00\x00\x00
        # 4 bytes height (little-endian): 200 px -> \xc8\x00\x00\x00
        # 2 bytes planes: \x01\x00
        # 2 bytes depth (bits-per-pixel): 24 -> \x18\x00
        bmp_data = (
            b"BM" +
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x36\x00\x00\x00\x28\x00\x00\x00" +
            b"\x64\x00\x00\x00" +
            b"\xc8\x00\x00\x00" +
            b"\x01\x00\x18\x00"
        )
        bmp_path.write_bytes(bmp_data)
        
        result = self.command.execute(str(bmp_path))
        
        assert result["success"] is True
        assert result["format"] == "BMP"
        assert result["width"] == 100
        assert result["height"] == 200
        assert result["color_depth"] == 24
        
    def test_parse_jpeg_headers(self, tmp_path):
        """Test parsing valid JPEG headers mock"""
        jpeg_path = tmp_path / "mock.jpg"
        
        # Construct raw JPEG structure:
        # SOI marker: \xff\xd8
        # APP0 marker (ignored segment): \xff\xe0 + length (\x00\x10) + 14 bytes data
        # SOF0 marker: \xff\xc0 + length (\x00\x11) + precision (\x08) + height (\x00\xc8 = 200) + width (\x00\x64 = 100) + color data...
        jpeg_data = (
            b"\xff\xd8" +
            b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00\x60\x00\x60\x00\x00" +
            b"\xff\xc0\x00\x11\x08\x00\xc8\x00\x64\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01" +
            b"\xff\xd9"
        )
        jpeg_path.write_bytes(jpeg_data)
        
        result = self.command.execute(str(jpeg_path))
        
        assert result["success"] is True
        assert result["format"] == "JPEG"
        assert result["width"] == 100
        assert result["height"] == 200
        assert result["color_depth"] == 24  # 8 bit precision * 3 color components
