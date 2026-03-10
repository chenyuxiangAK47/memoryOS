# Memory Guard — Stage 2 Hook MVP Summary

## Definition

**Stage 2: Cursor Hook Integration MVP.**  
MemoryGuard is now wired into Cursor's agent lifecycle via hooks, so that `prepare` and `check` can be triggered automatically before and after the agent loop, while keeping the main Cursor workflow fail‑open and unobstructed.

---

## What works

- **Hook plumbing**
  - Project‑level hook config at `.cursor/hooks.json`:
    - `beforeSubmitPrompt` → `py -3 .cursor/hooks/pre_memoryguard.py`
    - `afterAgentResponse` → `py -3 .cursor/hooks/post_memoryguard.py`
  - Hooks are executable scripts, not changing Cursor's core behavior; they read stdin and always echo the payload back to stdout.

- **Pre‑hook: automatic prepare**
  - Script: `.cursor/hooks/pre_memoryguard.py`.
  - Behavior:
    - If `outputs/imported_state.json` exists, run:
      ```bash
      py -3 memoryguard.py prepare outputs/imported_state.json
      ```
    - Write CLI output to `outputs/latest_prepare.txt`.
    - On failure, write error to `outputs/latest_prepare_error.txt` and continue.
    - Always pass the original hook event through unchanged.
  - Verified locally with:
    ```bash
    cd d:\Myfile\memoryos
    echo {} | py -3 .cursor/hooks/pre_memoryguard.py
    ```
    which correctly produced an up‑to‑date `latest_prepare.txt` for the imported OriginSystem conversation.

- **Post‑hook: automatic check on real response payload**
  - Script: `.cursor/hooks/post_memoryguard.py`.
  - Behavior:
    - Reads hook payload JSON from stdin.
    - Uses `_extract_response_text(payload)` to heuristically find the latest assistant response text by checking:
      - Top‑level fields like `response`, `agentResponse`, `assistantMessage`, `message`, `content`;
      - Or the last assistant/agent message in a `messages` array.
    - Writes that text to `outputs/latest_output.txt` (if found).
    - Chooses session file:
      - Prefer `outputs/imported_state.json`;
      - Fallback to `outputs/imported_state_session_real_20plus.json` if present.
    - Runs:
      ```bash
      py -3 memoryguard.py check outputs/latest_output.txt --session <session_file>
      ```
    - Writes the full CLI output (drift report) to `outputs/latest_check.json`.
    - On any error, writes a simple message to `outputs/latest_check_error.txt` and still passes the payload through unchanged.
  - Verified locally with:
    ```bash
    cd d:\Myfile\memoryos
    echo "{\"response\": \"test\"}" | py -3 .cursor/hooks/post_memoryguard.py
    ```
    which produced:
    - `outputs/latest_output.txt` with the response text;
    - `outputs/latest_check.json` with a drift report when a valid session file was present.

- **Fail‑open behavior**
  - Both hooks:
    - Guard calls to `memoryguard.py` with try/except and timeouts.
    - Do not raise on failure; at worst, they write an error file.
    - Always echo the original stdin payload (or `{}`) so Cursor can proceed normally even if MemoryGuard fails.

---

## What is still mocked / partial

- **Pre‑hook does not yet modify the live prompt**
  - It generates `latest_prepare.txt` (Enhanced prompt with current state + hard/soft constraints), but does not rewrite the actual agent prompt payload.
  - Effectively: **automatic prepare artifact**, not yet **automatic prompt injection**.

- **Post‑hook extraction schema is heuristic**
  - `_extract_response_text` uses common field names (`response`, `agentResponse`, `message.content`, etc.) and a `messages` array fallback.
  - It is robust but best‑effort; true schema alignment with Cursor's payload would allow a more precise binding.

---

## Next validation targets (toward “full Stage 2”)

1. **Prompt injection effect (Pre‑hook Stage 2B)**
   - Wire `latest_prepare` into the actual agent prompt:
     - Read the existing user request from the hook payload;
     - Construct a new prompt: `Enhanced prompt + 用户本轮请求`;
     - Write this modified payload back to stdout.
   - A/B test:
     - Same question, once without enhanced context, once with pre‑hook injection.
     - Evaluate improvements on: state alignment, constraint respect, and “懂人话”感受。

2. **Real‑time drift check on every response**
   - Confirm that `post_memoryguard.py` is actually seeing the full, final response for each agent run in Cursor.
   - Validate on:
     - At least one “OK” answer (`final_status: "ok"`).
     - At least one intentionally drifted answer (`final_status: "possible_memory_drift"` with meaningful violations).

3. **Robust fail‑open under bad inputs**
   - Test cases:
     - `outputs/imported_state.json` missing or corrupted.
     - `memoryguard.py` throwing an exception.
     - Hook payload JSON malformed.
   - Expected behavior:
     - Cursor continues to function normally;
     - Only `latest_prepare_error.txt` / `latest_check_error.txt` are updated.

---

## One‑line status

Stage 2 hook MVP is complete: Cursor can automatically trigger MemoryGuard `prepare` and `check` hooks and persist local artifacts without breaking the agent loop.  
Remaining work: bind pre‑hook to real prompt injection, strengthen post‑hook’s binding to actual responses, and validate A/B improvements on real tasks.

