# DesoMonitor Operations Guide

## 🔧 **Node Configuration Operations**

### **📍 Configuration File Location**
```
/path/to/DesoMonitor/nodes_config.json
```

### **🛠️ Basic Node Operations**

#### **1. Add a New Node**
Add this structure to the `nodes` array:
```json
{
  "url": "https://new-node.example.com",
  "name": "New Node Name",
  "description": "Description of the node",
  "active": false,
  "priority": 7,
  "verified": false,
  "last_tested": null,
  "notes": "Newly added - needs testing"
}
```

#### **2. Activate/Deactivate a Node**
Change the `active` field:
```json
"active": true   // Enable node monitoring
"active": false  // Disable node monitoring
```

#### **3. Change Node Priority**
Lower number = higher priority:
```json
"priority": 1    // Highest priority (monitored first)
"priority": 5    // Lower priority
```

#### **4. Update Node Information**
```json
"name": "Updated Node Name",
"description": "Updated description",
"notes": "Updated operational notes"
```

### **⚙️ Global Configuration Settings**

#### **Available Settings in `config` section:**
```json
"config": {
  "max_active_nodes": 6,        // Maximum nodes to monitor simultaneously
  "test_interval_days": 7,      // How often to test inactive nodes
  "timeout_seconds": 30,        // Timeout for node tests
  "min_required_endpoints": 3,  // Minimum API endpoints required
  "auto_disable_failed_nodes": true,  // Auto-disable failing nodes
  "fallback_to_primary": true   // Fall back to primary if others fail
}
```

### **🔄 Step-by-Step Operational Procedures**

#### **Adding a New Node:**

**📋 Standard 3-Step Procedure:**

**Step 1: Add to Configuration JSON**
```json
{
  "url": "https://new-node.example.com/",
  "name": "New Node Name", 
  "description": "Description of the new node",
  "active": false,           // Start inactive until tested
  "priority": 5,             // Next available priority number
  "verified": false,         // Will be set by testing
  "last_tested": "",         // Will be updated by testing
  "notes": "New node - needs testing"
}
```

**Step 2: Test Node Capabilities**
```bash
.\.venv\Scripts\python.exe test_nodes.py
```

**What the test determines automatically:**
- ✅ **Full Node (TxIndex enabled):** `active: true, verified: true` - Monitors POST + CONFIRMATION
- ⚠️ **Validator (No TxIndex):** `active: true, verified: true, post_only: true` - Monitors POST only  
- ❌ **Failed Node:** `active: false, verified: false` - Not included in monitoring

**Step 3: Deploy to Production**
```bash
bash deploy-hetzner-docker.sh
```

**✅ Result:** New node automatically integrated with appropriate monitoring based on its capabilities!

#### **Removing a Node:**

1. **Deactivate First:**
```json
"active": false
```

2. **Wait for Current Measurement Cycle to Complete**

3. **Remove from Configuration:**
Delete the entire node object from the `nodes` array

#### **Changing Active Node Set:**

**Example: Replace SafetyNet with Austin Validator**
```json
{
  "url": "https://safetynet.social",
  "active": false  // Deactivate current node
},
{
  "url": "https://node.0xaustinvalidator.com/",
  "active": true   // Activate new node (ensure it has TxIndex!)
}
```

### **🧪 Testing & Validation Commands**

#### **Test All Configured Nodes:**
```bash
python test_nodes.py
```

#### **Test Specific Node Capabilities:**
```bash
# Test POST capability only
python -c "from test_nodes import test_node_post_capability; print(test_node_post_capability('https://node.example.com'))"

# Test API endpoints
python -c "from test_nodes import test_node_api_endpoints; print(test_node_api_endpoints('https://node.example.com'))"
```

#### **Validate Current Configuration:**
```bash
python -c "from node_manager import NodeManager; nm = NodeManager(); print(nm.get_config_summary())"
```

#### **Check Active Nodes:**
```bash
python -c "from node_manager import NodeManager; nm = NodeManager(); print('Active nodes:', nm.get_active_nodes())"
```

### **🚀 Deployment Procedures**

#### **Local Development Changes:**
1. Edit `nodes_config.json`
2. Test configuration: `python test_nodes.py`
3. Validate changes: `python -c "from node_manager import NodeManager; print(NodeManager().get_config_summary())"`
4. Commit changes: `git add nodes_config.json && git commit -m "Update node configuration"`
5. Push to GitHub: `git push origin main`

#### **Production Deployment:**
```bash
# SSH to production server
ssh -p 15689 carry@159.69.139.36

# Navigate to DesoMonitor directory
cd /home/carry/DesoMonitor

# Pull latest configuration changes
git pull origin main

# Restart the monitoring container
docker restart desomonitor

# Verify deployment
docker logs desomonitor --tail 20
```

