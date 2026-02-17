# Fix: "Job not found" Error

## Problem

Users were getting "Job not found" error which displayed as:
```
Nepavyko gauti progreso atnaujinimų. Prašome perkrauti puslapį ir bandyti dar kartą.
```

## Root Causes

### 1. **Race Condition**
- Frontend connects to `/validate-progress/{job_id}` immediately after getting job_id
- Background thread might not have fully initialized the job yet
- Original wait time: 5 seconds (sometimes not enough)

### 2. **Thread Safety Issue**
- Multiple threads accessing `validation_jobs` dictionary without synchronization
- No lock protecting concurrent reads/writes
- Could lead to race conditions where job appears to "disappear"

### 3. **Flask Debug Mode Auto-Reload**
- `debug=True` enables auto-reload on code changes
- Auto-reload clears in-memory `validation_jobs` dictionary
- Jobs created before reload are lost

## Fixes Applied

### 1. ✅ **Added Thread-Safe Job Updates**

**Added threading lock:**
```python
validation_jobs_lock = threading.Lock()
```

**Created helper function:**
```python
def update_job(job_id, **kwargs):
    """Thread-safe helper to update job status"""
    with validation_jobs_lock:
        if job_id in validation_jobs:
            validation_jobs[job_id].update(kwargs)
        else:
            print(f"[WARNING] Tried to update non-existent job {job_id}")
```

**Benefits**:
- All job updates are atomic
- No race conditions between threads
- Safe concurrent access from validation thread and SSE endpoint

---

### 2. ✅ **Increased Wait Time: 5s → 10s**

**Before:**
```python
max_wait = 5  # seconds
```

**After:**
```python
max_wait = 10  # seconds (increased from 5)
```

**Why**: Some slower systems need more time for thread initialization

---

### 3. ✅ **Added Debug Logging**

**Added comprehensive logging throughout:**
```python
print(f"[VALIDATE] Created job {job_id}, total jobs: {len(validation_jobs)}")
print(f"[WORKER] Starting job {job_id}")
print(f"[PROGRESS] Job {job_id} found after {waited}s")
print(f"[PROGRESS] Job {job_id} NOT FOUND after {max_wait}s")
print(f"[WORKER] Job {job_id} completed successfully")
```

**Benefits**:
- Easy to diagnose where failures occur
- Track job lifecycle in terminal
- See timing issues in real-time

---

### 4. ✅ **Increased Initial Delay: 0.1s → 0.2s**

**Before:**
```python
time.sleep(0.1)  # Small delay to ensure thread has started
```

**After:**
```python
time.sleep(0.2)  # Longer delay to ensure thread has started
```

**Why**: Gives background thread more time to initialize before returning job_id

---

### 5. ✅ **Added Job Creation Timestamp**

**Added to job initialization:**
```python
validation_jobs[job_id] = {
    'status': 'initializing',
    'progress': 0,
    'processed': 0,
    'total': 0,
    'results': [],
    'retrying': None,
    'output_file': None,
    'error': None,
    'created_at': time.time()  # NEW: Track when job was created
}
```

**Benefits**: Can track job age, implement cleanup later

---

### 6. ✅ **Protected All Dict Access with Lock**

**Replaced all unsafe accesses:**

**Before:**
```python
validation_jobs[job_id]['total'] = total
validation_jobs[job_id]['status'] = 'processing'
validation_jobs[job_id]['results'].append(result_item)
```

**After:**
```python
update_job(job_id, total=total, status='processing')

with validation_jobs_lock:
    if job_id in validation_jobs:
        validation_jobs[job_id]['results'].append(result_item)
```

**Benefits**:
- Thread-safe updates
- Consistent state
- No partial updates

---

### 7. ✅ **Safe Job Copy in SSE Stream**

**Before:**
```python
job = validation_jobs[job_id]  # Direct reference - holding lock too long
```

**After:**
```python
with validation_jobs_lock:
    if job_id not in validation_jobs:
        # Handle disappearing job
        yield error
        return
    job = validation_jobs[job_id].copy()  # Copy to avoid holding lock
```

**Benefits**:
- Lock held for minimal time
- SSE streaming doesn't block job updates
- Handles case where job disappears mid-stream

---

### 8. ✅ **Explicit Flask Configuration**

**Before:**
```python
app.run(debug=True, host='0.0.0.0', port=8080)
```

**After:**
```python
app.run(debug=True, host='0.0.0.0', port=8080, threaded=True, use_reloader=True)
```

**Why**: Makes threading behavior explicit

---

## Files Changed

### `app.py`

**Lines changed:**
- Line 20-21: Added `validation_jobs_lock`
- Line 23-29: Added `update_job()` helper function
- Line 87, 110, 118, 126: Use `update_job()` for retrying flag
- Line 212-218: Added debug logging in `process_validation_job`
- Line 241-247: Use `update_job()` for total/status
- Line 254-264: Use `update_job()` for progress/retrying
- Line 275-280: Safe append to results with lock
- Line 298-300: Use `update_job()` for completion
- Line 304-305: Use `update_job()` for errors
- Line 315-322: Added `created_at`, debug logging, lock in `/validate`
- Line 329: Increased delay to 0.2s
- Line 340-393: Complete rewrite of `/validate-progress` with:
  - Increased wait to 10s
  - Debug logging
  - Thread-safe job access
  - Safe job copy
  - Handle disappearing jobs
