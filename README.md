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

## 🤖 Live Agent Addresses

**Main Entry Point (Chat with this on ASI:One):**

- **Coordinator Agent**: `agent1q0l27hvewwd3hj5yg43qyq855eqkg5hvff8yxj5tvnjapcwf42nwycej2r9`

**Specialized Agents (Auto-routed by Coordinator):**

- **Privacy Agent**: `agent1q23s83nytgarhvxektslgclzt5xa6afrryekd736d69n2697ytky68wgttp`
- **Execution Agent**: `agent1qfu7f7jeuhc6swt5tmcag7gjywsavwhme6wzaap5ann48kwkmdq5skjhkwr`
- **Monitoring Agent**: `agent1q03kyc3sadfzwx3mjwyjajqv6gdj6ag39jwdffefl02ldv9fcs4rc0mg2qu`

### 🎯 Try It Now on ASI:One

1. Go to https://asi1.ai
2. Search for the **Coordinator** address above
3. Send: `hello` or `help`

---

## ⚡ Quick Start (2 Minutes)

### 1. Environment Setup

```bash
# Copy the environment template
cp .env.example .env

# Edit with your credentials
vi .env
```

**Required Environment Variables:**

- `LLM_API_KEY` – OpenAI or ASI:One API key
- `COORDINATOR_SEED` – secure seed phrase for coordinator
- `PRIVACY_AGENT_SEED` – secure seed phrase for privacy agent
- `EXECUTION_AGENT_SEED` – secure seed phrase for execution agent
- `MONITORING_AGENT_SEED` – secure seed phrase for monitoring agent
- `BLOCKCHAIN_HELIUS_RPC_URL` – Helius RPC URL

### 2. Run All Agents

```bash
# Start all 4 agents with one command
./run_all_agents.sh
```

**Look for this output:**

```
============================================================
🤖 COORDINATOR AGENT ADDRESS: agent1qf8xk3j2...
📍 Search for this address on https://asi1.ai
============================================================
```

### 3. Test on ASI:One

1. **Copy** the coordinator address (starts with `agent1...`)
2. Go to **https://asi1.ai**
3. Search for your coordinator address
4. Type commands:
   ```
   "hello"
   "help"
   "check privacy score for wallet Gx7UJ7XNBFxRDehVQhZtKRhYHA1J1pkmvxAMUeF4CX"
   ```

✅ **That's it!** Your agents are discoverable and ready for the hackathon.

---

## 🤖 Agent Addresses

**Production Deployment (Local with Mailbox):**

- **Coordinator Agent**: _(Copy from startup output)_
- **Privacy Agent**: _(Generated from PRIVACY_AGENT_SEED)_
- **Execution Agent**: _(Generated from EXECUTION_AGENT_SEED)_
- **Monitoring Agent**: _(Generated from MONITORING_AGENT_SEED)_

**Test via ASI:One**: Search for the coordinator address at https://asi1.ai

### Demo Commands

Try these commands in ASI:One to showcase all features:

- `"hello"` – Basic connectivity test
- `"help"` – Shows all available commands
- `"check privacy score for wallet Gx7UJ7XNBFxRDehVQhZtKRhYHA1J1pkmvxAMUeF4CX"` – Privacy analysis with MeTTa Knowledge Graph
- `"compress 100 USDC from my wallet"` – ZK compression (if Light CLI installed)
- `"monitor my wallet for privacy issues"` – Real-time privacy monitoring

---

## 🚀 Full Setup (Optional)

For complete development setup with Light Protocol CLI support:

### Prerequisites

- Python 3.12+ and uv
- Light Protocol CLI (optional for ZK compression)
- Helius API key
- OpenAI or ASI:One API key

### Complete Installation

```bash
# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv sync

# Optional: Install Light Protocol CLI for real ZK compression
npm install -g @lightprotocol/zk-compression-cli
```

### Testing

```bash
# Start agents (no wallet configuration needed)
./run_all_agents.sh
```

### Troubleshooting

