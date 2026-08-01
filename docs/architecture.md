# LAZARUS Architecture — Version 4.1.0

## 🔧设计理念

سیستم مثل یه **کامپیوتر** طراحی شده:
- **سخت‌افزار** = ماژول‌های اصلی (AI, Executor, State)
- **نرم‌افزار** = الگوریتم‌ها و جریان داده
- **سیستم‌عامل** = مدیریت صف، هماهنگی، خطا

## 🏗️ معماری (CPU-like)

```
┌─────────────────────────────────────┐
│           CONTROL UNIT              │
│         (AI Decision Maker)         │
│                                     │
│  1. detect_role()     → admin/dev   │
│  2. needs_code()      → true/false  │
│  3. info_complete()   → true/false  │
│  4. decompose()       → task list   │
│  5. generate_code()   → HTML        │
│  6. verify()          → true/false  │
│  7. fix_code()        → fixed HTML  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          ALU (Processing)           │
│                                     │
│  API Calls → Input                  │
│  LLM       → Processing             │
│  Response  → Output                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        STATE REGISTERS              │
│                                     │
│  PC:    current_step                │
│  SR:    status (idle/running/done)  │
│  ACC:   current HTML output         │
│  MEM:   saved files                 │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       PIPELINE (Data Flow)          │
│                                     │
│  Input → Detect → Plan → Execute    │
│        → Verify → Save → Next       │
└─────────────────────────────────────┘
```

## 📋 Process States (Stallings Model)

| OS State    | Our State    | Description                    |
|-------------|-------------|--------------------------------|
| New         | idle        | No project in progress         |
| Ready       | planning    | Decomposed, waiting to start   |
| Running     | executing   | Generating code                |
| Blocked     | verifying   | Waiting for verification       |
| Terminated  | done/error  | Project complete or failed     |

## 🔀 Scheduling: FCFS (First Come First Served)

**Why FCFS?**
- Tasks are sequential by nature (step N must finish before N+1)
- No preemption needed (can't interrupt code generation)
- Simple and predictable
- Matches pipeline architecture

## 📡 Inter-Process Communication: Pipes

```
Planner → [Task Queue] → Executor → [Output Buffer] → Verifier
                                                           │
                                          ┌────────────────┘
                                          ▼
                                     [State Register]
                                          │
                                          ▼
                                    Save to File
```

## 🛡️ Error Handling: Circuit Breaker Pattern

```
Normal: API Call → Success → Next
        API Call → Fail (1) → Retry
        API Call → Fail (2) → Retry
        API Call → Fail (3) → CIRCUIT BREAK → Skip/Report

Prevents: Infinite loops, API abuse, hanging
```

## 📁 File Management

**Planner creates TODO with file specs:**
```json
{
  "name": "header",
  "description": "Build site header with navigation",
  "file": {
    "name": "header.html",
    "format": "html",
    "template": "base",
    "css": "inline"
  },
  "input": "Site title and menu items",
  "output": "Complete HTML header section"
}
```

**Executor:**
1. Creates file FIRST (empty)
2. Generates code
3. Writes code to file
4. Verifies file content
5. If fails: fixes and rewrites

## 🚫 Removed (Not Needed)

- ❌ Skills system (unnecessary complexity)
- ❌ Memory system (use State Register instead)
- ❌ curl test (use local validation)
- ❌ max_tokens:10 for API (use 100+)

## ✅ Core Principles

1. **Single Responsibility**: Each module does ONE thing
2. **Open/Closed**: Easy to extend, hard to break
3. **Pipe & Filter**: Data flows through stages
4. **Fail-Safe**: Timeout + Retry + Circuit Breaker
5. **Observable**: State Register tracks everything
