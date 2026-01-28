# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**LEAN** is an open-source, event-driven algorithmic trading platform built by QuantConnect. It supports backtesting, live trading, and research for multiple asset classes (equities, forex, crypto, futures, options) across 50+ global markets.

**Key characteristics:**
- Multi-language support (C# primary, Python via Python.NET)
- Modular plugin architecture for data feeds, brokerages, and models
- Cross-platform (Windows, macOS, Linux) with Docker support
- Targets .NET 10.0 SDK (use `dotnet build`, not Visual Studio MSBuild)

## Common Development Commands

### Building

```bash
# Build entire solution (primary build command)
dotnet build QuantConnect.Lean.sln

# Build in Release mode
dotnet build /p:Configuration=Release /v:quiet QuantConnect.Lean.sln

# Build specific project
dotnet build Engine/QuantConnect.Lean.Engine.csproj
```

### Running LEAN

```bash
# Run from Launcher project (after building)
cd Launcher/bin/Debug
dotnet QuantConnect.Lean.Launcher.dll

# Or run using project reference
dotnet run --project Launcher/QuantConnect.Lean.Launcher.csproj
```

**Configuration:** Edit `Launcher/config.json` to set algorithm type, language, data paths, and environment (backtesting/live-paper/live-interactive).

### Testing

```bash
# Run all tests
dotnet test ./Tests/bin/Release/QuantConnect.Tests.dll

# Run specific test
dotnet test --filter "FullyQualifiedName~AShareFeeModelTests"

# Exclude certain categories
dotnet test --filter "TestCategory!=TravisExclude"
```

**Test Framework:** NUnit 3.x. Tests are in `/Tests/` organized by project structure.

### Python Support

Python algorithms require Python 3.11.11 and use Python.NET for interop. See `Algorithm.Python/readme.md` for setup instructions.

## High-Level Architecture

LEAN uses a **layered event-driven architecture**:

```
┌─────────────────────────────────────┐
│   Algorithm Layer (User Code)       │  QCAlgorithm, OnData(), Orders
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Engine Layer (Core Engine)        │  Engine, AlgorithmManager, TimeSlice
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Data & Execution Layer            │  DataFeed, HistoryProvider, Brokerage
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│   Market & Security Layer           │  Security, Exchange, Models
└─────────────────────────────────────┘
```

### Data Flow (Backtesting)

```
FileSystemDataFeed
  → SubscriptionDataReader
  → Enumerator Chain (Parse → Aggregate → FillForward → Filter)
  → TimeSlice
  → OnData(slice)
  → Trading logic
  → Orders
  → TransactionHandler
  → FillModel → FeeModel → Portfolio update
```

### Core Components

| Directory | Purpose |
|-----------|---------|
| `/Launcher/` | Entry point, config loading, CLI |
| `/Engine/` | Core orchestration, algorithm lifecycle |
| `/Engine/DataFeeds/` | Historical and real-time data pipelines |
| `/Engine/Setup/` | Algorithm initialization (backtest/live setup handlers) |
| `/Engine/TransactionHandlers/` | Order execution management |
| `/Algorithm/` | Base QCAlgorithm class |
| `/Algorithm.Framework/` | Advanced modules (Alpha/Execution/Risk/Portfolio/Selection) |
| `/Common/Securities/` | Security implementations, pricing, models |
| `/Common/Orders/` | Order system, fee/fill/slippage models |
| `/Brokerages/` | Live trading brokerage integrations |
| `/Indicators/` | 200+ technical analysis indicators |
| `/Configuration/` | Configuration management |
| `/ToolBox/` | Utilities (includes A-share data downloader) |

## Key Design Patterns

1. **Plugin Architecture** - Swap implementations via interfaces (IDataFeed, IBrokerage, IFillModel, etc.)
2. **Event-Driven** - All data flows through `OnData()` events
3. **Factory Pattern** - Component creation via factories (e.g., `BrokerageFactory`)
4. **Strategy Pattern** - Multiple interchangeable models (Fill, Fee, Slippage, Settlement)
5. **Enumerator Chains** - Data processing through composable enumerators

## Critical Concepts

### Symbol-Centric Design
All data is keyed by `Symbol` objects (not strings). A Symbol contains SecurityType, Market, and the ticker value.

**Example:** `Symbol.Create("000001", SecurityType.Equity, Market.China)`

### Time Handling
- Uses NodaTime for precise timezone handling
- Three timezones: data timezone, exchange timezone, algorithm timezone
- Resolution options: Tick, Second, Minute, Hour, Daily

### Security Models
Pluggable models for customization:
- **Fill Model** - How orders fill (immediate, partial fill simulation)
- **Fee Model** - Commission and fees calculation
- **Slippage Model** - Price slippage simulation
- **Buying Power Model** - Margin and leverage calculation
- **Settlement Model** - When funds/securities settle (e.g., T+1 for A-shares)

### Data Subscriptions
Must call `AddEquity()`, `AddCrypto()`, etc. before data arrives. This creates a subscription that the DataFeed will populate.

### Order System
Orders flow: Algorithm → TransactionHandler → Brokerage → OrderEvents → Portfolio updates

## Algorithm Framework (Advanced)

Located in `/Algorithm.Framework/`, provides modular architecture:

- **Alpha Models** - Generate insights/insights
- **Portfolio Construction** - Turn insights into portfolio targets
- **Execution Models** - Execute orders to reach targets
- **Risk Management** - Monitor and limit portfolio risk
- **Universe Selection** - Dynamic security addition/removal

**Framework Module Rules:**
- Modules should do one focused task well (separation of concerns)
- No logging/debugging in production framework modules
- No charting in modules

## A-Share (Chinese Market) Integration

This repository includes custom implementation for Chinese A-shares with special trading rules:

- **T+1 Settlement** - Buy today, sell tomorrow (`TPlusOneSettlementModel`)
- **Price Limits** - 10% daily (5% ST, 20% ChiNext/STAR)
- **100-share lots** - Trading units
- **Fees** - Commission 0.03%, stamp duty 0.1% on sell (`AShareFeeModel`)
- **Market** - `Market.China`, Currency `Currencies.CNY`

**Key files:**
- `/Common/Securities/Equity/AShareEquityExtensions.cs`
- `/Common/Securities/TPlusOneSettlementModel.cs`
- `/Common/Orders/Fees/AShareFeeModel.cs`
- `/ToolBox/AkshareDataDownloader.cs` - China A-share data downloader

## Development Workflow

### For Algorithm Development
1. Create algorithm in `/Algorithm.Python/` or `/Algorithm.CSharp/`
2. Update `/Launcher/config.json` with algorithm details
3. Build: `dotnet build`
4. Run: `dotnet run --project Launcher/QuantConnect.Lean.Launcher.csproj`

### For LEAN Core Development
1. Modify relevant project files
2. Build: `dotnet build QuantConnect.Lean.sln`
3. Test: `dotnet test ./Tests/bin/Release/QuantConnect.Tests.dll`
4. Debug using VS Code or Visual Studio

### For Research
Use the Lean CLI or run Jupyter:
```bash
cd Launcher/bin/Debug
jupyter lab
```
Load `Initialize.csx` (C#) or `start.py` (Python). Use `QuantBook` API for data access.

## Configuration

Main config: `Launcher/config.json`

Key settings:
- `algorithm-type-name` - Algorithm class name
- `algorithm-language` - "Python" or "CSharp"
- `algorithm-location` - Path to algorithm file
- `data-folder` - Root data directory
- `environments` - Environment-specific configs (backtesting, live-paper, live-interactive)

Supports layered configuration (base + environment overrides).

## Code Style

- Follow Microsoft C# coding guidelines
- 4 spaces for indentation (configured in `.editorconfig`)
- All contributions must include unit tests
- Extension methods for security-specific logic (e.g., `AShareEquityExtensions`)
- Factory pattern for creating components

## Solution Structure

The solution has 23 projects. Key projects:
- `QuantConnect.Lean.Launcher` - Entry point
- `QuantConnect.Lean.Engine` - Core engine
- `QuantConnect.Algorithm` - Base algorithm
- `QuantConnect.Algorithm.CSharp` - C# algorithms
- `QuantConnect.Algorithm.Python` - Python algorithms
- `QuantConnect.Common` - Shared types and interfaces
- `QuantConnect.Tests` - Test suite (736 test files)

## Git Workflow

Uses rebase-based workflow for contributors:
1. Fork repository
2. Create topic branch: `bug-123-description` or `feature-123-description`
3. Commit changes with descriptive messages
4. Push to fork
5. Submit pull request to `upstream/master`

**Important:** Once pushed remotely, do NOT rebase. Use `git pull upstream/master` instead.

## Additional Resources

- `/docs/lean-core-principles/00-LEAN架构深度解析.md` - Deep Chinese architecture analysis
- `/misc/` - A-share integration documentation (STATUS.md, QUICK_START.md, TRADING_GUIDE.md)
- `/readme.md` - Main project README with installation and CLI usage
- `/CONTRIBUTING.md` - Detailed contribution guidelines
- `/Tests/readme.md` - Testing instructions
- `/.vscode/readme.md` - VS Code development setup
