#!/usr/bin/env python3
"""
Node Configuration Manager for DeSoMonitor
Handles loading, testing, and updating node configurations from JSON
"""

import json
import logging
import datetime
from typing import List, Dict, Optional
import os

class NodeManager:
    def __init__(self, config_file: str = "nodes_config.json"):
        self.config_file = config_file
        self.config = None
        self.load_config()
    
    def load_config(self) -> Dict:
        """Load node configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logging.info(f"✅ Loaded node configuration from {self.config_file}")
            return self.config
        except FileNotFoundError:
            logging.error(f"❌ Configuration file {self.config_file} not found")
            self.create_default_config()
            return self.config
        except json.JSONDecodeError as e:
            logging.error(f"❌ Invalid JSON in {self.config_file}: {e}")
            raise
    
    def save_config(self):
        """Save current configuration to JSON file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            logging.info(f"✅ Configuration saved to {self.config_file}")
        except Exception as e:
            logging.error(f"❌ Error saving configuration: {e}")
            raise
    
    def create_default_config(self):
        """Create a default configuration if none exists"""
        self.config = {
            "nodes": [
                {
                    "url": "https://node.deso.org",
                    "name": "Official DeSo Node",
                    "description": "Main DeSo node",
                    "active": True,
                    "priority": 1,
                    "verified": True,
                    "last_tested": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                    "notes": "Default primary node"
                }
            ],
            "config": {
                "max_active_nodes": 6,
                "test_interval_days": 7,
                "timeout_seconds": 30,
                "min_required_endpoints": 3,
                "auto_disable_failed_nodes": True,
                "fallback_to_primary": True
            }
        }
        self.save_config()
        logging.info("✅ Created default node configuration")
    
    def get_active_nodes(self) -> List[str]:
        """Get list of active node URLs"""
        if not self.config:
            return []
        
        active_nodes = [
            node["url"] for node in self.config["nodes"] 
            if node.get("active", False)
        ]
        
        # Sort by priority
        node_dict = {node["url"]: node for node in self.config["nodes"]}
        active_nodes.sort(key=lambda url: node_dict[url].get("priority", 999))
        
        max_nodes = self.config.get("config", {}).get("max_active_nodes", 6)
        return active_nodes[:max_nodes]
    
    def get_all_nodes(self) -> List[Dict]:
        """Get all nodes regardless of status"""
        return self.config.get("nodes", []) if self.config else []
    
    def get_node_info(self, url: str) -> Optional[Dict]:
        """Get detailed information about a specific node"""
        if not self.config:
            return None
        
        for node in self.config["nodes"]:
            if node["url"] == url:
                return node
        return None
    
    def update_node_status(self, url: str, active: bool, verified: bool = None, notes: str = None):
        """Update node status after testing"""
        if not self.config:
            return False
        
        for node in self.config["nodes"]:
            if node["url"] == url:
                node["active"] = active
                node["last_tested"] = datetime.datetime.utcnow().strftime("%Y-%m-%d")
                
                if verified is not None:
                    node["verified"] = verified
                if notes:
                    node["notes"] = notes
                
                self.save_config()
                logging.info(f"✅ Updated node {url}: active={active}, verified={verified}")
                return True
        
        logging.warning(f"⚠️ Node {url} not found in configuration")
        return False
    
    def add_node(self, url: str, name: str, description: str = "", active: bool = False, priority: int = None):
        """Add a new node to configuration"""
        if not self.config:
            self.create_default_config()
        
        # Check if node already exists
        for node in self.config["nodes"]:
            if node["url"] == url:
                logging.warning(f"⚠️ Node {url} already exists in configuration")
                return False
        
        # Set priority if not specified
        if priority is None:
            existing_priorities = [node.get("priority", 0) for node in self.config["nodes"]]
            priority = max(existing_priorities) + 1 if existing_priorities else 1
        
        new_node = {
            "url": url,
            "name": name,
            "description": description,
            "active": active,
            "priority": priority,
            "verified": False,
            "last_tested": None,
            "notes": "Newly added"
        }
        
        self.config["nodes"].append(new_node)
        self.save_config()
        logging.info(f"✅ Added new node: {url}")
        return True
    
    def remove_node(self, url: str):
        """Remove a node from configuration"""
        if not self.config:
            return False
        
        original_count = len(self.config["nodes"])
        self.config["nodes"] = [node for node in self.config["nodes"] if node["url"] != url]
        
        if len(self.config["nodes"]) < original_count:
            self.save_config()
            logging.info(f"✅ Removed node: {url}")
            return True
        else:
            logging.warning(f"⚠️ Node {url} not found for removal")
            return False
    
    def update_node_test_result(self, url: str, can_post: bool, post_time: float = None, 
                               confirm_time: float = None, error: str = None):
        """Update node with test results"""
        node_info = self.get_node_info(url)
        if not node_info:
            return False
        
        # Determine if node should be active based on test results
        should_be_active = can_post and not error
        
        # Create notes based on test results
        notes = f"Last test: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        if can_post:
            if post_time and confirm_time:
                notes += f" | POST: {post_time:.2f}s, CONFIRM: {confirm_time:.2f}s"
            elif post_time:
                notes += f" | POST: {post_time:.2f}s, CONFIRM: timeout"
        else:
            notes += f" | Error: {error}" if error else " | Failed to post"
        
        return self.update_node_status(url, should_be_active, can_post, notes)
    
    def get_config_summary(self) -> str:
        """Get a human-readable summary of current configuration"""
        if not self.config:
            return "No configuration loaded"
        
        active_nodes = self.get_active_nodes()
        all_nodes = self.get_all_nodes()
        
        summary = f"📊 Node Configuration Summary:\n"
        summary += f"   Total nodes: {len(all_nodes)}\n"
        summary += f"   Active nodes: {len(active_nodes)}\n"
        summary += f"   Max active: {self.config.get('config', {}).get('max_active_nodes', 'N/A')}\n\n"
        
        summary += "🌐 Active Nodes:\n"
        for i, url in enumerate(active_nodes, 1):
            node_info = self.get_node_info(url)
            name = node_info.get("name", "Unknown") if node_info else "Unknown"
            summary += f"   {i}. {name} ({url})\n"
        
        inactive_nodes = [node for node in all_nodes if not node.get("active", False)]
        if inactive_nodes:
            summary += f"\n❌ Inactive Nodes ({len(inactive_nodes)}):\n"
            for node in inactive_nodes:
                summary += f"   - {node.get('name', 'Unknown')} ({node['url']})\n"
        
        return summary
    
    def needs_testing(self, days_threshold: int = None) -> List[str]:
        """Get list of nodes that need testing"""
        if days_threshold is None:
            days_threshold = self.config.get("config", {}).get("test_interval_days", 7)
        
        cutoff_date = datetime.datetime.utcnow() - datetime.timedelta(days=days_threshold)
        cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        
        nodes_to_test = []
        for node in self.config.get("nodes", []):
            last_tested = node.get("last_tested")
            if not last_tested or last_tested < cutoff_str:
                nodes_to_test.append(node["url"])
        
        return nodes_to_test

# Convenience functions for backward compatibility
def load_nodes_from_config(config_file: str = "nodes_config.json") -> List[str]:
    """Load active nodes from JSON config (backward compatibility)"""
    manager = NodeManager(config_file)
    return manager.get_active_nodes()

def update_nodes_from_test_results(test_results: List[Dict], config_file: str = "nodes_config.json"):
    """Update node configuration based on test results"""
    manager = NodeManager(config_file)
    
    for result in test_results:
        manager.update_node_test_result(
            url=result["node"],
            can_post=result["can_post"],
            post_time=result.get("post_time"),
            confirm_time=result.get("confirm_time"),
            error=result.get("error")
        )
    
    logging.info("✅ Updated node configuration with test results")

if __name__ == "__main__":
    # Demo usage
    manager = NodeManager()
    print(manager.get_config_summary())
    
    print(f"\nActive nodes: {manager.get_active_nodes()}")
    print(f"Nodes needing testing: {manager.needs_testing()}")