### **📊 Monitoring & Health Checks**

#### **View Current Node Status:**
```bash
# Local development
python -c "from node_manager import NodeManager; nm = NodeManager(); print(nm.get_config_summary())"

# Production (via SSH)
ssh -p 15689 carry@159.69.139.36 "cd /home/carry/DesoMonitor && python3 -c 'from node_manager import NodeManager; print(NodeManager().get_config_summary())'"
```

#### **Monitor Real-Time Logs:**
```bash
# Local development
tail -f desomonitor.log

# Production Docker container
ssh -p 15689 carry@159.69.139.36 "docker logs desomonitor -f"
```

#### **Check Container Health:**
```bash
# Production server status
ssh -p 15689 carry@159.69.139.36 "docker ps | grep desomonitor"

# Container resource usage
ssh -p 15689 carry@159.69.139.36 "docker stats desomonitor --no-stream"
```

### **⚠️ Important Operational Notes**

#### **Node Requirements:**
- **TxIndex Required:** Only nodes with TxIndex can provide confirmation timing
- **API Endpoints:** Nodes must support `/api/v0/submit-post` and `/api/v0/get-txn`
- **Network Access:** Nodes must be publicly accessible
- **Performance:** Recommended POST time < 2s, CONFIRM time < 30s

#### **Configuration Best Practices:**
- **Priority Order:** Lower numbers = higher priority (1 = highest)
- **Testing First:** Always test new nodes before activating
- **Gradual Changes:** Don't change all nodes simultaneously
- **Backup Configs:** Keep backups of working configurations
- **Documentation:** Update notes field with relevant information

#### **Safety Guidelines:**
- **Validate JSON:** Check syntax before committing
- **Test Locally:** Validate changes in development first
- **Monitor Deployment:** Watch logs after production changes
- **Rollback Plan:** Keep previous working configuration available

### **🔧 Troubleshooting Guide**

#### **Configuration Issues:**
```bash
# Validate JSON syntax
python -c "import json; json.load(open('nodes_config.json'))"

# Check file permissions
ls -la nodes_config.json

# Verify configuration loading
python -c "from node_manager import NodeManager; NodeManager()"
```

#### **Node Test Failures:**
- **Connection Issues:** Verify node URL is accessible
- **TxIndex Problems:** Check if node has TxIndex enabled
- **API Errors:** Ensure required endpoints are available
- **Timeout Issues:** Increase `timeout_seconds` in config
- **Authentication:** Verify DeSo credentials are correct

#### **Production Deployment Issues:**
```bash
# Check container status
docker ps -a | grep desomonitor

# View detailed logs
docker logs desomonitor --tail 50

# Restart container
docker restart desomonitor

# Rebuild if configuration changes aren't loading
docker stop desomonitor && docker rm desomonitor && docker build -t desomonitor . && docker run -d --name desomonitor --restart unless-stopped desomonitor
```

### **📋 Quick Reference Commands**

#### **Essential Operations:**
```bash
# Test all nodes
python test_nodes.py

# View active configuration
python -c "from node_manager import NodeManager; print(NodeManager().get_config_summary())"

# Deploy to production
git push origin main && ssh -p 15689 carry@159.69.139.36 "cd /home/carry/DesoMonitor && git pull origin main && docker restart desomonitor"

# Monitor production logs
ssh -p 15689 carry@159.69.139.36 "docker logs desomonitor -f"
```

#### **Emergency Procedures:**
```bash
# Revert to safe configuration (if needed)
git checkout HEAD~1 nodes_config.json

# Force production rebuild
ssh -p 15689 carry@159.69.139.36 "cd /home/carry/DesoMonitor && git reset --hard HEAD && git pull origin main && docker stop desomonitor && docker rm desomonitor && docker build -t desomonitor . && docker run -d --name desomonitor --restart unless-stopped desomonitor"
```

### **📈 Performance Optimization**

#### **Node Selection Criteria:**
- **Geographic Distribution:** Mix of regions for redundancy
- **Performance Metrics:** Prioritize faster POST and CONFIRM times
- **Reliability History:** Prefer nodes with consistent uptime
- **TxIndex Capability:** Essential for complete monitoring

#### **Monitoring Frequency:**
- **Active Nodes:** Monitored every 10 minutes
- **Inactive Nodes:** Tested weekly (configurable)
- **Failed Nodes:** Automatically disabled with alerts

---

## 🎯 **Summary**

This operations guide provides complete control over DesoMonitor's node configuration. Follow these procedures to safely add, remove, or modify monitored nodes while maintaining system reliability and performance.

For questions or issues, check the troubleshooting section or review the detailed logs for specific error messages.
