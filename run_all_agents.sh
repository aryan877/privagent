#!/bin/bash

# PrivAgent - Run All Agents Script
# This script starts all 4 agents in separate terminal windows/tabs

echo "🚀 Starting PrivAgent Multi-Agent System..."
echo "================================================"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv not found. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check if Light Protocol CLI is installed
if ! command -v light &> /dev/null; then
    echo "❌ Error: Light Protocol CLI not found. Please install:"
    echo "   bun install -g @lightprotocol/zk-compression-cli"
    exit 1
fi

# Export PATH for uv
export PATH="$HOME/.local/bin:$PATH"

echo "✅ Prerequisites checked"
echo ""
echo "Starting agents..."
echo "Each agent will run in a separate process"
echo "Press Ctrl+C in this terminal to stop all agents"
echo ""

# Function to run agent in background
run_agent() {
    local agent_name=$1
    local agent_file=$2
    echo "  📡 Starting $agent_name..."
    uv run python "$agent_file" &
    pids+=($!)
}

# Array to store process IDs
pids=()

# Start all agents
run_agent "Privacy Agent" "agents/privacy_agent.py"
sleep 2

run_agent "Execution Agent" "agents/execution_agent.py"
sleep 2

run_agent "Monitoring Agent" "agents/monitoring_agent.py"
sleep 2

run_agent "Coordinator Agent" "agents/coordinator.py"
sleep 2

echo ""
echo "================================================"
echo "✅ All agents started successfully!"
echo "================================================"
echo ""
echo "Agent Status:"
echo "  • Privacy Agent    (Port 8001) - PID ${pids[0]}"
echo "  • Execution Agent  (Port 8002) - PID ${pids[1]}"
echo "  • Monitoring Agent (Port 8003) - PID ${pids[2]}"
echo "  • Coordinator Agent(Port 8000) - PID ${pids[3]}"
echo ""
echo "📝 Logs are being written to each agent's stdout"
echo ""
echo "To test via ASI:One:"
echo "  1. Check agents/coordinator.py output for agent address"
echo "  2. Go to https://asi1.ai"
echo "  3. Search for your agent address"
echo "  4. Send message: 'hello'"
echo ""
echo "Press Ctrl+C to stop all agents"
echo "================================================"

# Trap Ctrl+C and kill all agents
trap 'echo ""; echo "Stopping all agents..."; for pid in ${pids[@]}; do kill $pid 2>/dev/null; done; echo "✅ All agents stopped"; exit 0' INT

# Wait for all background processes
wait
