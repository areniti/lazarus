# LAZARUS v5.0 — Complete Architecture Redesign

## Problem Analysis

### Why LAZARUS fails:
1. **One-shot generation**: Tries to build entire website in single API call
2. **No step-by-step**: No iterative refinement
3. **Bad prompts**: Generic prompts that don't guide the model
4. **No verification**: Doesn't check if output is good
5. **No tools**: Can't read/write files independently

### Why Hermes succeeds:
1. **150 max turns**: Many small steps
2. **Tools**: terminal, file_read, file_write, search
3. **Guardrails**: Prevents infinite loops
4. **Compression**: Manages context window
5. **Professional prompts**: Carefully crafted system prompts

## New Architecture: Tool-Based CMS

### Core Concept
Lazarus should work like Hermes but specialized for web development:
- User describes what they want
- Lazarus uses tools to build it step by step
- Each step is small and testable
- User can intervene at any point

### Tool System
```python
tools = {
    "file_read": "Read a file from disk",
    "file_write": "Write content to a file", 
    "file_list": "List files in directory",
    "html_validate": "Validate HTML structure",
    "html_preview": "Preview HTML in browser",
    "search_replace": "Find and replace in file",
    "terminal": "Execute shell command",
}
```

### Pipeline Stages

#### Stage 1: UNDERSTAND (No API)
- Parse user request
- Detect language (Persian/English)
- Classify: chat vs build vs edit
- Extract requirements

#### Stage 2: PLAN (1 API call)
- List components to build
- Order by dependency
- Estimate complexity

#### Stage 3: BUILD (N API calls)
- For EACH component:
  - Generate code (1 API call)
  - Validate locally (no API)
  - Save to file (no API)
  - Report progress

#### Stage 4: VERIFY (1 API call)
- Load all files
- Ask AI to review
- List issues

#### Stage 5: FIX (M API calls)
- For each issue:
  - Fix code (1 API call)
  - Validate (no API)

#### Stage 6: FINALIZE (no API)
- Merge into index.html
- Clean up
- Report completion

### Max API Calls per Project
- Simple page: 5-8 calls
- Complex site: 10-15 calls
- With fixes: 15-25 calls

## Prompt Engineering

### System Prompt (v2)
```
You are Lazarus, an expert web developer.

CRITICAL RULES:
1. NEVER generate more than 50 lines of code at once
2. ALWAYS explain what you did after each code block
3. ALWAYS wait for user confirmation before next step
4. If something fails, fix it immediately
5. Use the user's language

OUTPUT FORMAT:
- Code in ```html blocks
- Explanations in plain text
- Questions when unsure
```

### Build Prompt (v2)
```
Write a SINGLE HTML component.

Requirements:
- Component: {name}
- Purpose: {description}
- Style: {style_notes}

Rules:
- Maximum 50 lines
- Inline CSS only
- RTL support
- Responsive

After code, write:
1. What this does
2. How to test it
3. What comes next
```

## Implementation Plan

### Phase 1: Core (Week 1)
- [ ] New system prompt
- [ ] Tool system (file operations)
- [ ] Step-by-step pipeline
- [ ] Basic error handling

### Phase 2: Intelligence (Week 2)
- [ ] Smart decomposition
- [ ] Context management
- [ ] Progress tracking
- [ ] User intervention

### Phase 3: Quality (Week 3)
- [ ] HTML validation
- [ ] CSS best practices
- [ ] Responsive testing
- [ ] Accessibility checks

### Phase 4: Polish (Week 4)
- [ ] Web UI updates
- [ ] Memory system
- [ ] History management
- [ ] Documentation
