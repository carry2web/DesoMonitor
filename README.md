# DesoMonitor

A Python application that monitors DeSo blockchain node performance by posting measurement comments and timing their responses. Posts scheduled measurements every 10 minutes and creates daily summary posts with performance visualizations.

## Features
- **Real-time monitoring**: Posts measurement comments to verified DeSo nodes every 10 minutes
- **Performance tracking**: Times complete post-to-confirmation cycles with 2-minute timeouts
- **Daily visualizations**: Generates performance graphs and gauges showing median response times
- **Comprehensive logging**: Detailed UTF-8 logging with emoji status indicators
- **Cloud deployment ready**: Includes Docker and deployment scripts for Hetzner/Azure
- **Verified nodes**: Uses 3 confirmed TxIndex-enabled nodes for reliable monitoring

## Monitored Nodes
- `https://node.deso.org` - Main DeSo node
- `https://desocialworld.desovalidator.net` - Validator with public API
- `https://safetynet.social` - SafetyNet community node

## Setup
1. Ensure Python is installed.
2. (Recommended) Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate   # On Windows
   source .venv/bin/activate # On macOS/Linux
   ```
3. Install dependencies (see below).
4. Configure your node list and schedule in the script.
5. Set up your `.env` file with DeSo credentials:
   ```
   DESO_PUBLIC_KEY="your_public_key"
   DESO_SEED_HEX="your_seed_hex"
   ```

## Install dependencies
```
pip install bip32 mnemonic coincurve ecdsa numpy matplotlib requests python-dotenv
```

## Usage

### Running the Script
- Run the script to start scheduled measurements and daily summary posts:
  ```
  python deso_monitor.py
  ```
  Or, if using the virtual environment:
  ```
  .venv\Scripts\python.exe deso_monitor.py
  ```

### VS Code Task Management
Use VS Code's integrated task system for easier management:

**To Start:**
- Press `Ctrl+Shift+P` → "Tasks: Run Task" → "Run DesoMonitor Script"

**To Stop:**
- Press `Ctrl+C` in the terminal running the task
- Or use Command Palette: `Ctrl+Shift+P` → "Tasks: Terminate Task"

**To Restart:**
- Stop the current task, then start it again using the task command

## How It Works

### Posting Logic
1. **On startup**: Creates initial daily post (may have empty graphs initially)
2. **Start measurements immediately**: Begins collecting data under that post
3. **Every midnight (00:00 UTC)**: 
   - Creates NEW daily post with graphs from previous day's data
   - Continues measurements under the new post
4. **Result**: Each daily post shows performance from the previous 24 hours

### Logging Features
The script provides comprehensive logging with visual indicators:
- 🚀 Startup and configuration
- 🔄 Active monitoring cycles
- 📡 Node connections and status
- ✅ Successful measurements with timing
- ⚠️ Warnings and timeouts
- ❌ Errors and failures
- 📊 Data collection statistics
- 📈 Graph and gauge generation
- 💤 Sleep periods and scheduling

### Output Files
- `desomonitor.log` - Persistent log file with all activities
- `daily_performance.png` - Daily performance graph
- `daily_gauge.png` - Performance gauge visualization
- Console output - Real-time status updates

## Customization
- Edit the script to set your node list, schedule interval, and post formatting.
- Modify `NODES` array to monitor different DeSo nodes
- Adjust `SCHEDULE_INTERVAL` for measurement frequency (in seconds)
- Customize `POST_TAG` hashtag for your measurements

## License
MIT
