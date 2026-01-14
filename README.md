# TAP Minecraft Multi-Agent System

This project implements an autonomous ecosystem of agents in Minecraft using Python and the `mcpi` API. The system features dynamic agent discovery, asynchronous communication, and a functional base-building workflow.

## Project Structure

Ensure your folders match this structure:

- `agents/` - (Explorer, Miner, Builder logic)
- `strategies/` - (Mining algorithms)
- `core/` - (Base classes, FSM, Messaging, Validation)
- `mcpi/` - (Minecraft API library)
- `tests/` - (Unit and Integration tests)

## Implementation Roadmap (Task Checklist)

### Phase 1: The Core Framework (The "Brain")
Before creating specific bots, the system needs the rules of engagement.

- [x] **Implement `core/fsm.py`**
    - Define the State Enums: `IDLE`, `RUNNING`, `PAUSED`, `WAITING`, `STOPPED`, `ERROR`.
- [x] **Implement `core/messaging.py`**
    - Create the standard JSON Schema validator.
    - Fields required: `type`, `source`, `target`, `timestamp`, `payload`, `status`, `context`.
- [x] **Implement `core/base_agent.py`**
    - Create the abstract class `BaseAgent`.
    - Enforce the `perceive()`, `decide()`, `act()` cycle methods.
    - Integrate the FSM (handling transitions like pause and resume).

### Phase 2: Advanced Engineering Mechanisms
Meeting the Reflective and Concurrency requirements.

- [x] **Implement Dynamic Discovery (Reflection)**
    - In `main.py`, write a scanner that looks into `agents/` and imports classes automatically without manual import statements.
- [x] **Implement The Communication Bus**
    - Choose a mechanism (Queue or Event Bus) for asynchronous messaging.
    - Ensure messages are logged with timestamps.
- [x] **Implement Strategy Pattern Loader**
    - In `miner_bot.py`, allow it to dynamically load strategies (Vertical, Grid) from the `strategies/` folder.

### Phase 3: Agent Logic (The Behavior)
Coding the specific intelligence of each bot.

- [x] **ExplorerBot (`agents/explorer_bot.py`)**
    - Implement `getHeight(x, z)` scanning.
    - Use Functional Programming (`map`/`filter`) to process terrain data (e.g., finding flat spots).
    - Publish `map.v1` messages.
- [x] **BuilderBot (`agents/builder_bot.py`)**
    - Listen for `map.v1` and calculate a Bill of Materials (BOM).
    - Publish `materials.requirements.v1`.
    - Wait for `inventory.v1` updates before building.
- [x] **MinerBot (`agents/miner_bot.py`)**
    - Listen for `materials.requirements.v1`.
    - Implement Mining Strategies in `strategies/mining/`:
        - [x] Vertical Search.
        - [x] Grid Search.
    - Implement Locking (lock specific x,z sectors while mining).

### Phase 4: Coordination & User Control
Connecting the parts and letting the user drive.

- [x] **Chat Command Handler**
    - Implement a listener for in-game commands (e.g., `/explorer start`).
    - Convert chat commands into internal JSON control messages.
- [x] **Synchronization Logic**
    - Ensure BuilderBot pauses if materials run out.
    - Ensure MinerBot releases locks if stopped.
    - Test the full loop: Explorer → Builder → Miner → Builder.

### Phase 5: Quality Assurance & Submission

- [x] **Automated Tests (`tests/`)**
    - Write unit tests for JSON validation.
    - Write integration tests for the message flow.
- [x] **CI/CD Setup (`.github/workflows`)**
    - Configure GitHub Actions to run tests on push.
- [x] **Documentation**
    - Add docstrings (PEP8) to all classes.
    - Generate the Technical Report with diagrams.

## 🛠 Usage

### Starting the Server
1. Navigate to `AdventureInMinecraft/Server`
2. Run `StartServer.bat` (Windows) or `StartServer.sh` (Linux/Mac).

### Running the Agents
```bash
python main.py
```

### In-Game Commands
- `/workflow run` - Starts the full Explorer->Builder->Miner cycle.
- `/agent pause` - Pauses all agents.
- `/agent resume` - Resumes all agents.

