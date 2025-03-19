#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
from typing import List, Dict, Any, Optional

class ConfigManager:
    """
    ConfigManager
    
    """
    def __init__(self, config_path: str = "config.json"):
        """
        __init__
        
        Args:
            self: Description
            config_path (str): Description
        """
        self.config_path = config_path
        self.config_data = {}
        self.is_loaded = False
    
    def load_config(self) -> bool:
        """
        load_config
        
        Args:
            self: Description
        
        Returns:
            bool: Description
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.config_data = json.load(f)
                self.is_loaded = True
                return True
            except Exception as e:
                print(f"Error loading config: {str(e)}")
        return False
    
    def save_config(self) -> bool:
        """
        save_config
        
        Args:
            self: Description
        
        Returns:
            bool: Description
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving config: {str(e)}")
            return False
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """
        get_value
        
        Args:
            self: Description
            key (str): Description
            default (Any): Description
        
        Returns:
            Any: Description
        """
        return self.config_data.get(key, default)
    
    def set_value(self, key: str, value: Any) -> None:
        """
        set_value
        
        Args:
            self: Description
            key (str): Description
            value (Any): Description
        
        Returns:
            None: Description
        """
        self.config_data[key] = value


def process_data(data: List[Dict[str, Any]], filter_func=None) -> List[Dict[str, Any]]:
    """
    process_data
    
    Args:
        data (List[Dict[str, Any]]): Description
        filter_func: Description
    
    Returns:
        List[Dict[str, Any]]: Description
    """
    if not data:
        return []
    
    result = []
    for item in data:
        if filter_func is None or filter_func(item):
            result.append(item)
    
    return result


def calculate_statistics(numbers: List[float]) -> Dict[str, float]:
    """
    calculate_statistics
    
    Args:
        numbers (List[float]): Description
    
    Returns:
        Dict[str, float]: Description
    """
    if not numbers:
        return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
    
    count = len(numbers)
    total = sum(numbers)
    avg = total / count
    min_val = min(numbers)
    max_val = max(numbers)
    
    return {
        "count": count,
        "sum": total,
        "avg": avg,
        "min": min_val,
        "max": max_val
    }


if __name__ == "__main__":
    # Test the ConfigManager
    config = ConfigManager("test_config.json")
    config.set_value("name", "Test Application")
    config.set_value("version", "1.0.0")
    config.set_value("debug", True)
    config.save_config()
    
    # Test the data processing
    test_data = [
        {"id": 1, "name": "Item 1", "active": True},
        {"id": 2, "name": "Item 2", "active": False},
        {"id": 3, "name": "Item 3", "active": True}
    ]
    
    active_only = process_data(test_data, lambda x: x["active"])
    print(f"Active items: {len(active_only)}")
    
    # Test statistics
    values = [1.5, 2.5, 3.5, 4.5, 5.5]
    stats = calculate_statistics(values)
    print(f"Statistics: {stats}") 