**Agent Won't Start:**

```bash
# Check Python version
python --version  # Should be 3.12+

# Reinstall dependencies
uv sync

# Check .env configuration
cat .env | grep -v "^#" | grep -v "^$"
```

**ASI:One Can't Find Agent:**

1. Verify `mailbox=True` in agent configuration
2. Check `publish_manifest=True` in coordinator.py
3. Wait 5-10 minutes for Agentverse discovery
4. Ensure no `endpoint` configuration overrides mailbox

---

## 🔧 Configuration Guide

| Category   | Key Variables                                                                             | Notes                                                                 |
| ---------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| Blockchain | `BLOCKCHAIN_HELIUS_RPC_URL`, `BLOCKCHAIN_SOLANA_RPC_URL`, `BLOCKCHAIN_SOLANA_NETWORK`     | Provide mainnet + backup RPCs.                                        |
| Agents     | `COORDINATOR_SEED`, `PRIVACY_AGENT_SEED`, `EXECUTION_AGENT_SEED`, `MONITORING_AGENT_SEED` | Use distinct secure seed phrases.                                     |
| Security   | **Client-side signing (recommended)**                                                     | Transactions returned unsigned for wallet signing. Zero custody risk. |
| Execution  | `EXECUTION_JUPITER_API_KEY`, `EXECUTION_MAX_PRIORITY_FEE`, `JUPITER_TIMING_JITTER`        | Tunes Jupiter client privacy + performance.                           |
| CLI        | `LIGHT_CLI_PATH`, `CLI_LIGHT_CLI_PATH`, `CLI_TIMEOUT_SECONDS`                             | Controls Light Protocol CLI discovery & safety.                       |
| Monitoring | `MONITORING_DEFAULT_PRIVACY_THRESHOLD`, `MONITORING_ALERT_COOLDOWN_MINUTES`               | Alert thresholds and cooldown.                                        |

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

## 🔒 Security Model

### Client-Side Signing Architecture

**PrivAgent uses a zero-custody security model** - your private keys never touch our backend servers.

#### How It Works

1. **Agent Creates Transaction**
   - Analyzes your request (transfer, swap, compression)
   - Builds optimal transaction parameters
   - Returns unsigned transaction data

2. **You Sign in Your Wallet**
   - Transaction displayed in Phantom/Solflare
   - You review and approve
   - Your wallet signs with your private key

3. **Transaction Executes On-Chain**
   - Signed transaction broadcasts to Solana
   - Settlement happens on-chain
   - Agent never has custody

#### Security Guarantees

✅ **No Custody Risk** - Backend never holds your private keys
✅ **Cryptographic Proof** - Wallet signature proves ownership
✅ **Web3-Native** - Same security model as Uniswap, Jupiter, Raydium
✅ **User Control** - You approve every transaction explicitly
✅ **No Backend Auth** - Wallet signing eliminates need for separate authentication

#### Why This Is Better

Traditional custodial models require:

- Backend to hold private keys (custody risk)
- Complex authentication flows (challenge-response)
- Trust in the service provider

Client-side signing eliminates all of these:

- **Zero trust required** - You hold your keys
- **Simple UX** - One-click wallet approval
- **Battle-tested** - Industry-standard approach

#### Technical Implementation

**Agent-to-Agent Communication:**

- Uses uAgents built-in cryptographic message verification
- All inter-agent messages are automatically signed and verified by uAgents framework
- Follows Fetch.ai security standards for distributed agent systems

**Transaction Flow:**

```python
# Agent returns unsigned transaction
{
    "success": true,
    "requires_signing": true,
    "operation": "transfer",
    "unsigned_transaction": "base64_encoded_tx...",
    "instructions": [...]
}

# User signs in wallet → broadcasts to Solana
```

**For Developers:**

- Client-side signing implementation in `agents/execution_agent.py`
- See `_finalize_swap()` and `_standard_transfer()` for unsigned transaction return logic
- Frontend wallet integration guide available in project documentation

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