- Last lines: Explicit Flask config with startup banner

---

## Testing Checklist

### Before Starting
- [ ] Stop any running Flask server
- [ ] Delete `uploads/` folder (clean start)
- [ ] Restart Flask server

### Test 1: Normal Operation
- [ ] Upload file with 10-50 VAT numbers
- [ ] Click "Tikrinti PVM Numerius"
- [ ] Should NOT see "Job not found" error
- [ ] Progress bar should appear immediately
- [ ] Watch terminal for logs:
  ```
  [VALIDATE] Created job abc-123, total jobs: 1
  [WORKER] Starting job abc-123
  [PROGRESS] Client connected for job abc-123
  [PROGRESS] Job abc-123 found after 0.0s
  [WORKER] Job abc-123 found 50 VAT numbers
  ```

### Test 2: Large File
- [ ] Upload file with 200+ VAT numbers
- [ ] Click "Tikrinti PVM Numerius"
- [ ] Should start processing immediately
- [ ] Check terminal shows job creation and connection

### Test 3: Multiple Files
- [ ] Open two browser tabs
- [ ] Upload different files in each
- [ ] Start validation in both (within seconds of each other)
- [ ] Both should work without "Job not found"
- [ ] Terminal should show logs for both job IDs

### Test 4: Quick Succession
- [ ] Upload file
- [ ] Start validation
- [ ] Immediately refresh page (before validation completes)
- [ ] Start new validation
- [ ] Should work (old job lost is expected, new job should work)

---

## Expected Terminal Output

### Successful Job Flow:
```
===================================================================
Starting VAT Validator Server
===================================================================
Server: http://0.0.0.0:8080
Note: Debug mode is ON - auto-reload enabled
===================================================================

[VALIDATE] Created job 12345, total jobs: 1
[WORKER] Starting job 12345
[PROGRESS] Client connected for job 12345
[PROGRESS] Job 12345 found after 0.0s
[WORKER] Job 12345 found 217 VAT numbers
[WORKER] Job 12345 completed successfully
[PROGRESS] Job 12345 finished with status: completed
```

### If Job Not Found (Should be RARE now):
```
[VALIDATE] Created job 67890, total jobs: 1
[PROGRESS] Client connected for job 67890
[PROGRESS] Job 67890 not found, waiting... (total jobs: 0)
[PROGRESS] Job 67890 not found, waiting... (total jobs: 0)
...
[PROGRESS] Job 67890 NOT FOUND after 10s
```

---

## Why This Fixes the Issue

### Race Condition Fixed
- ✅ **10-second wait** gives plenty of time for thread initialization
- ✅ **0.2s delay** ensures job exists before SSE connection
- ✅ **Thread lock** prevents concurrent access issues

### Thread Safety Fixed
- ✅ **All updates use lock** - no race conditions
- ✅ **Safe job copy** - SSE doesn't block validation
- ✅ **Check before access** - handle missing jobs gracefully

### Debug Visibility
- ✅ **Comprehensive logging** - see exactly what's happening
- ✅ **Track job lifecycle** - creation → processing → completion
- ✅ **Identify problems** - logs show where failures occur

---

## Known Limitations

### Auto-Reload Still Clears Jobs
**Issue**: When Flask auto-reloads (code changes), all jobs are lost

**Impact**:
- Users see "Job not found" if validation was running during reload
- Acceptable during development

**Solution for Production**:
```python
if __name__ == '__main__':
    import os
    is_production = os.getenv('FLASK_ENV') == 'production'

    app.run(
        debug=not is_production,
        host='0.0.0.0',
        port=8080,
        threaded=True,
        use_reloader=not is_production  # Disable in production
    )
```

### In-Memory Storage
**Issue**: Jobs stored in RAM, lost on server restart

**Impact**:
- Jobs don't persist across restarts
- Not suitable for very long-running validations (hours)

**Future Enhancement**:
- Use Redis or database for job storage
- Jobs persist across restarts
- Can run multiple Flask workers

---

## Monitoring

### Check for Problems

**In Terminal**:
```bash
# Look for these warning patterns:
grep "NOT FOUND" server.log
grep "WARNING" server.log
grep "disappeared" server.log
```

**Success Indicators**:
- All jobs show "found after 0.0s" or very small delay
- No "NOT FOUND" messages
- Clean "completed successfully" for each job

**Failure Indicators**:
- "NOT FOUND after 10s" frequently
- "Tried to update non-existent job" warnings
- Jobs disappearing mid-stream

---

## Summary

The "Job not found" error was caused by:
1. Race condition between job creation and SSE connection
2. Missing thread synchronization
3. Auto-reload clearing jobs

Fixed by:
1. ✅ Thread-safe job updates with lock
2. ✅ Increased wait times (5s → 10s, 0.1s → 0.2s)
3. ✅ Comprehensive debug logging
4. ✅ Safe job access patterns
5. ✅ Graceful handling of missing jobs

**Result**: Job not found errors should be extremely rare now, and when they do occur, logs will show exactly why.
