# LLM Flow Improvements & Optimization Guide

## Current Flow Analysis

```
REASON → PLAN → ACT → OBSERVE → CRITIQUE → RESPOND
  ✓LLM    ✗LLM   Tools  ✗LLM      ✓LLM      ✗LLM
```

**Current LLM Usage:**
- ✓ REASON (Extract requirements)
- ✓ CRITIQUE (Self-review draft build)
- ✗ PLAN, OBSERVE, RESPOND (Deterministic/tool-based)

---

## High-Impact Improvements

### 1. **Intelligent PLAN Phase** (High Priority)
**Current:** Fixed heuristic-based planning
```python
# Now: Always CPU → GPU → RAM → PSU order
plan(requirements) → deterministic_sequence()
```

**Improvement:** LLM-driven adaptive planning
```python
def llm_plan(requirements, repository):
    prompt = f"""Given user requirements: {requirements}
    Available component categories: {categories}
    
    Return JSON with query order, strategy, and rationale:
    {{
        "query_order": ["cpu", "motherboard", ...],
        "strategy": "budget-first|performance-first|balanced",
        "component_rationale": {{
            "cpu": "Focus on single-thread for gaming",
            "gpu": "Prioritize new architecture"
        }},
        "estimated_price_distribution": {{"cpu": 0.2, "gpu": 0.4, ...}}
    }}"""
    return llm.generate(prompt)
```

**Benefits:**
- Adapts component priority based on usage
- Better budget allocation strategy
- Explains reasoning for each component

---

### 2. **Iterative Tool Query (OBSERVE Phase)** (High Priority)
**Current:** Single pass through all tools
```python
for component_type in plan:
    query_tool(component_type)  # Get results once
```

**Improvement:** LLM-guided iterative refinement
```python
def intelligent_observe(tool_results, requirements, llm):
    analysis = llm.analyze(f"""
    Current results: {tool_results}
    Requirements: {requirements}
    
    Should we:
    1. Query more results for this component?
    2. Relax filters (price/brand/specs)?
    3. Accept current best match?
    4. Skip this component?
    
    Return: {{"action": "proceed|requery|relax_filters|skip",
             "reason": "...", "new_filters": {{...}} }}
    """)
    
    if analysis["action"] == "requery":
        return query_tool(analysis["new_filters"])
    return tool_results
```

**Benefits:**
- Adaptive search instead of fixed queries
- Handle corner cases (out of stock, rare specs)
- Better quality results through iteration

---

### 3. **Intelligent Feedback Handling** (High Priority)
**Current:** Hardcoded pattern matching
```python
if "cheaper" in feedback.lower():
    reduce_gpu_price()  # Fixed logic
```

**Improvement:** LLM-parsed flexible feedback
```python
def llm_parse_feedback(feedback, current_build, llm):
    response = llm.generate(f"""
    User feedback: "{feedback}"
    Current build: {current_build}
    
    Extract: {{
        "intent": "cheaper|quieter|faster|upgrade|downgrade|...",
        "target_component": "cpu|gpu|memory|...",
        "constraints": [{{"type": "price_reduction", "percentage": 30}}],
        "alternative_strategy": "move_budget_from_X_to_Y"
    }}
    """)
    
    # Apply intelligent transformations
    rebuild_from_feedback(response)
```

**Benefits:**
- Handles complex feedback ("make it faster but quieter")
- Multi-component adjustments
- Intelligent budget redistribution

---

### 4. **Multi-Option Build Generation** (Medium Priority)
**Current:** Single build per run
```python
build = planner.generate_build()  # One option
```

**Improvement:** Generate multiple builds with trade-offs
```python
def generate_multiple_builds(requirements, llm):
    builds = {}
    strategies = ["budget", "performance", "balanced", "gaming-focus", "content-creation-optimized"]
    
    for strategy in strategies:
        plan = llm.generate_plan(requirements, strategy)
        build = execute_plan(plan)
        builds[strategy] = build
    
    # LLM ranks and explains differences
    ranking = llm.rank_builds(builds, requirements)
    return builds, ranking
```

**Output:**
```
Budget Build: $599 (Ryzen 5, RX 6600)
Balanced Build: $899 (Ryzen 7, RTX 4070) ← RECOMMENDED
Performance Build: $1299 (Ryzen 9, RTX 4080)
```

**Benefits:**
- User sees trade-offs explicitly
- Can choose based on priorities
- Educates user on pricing tiers

---

### 5. **Enhanced Compatibility Explanation** (Medium Priority)
**Current:** Binary compatibility check
```python
result = {"compatible": True/False, "issues": [...]}
```

**Improvement:** LLM explains why and suggests fixes
```python
def llm_explain_compatibility(components, compat_result, llm):
    explanation = llm.generate(f"""
    Components: {components}
    Compatibility issues: {compat_result["issues"]}
    
    Provide: {{
        "summary": "This build is compatible because...",
        "potential_concerns": "GPU clearance is 15mm tight",
        "suggested_fixes": [
            {{"issue": "GPU clearance", "solution": "Swap case to NZXT H510"}},
            {{"issue": "power", "solution": "Upgrade PSU to 750W"}}
        ],
        "performance_expectations": "16 FPS @ 1440p High settings"
    }}
    """)
```

---

### 6. **Component Justification & Alternatives** (Medium Priority)
**Current:** Simple rationale strings
```python
component.rationale = "Budget RTX option"
```

