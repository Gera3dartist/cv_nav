# Signal Bot for WinTAK

Receive coordinates via Signal messenger and forward them as CoT events to WinTAK.

## Prerequisites

1. **signal-cli** must be installed: https://github.com/AsamK/signal-cli
2. A Signal account must be registered with signal-cli for the bot
3. **WinTAK** configured to receive UDP input on the specified port

## Installation

Requires Python 3.12+

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

## Configuration

Before running, update `config.ini` with your settings:

```ini
[signal]
phone_number = +1234567890  ; your bot's Signal phone number
daemon_host = localhost
daemon_port = 7583

[wintak]
cot_url = udp+wo://192.168.0.17:4243  ; your WinTAK device IP and port
```

Optionally, create `local_config.ini` for local overrides (not tracked by git).

## Usage

Commands should be invoked from the project root folder.

```bash
uv run python -m src.tak_bot
```

## Message Format

Send coordinates to the bot in the format:
```
<latitude> <longitude> <entity_type>
```

Example:
```
48.567123 39.87897 tank
```

Supported entity types: tank, apc, infantry, artillery, mlrs, sam, radar, truck, helicopter, drone

## Architecture

### Data Flow

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────┐
│   Signal    │     │   signal-cli    │     │   Signal Bot    │     │   WinTAK    │
│   Client    │     │    Daemon       │     │   (Python)      │     │   Device    │
└──────┬──────┘     └────────┬────────┘     └────────┬────────┘     └──────┬──────┘
       │                     │                       │                     │
       │  Send message       │                       │                     │
       │  "48.5 39.8 tank"   │                       │                     │
       │────────────────────>│                       │                     │
       │                     │                       │                     │
       │                     │  JSON-RPC via TCP     │                     │
       │                     │  (port 7583)          │                     │
       │                     │──────────────────────>│                     │
       │                     │                       │                     │
       │                     │                       │  Parse coords       │
       │                     │                       │  Generate CoT XML   │
       │                     │                       │                     │
       │                     │                       │  UDP CoT Event      │
       │                     │                       │  (port 4243)        │
       │                     │                       │─────────────────────>
       │                     │                       │                     │
       │                     │                       │                     │  Display
       │                     │                       │                     │  marker
       │                     │                       │                     │  on map
       │                     │                       │                     │
```

## Warning: Development Only

> **This implementation is for development and prototyping purposes only.**

A production-grade deployment would require:

- **Service isolation**: Split into separate microservices (signal receiver, message processor, CoT sender) for independent scaling and failure handling
- **Persistence layer**: Message queue (e.g., Redis, RabbitMQ) to prevent data loss during failures
- **Error handling**: Dead-letter queues, retry mechanisms with exponential backoff
- **Observability**: Structured logging, metrics (Prometheus), distributed tracing
- **High availability**: Service redundancy, health checks, automatic restarts
- **Security**: Message validation, rate limiting, authentication between services
- **Poluted Env** - because the project contains single env for different packages, it may install what is not needed for particular package, initial idea was to have all projects as subproject in a single repo. 
