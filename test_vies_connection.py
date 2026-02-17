#!/usr/bin/env python3
"""
Test VIES API connectivity and diagnose connection issues.
Run this before starting the main app to check if VIES is working.
"""

import requests
import time

def test_vies_api():
    """Test VIES API with a known valid VAT number"""

    test_cases = [
        ("LT", "100013590314", "Valid Lithuanian VAT"),
        ("DE", "811569869", "Valid German VAT"),
        ("FR", "40303265045", "Valid French VAT"),
    ]

    print("=" * 60)
    print("VIES API Connection Test")
    print("=" * 60)
    print()

    all_passed = True

    for country, vat, description in test_cases:
        url = f'https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country}/vat/{vat}'

        print(f"Testing: {description}")
        print(f"URL: {url}")

        try:
            start_time = time.time()
            response = requests.get(url, timeout=30)
            elapsed = time.time() - start_time

            print(f"✅ Response time: {elapsed:.2f}s")
            print(f"✅ Status code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                is_valid = data.get('isValid', False)
                print(f"✅ VAT valid: {is_valid}")

                if is_valid:
                    print(f"   Name: {data.get('name', 'N/A')}")
                    print(f"   Address: {data.get('address', 'N/A')[:50]}...")
            else:
                print(f"⚠️  Non-200 status: {response.text[:100]}")
                all_passed = False

        except requests.exceptions.ConnectionError as e:
            print(f"❌ CONNECTION ERROR: {str(e)}")
            print("   This means:")
            print("   - VIES API might be down")
            print("   - Network firewall blocking connection")
            print("   - DNS issues")
            all_passed = False

        except requests.exceptions.Timeout:
            print(f"❌ TIMEOUT: Request took longer than 30 seconds")
            print("   VIES API is too slow or unresponsive")
            all_passed = False

        except requests.exceptions.SSLError as e:
            print(f"❌ SSL ERROR: {str(e)}")
            print("   SSL certificate issues with VIES API")
            all_passed = False

        except Exception as e:
            print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {str(e)}")
            all_passed = False

        print()
        time.sleep(1)  # Small delay between tests

    print("=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED - VIES API is working!")
        print("You can now run the main application.")
    else:
        print("❌ SOME TESTS FAILED - VIES API has issues")
        print()
        print("Possible solutions:")
        print("1. Wait and try again later (VIES has maintenance windows)")
        print("2. Check https://ec.europa.eu/taxation_customs/vies/ manually")
        print("3. Check your firewall/proxy settings")
        print("4. Try from a different network")
    print("=" * 60)

if __name__ == '__main__':
    test_vies_api()
