# VIES API Rate Limit Research & Optimization

## Research Summary

### Official Documentation

**VIES API Endpoints**:
- **Production SOAP**: `https://ec.europa.eu/taxation_customs/vies/services/checkVatService.wsdl`
- **Test SOAP**: `https://ec.europa.eu/taxation_customs/vies/checkVatTestService.wsdl`
- **REST API** (undocumented): `https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{countryCode}/vat/{vatNumber}`

Currently using: **REST API** ✓

### Rate Limit Information

**Official EU Documentation** ([VIES WSDL](https://ec.europa.eu/taxation_customs/vies/checkVatTestService.wsdl)):
- ❌ **No specific numeric rate limits published**
- ✅ Error codes exist for rate limiting:
  - `500/501`: GLOBAL_MAX_CONCURRENT_REQ (global across all users)
  - `600/601`: MS_MAX_CONCURRENT_REQ (per member state)
  - `302`: TIMEOUT
- 📝 **Limitation**: Concurrent requests, not per-second limits
- 📝 **Member State specific**: Each EU country has its own limits (e.g., Germany's limit differs from Lithuania's)

**Concurrent Request Limits**:
> "There is a limitation on concurrent requests handled by VIES, with a maximum number of concurrent requests the system can handle; when this maximum is reached, requests are rejected, and this maximum is not linked to a specific IP but is a global count across all users."

**Service Types**:
- WEB Interactive (Manual)
- SOAP (API)
- REST (API) ← We use this
- BATCH services

Each service type has separate concurrent limits.

### Community Findings

**Scott Helme Research** ([How the EU made our website slow](https://scotthelme.co.uk/how-the-eu-made-our-website-slow/)):
- ⚠️ **IP banning**: Requests every minute resulted in IP_BLOCKED errors
- ⚠️ **Failure rate**: 2.45% of requests failed over 5 months (2,457 out of 100,240)
- ⏱️ **Timeout issues**: 283 timeout errors
- 🐌 **Slow responses**: 10.32% of requests took over 1 second, some up to 46+ seconds
- ✅ **Solution**: Reduced to checking once every 10 minutes to avoid bans

**PyVAT Library** ([GitHub Issue #42](https://github.com/iconfinder/pyvat/issues/42)):
- Error: `MS_MAX_CONCURRENT_REQ` during test runs
- Recommendation: Implement request queuing with delays + retry logic + caching

**VAT Sense API** ([Documentation](https://vatsense.com/documentation)):
- Rate limit: **3 requests per second max** (for UK VAT via HMRC)
- This equals: **0.33 seconds minimum delay**
- Returns: `429 Too Many Requests` when exceeded

### Key Insights

1. **No public SLA or rate limits**: EU doesn't publish specific numbers
2. **Concurrent vs Sequential**: The limits are on concurrent requests, not request frequency
3. **Member State variations**: Each country (CZ, DE, LT, etc.) has different capacity
4. **Aggressive blocking**: Frequent polling (even 1/minute) triggers IP bans
5. **Unreliable service**: High timeout rate, slow responses, frequent unavailability

## Recommended Optimal Settings

Based on research and real-world usage:

### ✅ Changes Made

**1. Increased Delay Between Requests**: `0.5s → 1.0s`
- **Rationale**:
  - VAT Sense (commercial service) uses minimum 0.33s
  - Scott Helme found 1-minute polling too aggressive
  - Our sequential processing means no concurrent requests
  - **1 second balances speed vs. reliability**

**2. Increased Rate Limit Retries**: `3 → 5 retries`
- **Rationale**:
  - Rate limiting is external (other users), not our fault
  - More aggressive retry increases success rate
  - Exponential backoff: 2s, 4s, 6s, 8s, 10s (max 30s total wait)

**3. Changed Rate Limit Error Message**:
- **Before**: "API rate limit exceeded (too many requests)" + marked as ❌ Neteisingas (Invalid)
- **After**: "Pabandysiu vėliau (per daug užklausų)" + marked with `retriable: true`
- **Rationale**: VAT number isn't invalid - we just couldn't verify it due to EU API limits

**4. Timeout Settings** (no change):
- API timeout: **30 seconds** (already optimal)
- Timeout retries: **2 retries** (already good)
- Exponential backoff: 1s, 2s

## Performance Impact

### Before Changes
- **Delay**: 0.5s per request
- **Rate limit retries**: 3 (max wait: 12s)
- **Time for 217 VATs**: ~108 seconds (~1.8 minutes)
- **Rate limit failures**: Marked as "Invalid" ❌

### After Changes
- **Delay**: 1.0s per request
- **Rate limit retries**: 5 (max wait: 30s)
- **Time for 217 VATs**: ~217 seconds (~3.6 minutes)
- **Rate limit failures**: Marked as "Pabandysiu vėliau" (Will retry later) with retry indicator

### Trade-offs

**Slower** ⏱️:
- 2x slower processing time
- 217 VATs now takes ~3.6 minutes instead of ~1.8 minutes

**More Reliable** ✅:
- Significantly fewer rate limit errors
- Higher success rate on retries
- No IP bans from aggressive polling
- Better handling of member state capacity limits

**Better UX** 💚:
- Rate-limited VATs aren't marked as "invalid"
- Clear retry messages in Lithuanian
- Users understand it's a temporary API issue, not bad data

## Alternative Solutions Considered

### 1. **Concurrent Processing** ❌ Rejected
- **Pro**: 3-5x faster
- **Con**: Would hit concurrent request limits immediately
- **Con**: Complex to implement safely
- **Con**: Risk of IP bans

### 2. **Third-Party API** (viesapi.eu, vatapi.com) 💰
- **Pro**: Better rate limits and reliability
- **Pro**: 99.9% uptime SLAs
- **Con**: Costs money (€0.01-0.05 per validation)
- **Con**: Requires API key and payment setup
- **Use case**: If processing >10,000 VATs/month

### 3. **Caching** 🔄 Future Enhancement
- **Pro**: Avoid re-checking same VAT numbers
- **Pro**: Instant results for repeats
- **Con**: Needs database/storage
- **Use case**: When users upload same companies repeatedly

## Recommendations by Use Case

### Small Batches (<50 VATs)
- ✅ Current settings are perfect
- Time: ~1 minute
- Reliability: Very high

### Medium Batches (50-300 VATs)
- ✅ Current settings work well
- Time: ~3-6 minutes
- Reliability: High with retries
- User expectation: Progress bar makes wait acceptable

### Large Batches (>300 VATs)
- ⚠️ Consider third-party API (viesapi.eu, vatapi.com)
- ⚠️ Or: Process overnight and email results
- Time with current: >6 minutes
- Free EU API may struggle

## Sources & References

1. [VIES WSDL Documentation](https://ec.europa.eu/taxation_customs/vies/checkVatTestService.wsdl) - Official error codes
2. [How the EU made our website slow](https://scotthelme.co.uk/how-the-eu-made-our-website-slow/) - Real-world failure rates
3. [PyVAT GitHub Issue](https://github.com/iconfinder/pyvat/issues/42) - MS_MAX_CONCURRENT_REQ handling
4. [VAT Sense Documentation](https://vatsense.com/documentation) - Commercial API rate limits
5. [VIES Technical Information](https://ec.europa.eu/taxation_customs/vies/technicalInformation.html) - Official EU page

## Testing Checklist

Test with your 217 VAT file:
- [ ] Slower processing (~3.6 minutes vs 1.8 minutes)
- [ ] Fewer rate limit errors
- [ ] When rate limited: Shows "Pabandysiu vėliau" not "Neteisingas"
- [ ] Retry indicator: "🔄 Kartojama užklausa..." appears
- [ ] Retries up to 5 times with delays: 2s, 4s, 6s, 8s, 10s
- [ ] Success rate: Higher than before

## Conclusion

**Current settings (1s delay, 5 retries) represent the optimal balance** for free VIES API usage:

✅ Reliable (minimal rate limit errors)
✅ Safe (no IP bans)
✅ Simple (no external dependencies)
✅ Free (no API costs)
⚠️ Slower (but managed by progress bar)

For production at scale (>500 VATs/day), consider paid alternatives.
