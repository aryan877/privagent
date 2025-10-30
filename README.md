![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![Python](https://img.shields.io/badge/python-3.13-blue)
![uAgents](https://img.shields.io/badge/uAgents-0.22+-purple)
![Solana](https://img.shields.io/badge/Solana-mainnet-green)

# PrivAgent 🔐

> **Multi-Agent Privacy System for Solana**  
> Built for the ASI Alliance Cypherpunk Hackathon

Privacy-preserving AI agents that enable confidential transactions, MEV protection, and ZK compression on Solana—making the network usable for institutions and privacy-conscious users alike.

---

## ⚡ Quick Start (5 Minutes)

### 1. Install Prerequisites

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Light Protocol CLI (for ZK compression)
npm install -g @lightprotocol/zk-compression-cli

# Acquire a Helius API key (https://www.helius.dev/)

# Verify installations
uv --version
light --version
```

### 2. Configure Environment

```bash
cp .env.example .env
vi .env  # set RPC URLs, agent seeds, wallet credentials
```

Essential variables:
- `BLOCKCHAIN_HELIUS_RPC_URL` – primary RPC endpoint (Helius recommended)
- `PAYER_PRIVATE_KEY` **or** `PAYER_KEYPAIR_PATH` – execution wallet (JSON array or file)
- `EXECUTION_JUPITER_API_KEY` – optional Jupiter Pro key (public tier if blank)
- `LIGHT_CLI_PATH` – absolute path to the Light Protocol CLI when not on `$PATH`

### 3. Install & Run

```bash
export PATH="$HOME/.local/bin:$PATH"
uv sync

# Run the full bureau (coordinator + specialists)
./run_all_agents.sh

# or start agents individually
uv run python run_coordinator.py
uv run python agents/privacy_agent.py
uv run python agents/execution_agent.py
uv run python agents/monitoring_agent.py
```

### 4. Test via ASI:One
1. Copy the coordinator address printed at startup.
2. Visit https://asi1.ai and search for the address.
3. Say "hello" or ask for `help`.

### 5. 🎬 Impressive Demo Mode (For Hackathon)
```bash
# Quick demo preparation
./demo_quick.sh

# Run guided demo (highlights all winning features)
uv run python privacy_demo.py

# Test key capabilities:
"check privacy score for wallet Gx7UJ7XNBFxRDehVQhZtKRhYHA1J1pkmvxAMUeF4CX"
"compress 1000 USDC from wallet Gx7UJ7XNBFxRDehVQhZtKRhYHA1J1pkmvxAMUeF4CX"
"protect my swap from MEV"
"monitor my wallet for privacy issues"
```

---

## 🚀 Deployment

### Prerequisites

Before deploying, ensure you have:
- Python 3.12+ installed
- Node.js (for Light Protocol CLI)
- A Helius API account (free tier available at https://www.helius.dev/)
- OpenAI API key or ASI:One API key for LLM routing

### Step 1: Environment Setup

Create and configure your environment file:

```bash
# Copy the environment template
cp .env-example .env

# Edit with your credentials
vi .env
```

**Required Environment Variables:**

```bash
# LLM Provider (for coordinator routing)
LLM_PROVIDER=openai
LLM_API_KEY=your-openai-api-key-here
LLM_MODEL=gpt-4o-mini

# Blockchain RPC
BLOCKCHAIN_HELIUS_RPC_URL=https://your-helius-rpc-url.mainnet.helius-rpc.com
BLOCKCHAIN_SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# Execution Wallet
PAYER_KEYPAIR_PATH=./keys/payer-keypair.json

# Agent Seeds (use unique secure values)
COORDINATOR_SEED=your-secure-coordinator-seed-phrase-here
PRIVACY_AGENT_SEED=your-secure-privacy-agent-seed-phrase-here
EXECUTION_AGENT_SEED=your-secure-execution-agent-seed-phrase-here
MONITORING_AGENT_SEED=your-secure-monitoring-agent-seed-phrase-here
```

**Getting API Keys:**

- **OpenAI**: Visit [platform.openai.com/api-keys](https://platform.openai.com/api-keys) to create an API key
- **ASI:One** (Alternative): Visit [asi1.ai](https://asi1.ai), sign up, navigate to profile → "API Keys"
- **Helius RPC**: Sign up at [helius.dev](https://www.helius.dev/) for free RPC access

### Step 2: Install Dependencies

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Install Light Protocol CLI
npm install -g @lightprotocol/zk-compression-cli

# Sync Python dependencies
cd agent/
uv sync

# Verify installations
uv --version
light --version
python --version  # Should be 3.12+
```

### Step 3: Local Testing

Test your setup locally before deploying:

```bash
# Run authentication tests
uv run python tests/test_authentication.py

# Start coordinator agent
uv run python run_coordinator.py
```

**Expected Output:**
```
============================================================
PrivAgent Coordinator - Starting...
============================================================

Agent Address: agent1qf...
Port: 8000

To test via ASI:One:
1. Go to https://asi1.ai
2. Search for agent: agent1qf...
3. Send message: 'hello' or 'help'
============================================================
```

### Step 4: Deploy to Agentverse

**⚠️ Important Limitation:** Agentverse does not support the Light Protocol CLI (requires npm installation). When deploying to Agentverse, ZK compression features will use simulated mode. For full Light Protocol functionality, run agents locally.

To deploy to production on Agentverse, you need to deploy all 4 agents:

#### 4.1 Deploy Privacy Agent

1. Go to [agentverse.ai](https://agentverse.ai/) and log in
2. Click "My Agents" → "New Agent" → "Blank Agent"
3. Name: `PrivAgent Privacy`
4. Copy content from `agents/privacy_agent.py` and paste
5. Add environment variables in "Secrets" tab:
   ```bash
   BLOCKCHAIN_HELIUS_RPC_URL=your-helius-rpc-url
   PRIVACY_AGENT_SEED=your-secure-seed
   CLI_FALLBACK_TO_API=true  # Required for Agentverse (no CLI available)
   ```
6. Click "Start" and copy the agent address (starts with `agent1...`)

#### 4.2 Deploy Execution Agent

1. Create new agent: `PrivAgent Execution`
2. Copy content from `agents/execution_agent.py`
3. Add environment variables including `PAYER_KEYPAIR_PATH`
4. Start and copy agent address

#### 4.3 Deploy Monitoring Agent

1. Create new agent: `PrivAgent Monitoring`
2. Copy content from `agents/monitoring_agent.py`
3. Add environment variables
4. Start and copy agent address

#### 4.4 Deploy Coordinator Agent

1. Create new agent: `PrivAgent Coordinator`
2. Copy content from `agents/coordinator.py`
3. Add environment variables including addresses from previous steps:
   ```bash
   PRIVACY_AGENT_ADDRESS=agent1q... (from step 4.1)
   EXECUTION_AGENT_ADDRESS=agent1q... (from step 4.2)
   MONITORING_AGENT_ADDRESS=agent1q... (from step 4.3)
   ```
4. Start and copy the coordinator agent address (main entry point)

### Step 5: Test on ASI:One

1. Visit [asi1.ai](https://asi1.ai/) or [agentverse.ai/chat](https://agentverse.ai/chat)
2. Search for your coordinator agent address or "PrivAgent Coordinator"
3. Test with commands:
   ```
   "hello"
   "help"
   "check privacy score for wallet Gx7UJ7XNBFxRDehVQhZtKRhYHA1J1pkmvxAMUeF4CX"
   ```
4. Verify:
   - Agent responds to messages
   - Responses are formatted correctly
   - Session persists across messages

### Recommended: Local Multi-Agent Deployment

**For full Light Protocol CLI support**, run all agents locally on your machine:

```bash
# Terminal 1: Privacy Agent
uv run python agents/privacy_agent.py

# Terminal 2: Execution Agent
uv run python agents/execution_agent.py

# Terminal 3: Monitoring Agent
uv run python agents/monitoring_agent.py

# Terminal 4: Coordinator
uv run python run_coordinator.py
```

All agents will run locally with full ZK compression capabilities via Light Protocol CLI.

### Troubleshooting

**Agent Won't Start:**
```bash
# Check Python version
python --version  # Must be 3.12+

# Reinstall dependencies
uv sync

# Check .env file exists and is configured
cat .env | grep -v "^#" | grep -v "^$"
```

**ASI:One Can't Find Agent:**
1. Verify agent is "Active" on [agentverse.ai/agents](https://agentverse.ai/agents)
2. Check "Chat Protocol" badge is visible
3. Verify `publish_manifest=True` in coordinator.py
4. Wait 5-10 minutes for discovery propagation

---

## 🔧 Configuration Guide

| Category | Key Variables | Notes |
| --- | --- | --- |
| Blockchain | `BLOCKCHAIN_HELIUS_RPC_URL`, `BLOCKCHAIN_SOLANA_RPC_URL`, `BLOCKCHAIN_SOLANA_NETWORK` | Provide mainnet + backup RPCs. |
| Agents | `COORDINATOR_SEED`, `PRIVACY_AGENT_SEED`, `EXECUTION_AGENT_SEED`, `MONITORING_AGENT_SEED` | Use distinct secure seed phrases. |
| Wallet | `PAYER_PRIVATE_KEY` or `PAYER_KEYPAIR_PATH` | JSON array (SPL keypair) or path to keypair file. |
| Execution | `EXECUTION_JUPITER_API_KEY`, `EXECUTION_MAX_PRIORITY_FEE`, `JUPITER_TIMING_JITTER` | Tunes Jupiter client privacy + performance. |
| CLI | `LIGHT_CLI_PATH`, `CLI_LIGHT_CLI_PATH`, `CLI_TIMEOUT_SECONDS` | Controls Light Protocol CLI discovery & safety. |
| Monitoring | `MONITORING_DEFAULT_PRIVACY_THRESHOLD`, `MONITORING_ALERT_COOLDOWN_MINUTES` | Alert thresholds and cooldown. |

Publish agent addresses (`*_AGENT_ADDRESS`) when you want preconfigured routing between agents without relying on runtime discovery.

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ASI:One Interface                          │
│                    (Single Entry Point for Users)                  │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ Chat Protocol (Standard uAgents)
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   🤖 Coordinator Agent (Port 8000)                  │
│  • LLM-powered intent routing and parsing                          │
│  • Session management and response aggregation                     │
│  • Intelligent agent orchestration                                 │
│  • Dynamic discovery (Agentverse backup)                           │
└──────┬─────────────────────┬─────────────────────┬─────────────────┘
       │                     │                     │
       │ Inter-Agent         │ Inter-Agent         │ Inter-Agent
       │ Messages            │ Messages            │ Messages
       ▼                     ▼                     ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│🔐 Privacy   │    │⚡ Execution │    │📊 Monitoring │    │🧠 Knowledge │
│   Agent     │    │    Agent    │    │    Agent    │    │   Graph     │
│ (Port 8001) │    │(Port 8002)  │    │(Port 8003)  │    │ (MeTTa)     │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └─────────────┘
       │                   │                   │
       │ Solana            │ Solana            │ MeTTa
       │ Blockchain        │ Blockchain        │ Reasoning
       │ Privacy Data      │ Transaction       │ Analysis
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   🌐 External Services                             │
│   • Light Protocol (ZK Compression)                                │
│   • Jupiter API v6 (DEX Aggregation)                               │
│   • Helius RPC (High-performance Solana RPC)                       │
│   • Solana Mainnet                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Message Flow Example: "Check privacy score for wallet XYZ"

```
1.  User: "check privacy score for wallet XYZ"
    ↓ (via ASI:One Chat Protocol)
2.  Coordinator:
    • LLM parses intent = "privacy_score_analysis"
    • Extracts wallet address: "XYZ"
    • Routes to Privacy Agent
    ↓ (sends PrivacyRequest)
3.  Privacy Agent:
    • Queries Solana blockchain for wallet data
    • Analyzes transaction patterns
    • Runs MeTTa knowledge graph reasoning
    • Generates comprehensive privacy report
    ↓ (sends PrivacyResponse)
4.  Coordinator:
    • Receives PrivacyResponse
    • Formats for user-friendly display
    • Adds context and recommendations
    ↓ (sends ChatMessage via ASI:One)
5.  User: Receives formatted privacy report with:
    • Overall score and grade
    • Detailed breakdown
    • Threat analysis
    • Actionable recommendations
```

### Architecture Advantages

🎯 **User Experience Benefits**
- **Single Entry Point** - Unified interface through ASI:One chat protocol
- **Intelligent Routing** - Automatic agent selection based on user intent
- **Context Management** - Session awareness and response coordination

🚀 **Technical Benefits**
- **LLM-Powered Orchestration** - Advanced intent understanding and parameter extraction
- **Dynamic Composition** - Flexible agent workflows for complex tasks
- **Resilient Communication** - Automatic discovery and fallback mechanisms

🔧 **Operational Benefits**
- **Scalable Design** - Easy to add new specialist agents
- **Maintainable Code** - Clear separation of concerns between agents
- **Production Ready** - Robust error handling and monitoring

---

## 🌟 Key Technical Features

### 🏗️ **Multi-Agent Architecture**
- **Coordinator Pattern** - Centralized orchestration with intelligent routing
- **Dynamic Agent Discovery** - Agentverse integration with automatic fallback
- **Inter-Agent Communication** - Structured message passing between specialists
- **Fault-Tolerant Design** - Robust error handling and graceful degradation

### 🧠 **AI & Knowledge Integration**
- **MeTTa Knowledge Graph** - Symbolic reasoning for privacy pattern analysis
- **LLM Intent Understanding** - Natural language parsing and parameter extraction
- **Multi-Agent Coordination** - Intelligent workflow composition
- **Context-Aware Responses** - Aggregated insights from specialist agents

### ⚡ **Blockchain Integration**
- **Solana Mainnet Connectivity** - Real transaction data and analysis
- **Jupiter v6 API** - Deep liquidity routing with MEV protection
- **Light Protocol ZK Compression** - Advanced privacy features
- **Privacy-Preserving Operations** - Confidential transaction capabilities

### 🔐 **Privacy & Security Features**
- **Transaction Privacy Analysis** - Comprehensive wallet assessment
- **MEV Protection Mechanisms** - Defense against sandwich attacks
- **Zero-Knowledge Compression** - Advanced privacy techniques
- **Risk Assessment Tools** - Proactive threat detection

---

## 💡 Feature Highlights

### Coordinator Agent
- Intent detection for compression, execution, monitoring, and reporting
- Correlation-aware acknowledgements for ASI:One chat protocol
- Monitoring threshold parsing and async response fan-out

### Execution Agent
- Dynamic circuit-breaking + rate limiting tied to network telemetry
- Jupiter v6 client with privacy jitter, route obfuscation, and MEV risk gating
- Signed swap execution when a payer wallet is provided (or unsigned bundle hand-off otherwise)
- Transfer pipeline with compute-budget tuning and Light Protocol compression fallback

### Privacy Agent
- Hybrid telemetry: on-chain heuristics when RPC access is available, deterministic fallbacks otherwise
- Sandboxed Light Protocol CLI execution with JSON validation and timeout control
- MeTTa-backed reasoning that produces grade, threat assessment, and prioritized recommendations

### Monitoring Agent
- Live wallet analysis: counterparty diversity, high-fee bursts, and MEV program detection
- Configurable thresholds with cooldown-aware alerting to chat clients
- Shared MEV detection helpers consumable by tests or external tooling

---

## 📋 Conversational Commands

```
• "check my privacy score"
• "compress my tokens"
• "protect my swap from MEV"
• "monitor my wallet"
• "help"
```

---

## 🛠️ Tech Stack

- Fetch.ai **uAgents 0.22+** (Multi-agent communication)
- SingularityNET **MeTTa** knowledge graph reasoning
- **Light Protocol** ZK compression (CLI: `light transfer`)
- **Jupiter API v6** for deep liquidity routing
- **Helius RPC** mainnet access
- Solana Python SDK (`solana-py`)
- Python 3.13 + uv
- ASI:One chat protocol
- **Dynamic Agent Discovery** (Agentverse integration)
- **LLM-Powered Intent Routing** (Advanced coordinator)

**Real Integrations**
- Light Protocol CLI: `npm install -g @lightprotocol/zk-compression-cli`
- Jupiter Swap API: https://quote-api.jup.ag/v6
- Helius RPC: https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
- MeTTa Knowledge Graph: symbolic reasoning for privacy scoring

### Runtime Notes
- Agents set `publish_agent_details=True` and ship README metadata for Agentverse discovery.
- `ctx.storage` exposes live telemetry such as `performance_metrics`, `network_snapshot`, and pending request state.
- `run_all_agents.py` launches a bureau orchestrating coordinator + specialists with shared configuration.

---

See [guide.md](../guide.md) for complete deployment diagrams, message schemas, and operational playbooks.

**Privacy isn't a feature. It's a right.** 🔐
