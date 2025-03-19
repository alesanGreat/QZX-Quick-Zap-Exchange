#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Example script to test the QZX RunScript command
"""

import sys
import time

def main():
    print("Example Script Running...")
    print(f"Number of arguments: {len(sys.argv) - 1}")
    print(f"Arguments: {sys.argv[1:]}")
    
    # Simulate processing time
    print("Processing...")
    for i in range(5):
        print(f"Step {i+1}/5 completed")
        time.sleep(0.5)
    
    print("Script execution completed successfully!")

if __name__ == "__main__":
    main() 