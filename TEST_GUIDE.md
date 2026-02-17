# Testing Guide for Batch Processing

## Quick Start

1. **Start the application:**
```bash
cd /Users/michail/vat-validator
source venv/bin/activate
python app.py
```

2. **Open browser:**
Navigate to: http://localhost:8080

3. **Upload test file:**
Use: `/Users/michail/Downloads/Pirkimia is ES VAT tikrinimas.xlsx`
(Already copied to `uploads/test.xlsx`)

## What to Expect

### Before (Old Behavior)
- Click "Validate" → Wait 65+ seconds
- Browser shows loading spinner
- After 30-60 seconds: **"Unexpected end of JSON input"** error
- No results, validation incomplete

### Now (New Behavior)
- Click "Validate" → Immediate response
- Progress bar appears showing "0%"
- Every 0.5 seconds, progress updates:
  - "Tikrinama: 1 iš 217 PVM numerių..."
  - "Tikrinama: 2 iš 217 PVM numerių..."
  - Progress bar: 1%, 2%, 3%... 100%
- Results appear in real-time as each VAT is validated
- After ~65 seconds: "Tikrinimas baigtas!"
- Download button enabled
- ✅ No errors, all 217 VAT numbers validated

## Visual Flow

```
USER ACTION          FRONTEND              BACKEND                 VIES API
───────────          ─────────             ────────                ─────────
Upload Excel    →    POST /upload     →    Save file
                ←    Return sheets

Click Validate  →    POST /validate   →    Create job_id
                                            Start thread ───────┐
                ←    Return job_id                            │
                                                               │
Connect SSE     →    GET /validate-                           │
                     progress/{id}                            │
                                                               │
                                      Background Thread:      │
                ←    Progress: 0%                             │
                                            Process VAT #1 ──→ Validate
                                                           ←── Valid/Invalid
                ←    Progress: 1%          Update job
                     Result #1
                                            Process VAT #2 ──→ Validate
                ←    Progress: 2%                         ←── Valid/Invalid
                     Result #2

                     ... (continues) ...

                ←    Progress: 100%        Save Excel file
                     All results
                     Status: completed
                                            Thread ends ───────┘
Close SSE

Download File   →    GET /download    →    Send file
                ←    Excel file
```

## Browser Console Output (Expected)

Open DevTools (F12) → Console tab. You should see:

```
EventSource connected: /validate-progress/abc-123-def-456
Progress update: {status: "processing", progress: 5, processed: 10, total: 217}
Progress update: {status: "processing", progress: 10, processed: 21, total: 217}
...
Progress update: {status: "completed", progress: 100, processed: 217, total: 217}
EventSource closed
```

## Common Issues & Solutions

### Issue 1: "EventSource error"
**Solution:** Check that Flask app is running and accessible

### Issue 2: Progress stuck at 0%
**Solution:** Check browser console for errors. Verify SSE endpoint is accessible.

### Issue 3: Results not appearing
**Solution:** Check that `validation_jobs` has your job_id. Verify thread started.

### Issue 4: Download button disabled
**Solution:** Wait for "Status: completed". Check `output_file` is set.

## Manual Testing Steps

1. ✅ Upload file → Should show sheet and column dropdowns
2. ✅ Select sheet → Should update column dropdown
3. ✅ Select column → "Validate" button should enable
4. ✅ Click Validate → Should immediately show progress step
5. ✅ Progress bar → Should animate from 0% to 100%
6. ✅ Progress text → Should show "X iš Y PVM numerių"
7. ✅ Results → Should appear one by one in real-time
8. ✅ Summary → Should show "Teisingi: X | Neteisingi: Y"
9. ✅ Download → Should download colored Excel file
10. ✅ Open Excel → Cells should be colored (green/red/yellow)

## Performance Metrics

**File:** 217 VAT numbers
**Expected time:** ~65 seconds (217 × 0.3s)
**Progress updates:** ~130 updates (every 0.5s for 65s)
**Memory usage:** <50MB for job storage
**CPU usage:** Low (waiting on API most of the time)

## Test with Different File Sizes

- **Small (10 VAT):** ~3 seconds, progress updates quickly
- **Medium (50 VAT):** ~15 seconds, smooth progress
- **Large (200+ VAT):** ~60-70 seconds, real-time updates prevent timeout
- **Very large (500+ VAT):** ~150 seconds, still works (no timeout!)

## Browser Compatibility

✅ Chrome/Edge (Chromium) - Full support
✅ Firefox - Full support
✅ Safari - Full support
✅ Mobile browsers - Full support (SSE is widely supported)

## Production Deployment

When deploying to Render:
1. Push changes to GitHub
2. Render auto-deploys with new `render.yaml`
3. Gunicorn starts with: `--timeout 300 --workers 2 --threads 4`
4. Large files work perfectly on production

## Debug Mode

To see detailed logs:
```python
# In app.py, add at top of process_validation_job:
print(f"Starting job {job_id} for {filename}")

# After each VAT:
print(f"Job {job_id}: Processed {idx}/{total} - {vat_value} = {result['valid']}")
```

Then watch terminal while validation runs.
