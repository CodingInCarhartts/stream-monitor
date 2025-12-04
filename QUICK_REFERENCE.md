# Quick Reference - Resource Management

## At a Glance

**Problem**: Memory leaks, runaway WebSocket connections, hanging requests
**Solution**: Bounded structures, circuit breakers, explicit timeouts, proper cleanup

## Five Key Components

### 1. CircuitBreaker (Prevent Cascading Failures)
```python
breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
try:
    await breaker.call(risky_operation())
except RuntimeError:
    print("Circuit open, operation blocked")
```

### 2. BoundedMessageQueue (Fixed Memory)
```python
queue = BoundedMessageQueue(maxlen=500)
await queue.put(message)  # Auto-discards oldest if full
```

### 3. SessionPool (Managed Connections)
```python
async with session_pool.get_session() as session:
    async with session.post(url, json=data) as response:
        await response.json()
# Session automatically closed after with block
```

### 4. ExplicitTimeoutManager (No Hanging Operations)
```python
async with timeout_manager.timeout_context("operation", 10.0):
    await slow_operation()  # Fails if takes > 10 seconds
```

### 5. WebSocketConnectionManager (Smart Reconnection)
```python
manager = WebSocketConnectionManager()
await manager.connect_with_retry(
    ws_url,
    connection_handler,
    initial_backoff=1.0,
    max_backoff=60.0
)
```

## Current Timeout Configuration

| Where | Timeout | Why |
|-------|---------|-----|
| Message parsing | 10s | Prevent JSON parsing hangs |
| Discord send | 12s | API + buffer |
| Database save | 15s | API + buffer |
| WebSocket connect | 30s | Connection establishment |
| Handler execution | 15s | Prevent blocking |

## Current Bounds

| What | Limit | Why |
|------|-------|-----|
| Messages per channel | 500 | Prevent queue overflow |
| HTTP connections | 50 | Prevent connection exhaustion |
| Circuit breaker (Discord) | 5 failures then open | Fail fast |
| Circuit breaker (Database) | 10 failures then open | Allow more tolerance |
| Recovery wait | 60-120 seconds | Before retry |

## Common Operations

### Check Circuit Breaker Status
```python
if breaker.can_attempt():
    await breaker.call(operation())
else:
    print(f"Circuit {breaker.state.value}")
```

### Get Timeout Statistics
```python
rate = timeout_manager.get_violation_rate()
print(f"Timeout rate: {rate:.1f}%")
```

### Clean Up Resources
```python
# Discord
await discord_service.cleanup()

# Database
await db_service.cleanup()

# WebSocket
await ws_manager.cleanup_all()

# All tasks
await task_manager.cancel_all()
```

### Monitor Active Tasks
```python
count = await task_manager.get_active_count()
print(f"Active tasks: {count}")
```

## Error Handling Pattern

```python
try:
    await asyncio.wait_for(operation(), timeout=10.0)
except asyncio.TimeoutError:
    print("Operation timed out")
except Exception as e:
    print(f"Operation failed: {e}")
finally:
    # Always cleanup
    await cleanup()
```

## Files and Their Responsibilities

| File | Responsibility |
|------|-----------------|
| `resource_manager.py` | Core resource classes |
| `kick_service.py` | WebSocket with timeouts + circuit breaker |
| `discord_service.py` | Discord with circuit breaker + session pool |
| `db_service.py` | Database with circuit breaker + session pool |
| `app.py` | Service initialization + graceful shutdown |

## Shutdown Sequence

```
Signal received (SIGTERM/SIGINT)
    ↓
shutdown_handler() called
    ↓
main() finally block
    ↓
discord_service.cleanup()  → closes all sessions
    ↓
db_service.cleanup()       → closes all sessions
    ↓
task_manager.cancel_all()  → cancels all tasks
    ↓
print("Cleanup complete")
    ↓
Process exits
```

## Monitoring Commands

```bash
# Find timeout errors
grep "timeout" app.log

# Find circuit breaker events
grep -i "circuit\|fail\|open" app.log

# Find cleanup operations
grep -i "cleanup\|closing" app.log

# Watch real-time
tail -f app.log | grep -i "timeout\|circuit\|cleanup"
```

## When Things Go Wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Circuit breaker is OPEN" | Too many failures | Wait for recovery_timeout |
| Operation timeout | Slow API or network | Increase timeout value |
| Memory growing | Queue too large or sessions not closing | Check cleanup is called |
| Connections hanging | No timeout set | Verify timeouts in use |
| Tasks not cancelled | Task never yields control | Check for long blocking ops |

## Configuration Tips

### Increase Tolerance (More Failures Allowed)
```python
CircuitBreaker(failure_threshold=10)  # Was 5
```

### Increase Timeout
```python
async with asyncio.timeout(20.0):  # Was 10.0
```

### Increase Queue Size
```python
BoundedMessageQueue(maxlen=1000)  # Was 500
```

### Increase Recovery Wait
```python
CircuitBreaker(recovery_timeout=120.0)  # Was 60.0
```

## Key Principles

1. **Everything Has a Timeout** - No infinite waits
2. **All Resources Are Bounded** - Fixed max sizes
3. **Failures Don't Cascade** - Circuit breaker stops spread
4. **Cleanup Always Happens** - Even on errors
5. **Graceful Degradation** - Fails safely, doesn't crash

---

**See `RESOURCE_CLEANUP.md` for detailed documentation**