**Improvement:** Detailed LLM analysis
```python
def generate_detailed_rationale(selected_component, alternatives, usage, llm):
    analysis = llm.generate(f"""
    Selected: {selected_component}
    Alternatives: {alternatives}
    Usage: {usage}
    
    Provide: {{
        "why_selected": "Best performance-per-dollar for 1440p gaming",
        "performance_tier": "High-end",
        "vs_alternatives": {{
            "vs_cheaper": "20% less VRAM, 30% slower",
            "vs_expensive": "10% slower, $300 more"
        }},
        "use_cases": "Excels at: 1440p gaming, 4K streaming",
        "upgrade_path": "Future GPUs will work well with this system"
    }}
    """)
```

---

### 7. **Clarification Questions (REASON Phase Enhancement)** (Low Priority)
**Current:** No follow-up questions
```python
requirements = extract_requirements(user_input)
```

**Improvement:** Multi-turn clarification
```python
def clarify_requirements(user_input, llm):
    parsed = llm.extract_requirements(user_input)
    
    if parsed["confidence"] < 0.8:
        questions = llm.generate_questions(parsed)
        # Simulate: ask user or proceed with clarified assumptions
        return prompt_user(questions)
    
    return parsed
```

**Benefits:**
- Handles ambiguous inputs better
- Fewer failed builds
- Better user experience

---

### 8. **Build Summary Generation** (Low Priority)
**Current:** Template strings
```python
summary = f"{build.summary} Revised after user feedback."
```

**Improvement:** LLM-generated personalized summaries
```python
def generate_summary(build, requirements, decisions_made, llm):
    summary = llm.generate(f"""
    Build details: {build}
    User requirements: {requirements}
    Key decisions: {decisions_made}
    
    Generate a 2-3 sentence executive summary that:
    1. Addresses primary use case
    2. Highlights key features
    3. Mentions any trade-offs or compromises
    
    Style: Professional but conversational
    """)
    return summary
```

---

## Implementation Priority Matrix

| Feature | Impact | Complexity | Effort | Priority |
|---------|--------|-----------|--------|----------|
| Intelligent PLAN | High | Medium | Medium | 🔴 1 |
| Iterative OBSERVE | High | High | High | 🔴 1 |
| LLM Feedback | High | Medium | Medium | 🔴 2 |
| Multi-Option Builds | Medium | Medium | Medium | 🟡 2 |
| Compatibility Explain | Medium | Low | Low | 🟡 3 |
| Better Rationale | Medium | Low | Low | 🟡 3 |
| Clarification Q&A | Low | Medium | Medium | 🟢 4 |
| Better Summaries | Low | Low | Low | 🟢 4 |

---

## Quick Wins (Easy to Implement)

### Option A: Enhanced Rationale
```python
# In llm_client.py
def generate_component_rationale(component, usage, alternatives, llm):
    prompt = f"Explain why {component} is good for {usage}. Alternatives: {alternatives}"
    return llm.generate(prompt)
```

### Option B: Multi-Option Output
```python
# In planner.py
def generate_budget_tiers(requirements):
    return {
        "budget": plan(requirements, tier="budget"),
        "balanced": plan(requirements, tier="balanced"),
        "performance": plan(requirements, tier="performance")
    }
```

### Option C: Better Feedback Parsing
```python
# In loop.py
def parse_feedback_with_llm(feedback, current_build):
    intent = llm.extract_intent(feedback)
    return apply_intelligent_modifications(intent)
```

---

## Recommended Next Steps

1. **Start with Intelligent PLAN** - Highest ROI
   - Separates strategy from execution
   - Makes planning decisions explainable
   - Easy to test and validate

2. **Add Iterative OBSERVE** - Handles edge cases
   - Retry logic for better results
   - Adaptive filtering
   - Fallback strategies

3. **Enhance Feedback Loop** - Better UX
   - Complex feedback handling
   - Multi-component adjustments
   - Intelligent budget redistribution

4. **Multi-Option Builds** - Educates users
   - Shows trade-offs clearly
   - Builds trust through transparency
   - Enables informed decisions

---

## Code Template: Adding LLM PLAN Phase

```python
# Add to llm_client.py
def generate_build_plan(self, requirements: dict) -> dict:
    """LLM generates intelligent build plan."""
    from src.prompts.templates import BUILD_PLAN_PROMPT
    
    messages = [
        {"role": "system", "content": BUILD_PLAN_PROMPT},
        {"role": "user", "content": json.dumps(requirements)},
    ]
    result = self._chat(messages)
    return self._parse_json(result.get("content", "{}"))

# Add to planner.py
def plan_with_llm(self, requirements):
    """Use LLM guidance for intelligent planning."""
    plan_guidance = self.llm.generate_build_plan(requirements.model_dump())
    
    # Execute plan in suggested order
    build = self._execute_plan(plan_guidance["query_order"])
    return build
```

---

## Summary

**Current State:** 🔹 Deterministic, predictable, fast
**Improved State:** 🔸 Intelligent, adaptive, explainable

Focus on **PLAN and OBSERVE phases** for highest impact. These are where LLM's reasoning power can most improve decision quality and user experience.

MULTI-AGENT PROTOTYPE
https://github.com/manpreethsai/genai-pc-config-multi-agent/tree/main
