import os
import sys
import requests
import traceback
from binance.client import Client

def run_diagnostics():
    report = ["🔍 **SYSTEM DIAGNOSTICS REPORT** 🔍\n"]
    
    # 1. System Info
    report.append(f"**Python Version:** {sys.version.split()[0]}")
    report.append(f"**Platform:** {sys.platform}")
    
    # 2. Environment Variables (Safety First)
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_SECRET')
    
    report.append("\n**🔑 Credentials Check:**")
    report.append(f"- API Key Present: {'✅' if api_key else '❌'}")
    if api_key:
        report.append(f"- API Key Masked: {api_key[:4]}...{api_key[-4:]}")
    report.append(f"- Secret Present: {'✅' if api_secret else '❌'}")
    
    # 3. IP Check (Crucial for Geo-blocking)
    report.append("\n**🌍 Network / IP Check:**")
    
    # Proxy Check
    proxy_url = os.getenv('PROXY_URL')
    proxies = {'https': proxy_url} if proxy_url else None
    
    if proxy_url:
        report.append(f"🔄 Proxy Configured: `Yes`")
    else:
        report.append(f"🔄 Proxy Configured: `No`")

    try:
        # Check Direct IP
        try:
            direct_ip = requests.get("https://api.ipify.org?format=json", timeout=5).json().get('ip', 'Unknown')
            report.append(f"- Direct IP (Server): `{direct_ip}`")
        except:
            report.append(f"- Direct IP: Failed to resolve")

        # Check Proxy IP (what Binance sees)
        ip_data = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10).json()
        ip_addr = ip_data.get('ip', 'Unknown')
        report.append(f"- Effective IP (Outgoing): `{ip_addr}`")
        
        # Optional: Get Geolocation attempt
        try:
            geo = requests.get(f"http://ip-api.com/json/{ip_addr}", timeout=5).json()
            country = geo.get('country', 'Unknown')
            region = geo.get('regionName', 'Unknown')
            report.append(f"- Location: {country} ({region})")
            
            if country == "United States":
                report.append("\n⚠️ **WARNING: Effective IP is in US. Binance International may block this.**")
            else:
                report.append("\n✅ **Location looks good (Not US).**")
        except:
            report.append("- Location: Could not determine")
            
    except Exception as e:
        report.append(f"❌ Failed to get IP: {str(e)}")

    # 4. Binance Public Connectivity
    report.append("\n**📡 Binance Public API (api.binance.com):**")
    try:
        request_params = {'proxies': proxies} if proxies else None
        client = Client(tld='com', requests_params=request_params)
        # Test Ping
        client.ping()
        report.append("✅ Ping: Success")
        
        # Test Data Fetch
        klines = client.get_klines(symbol='BTCUSDT', interval='15m', limit=1)
        if klines:
            report.append(f"✅ Data Fetch: Success (BTC price: {klines[0][4]})")
        else:
            report.append("❌ Data Fetch: Empty response")
            
    except Exception as e:
        report.append(f"❌ Public Connection Failed:\n`{str(e)}`")

    # 5. Binance Authenticated Connectivity
    if api_key and api_secret:
        report.append("\n**🔐 Binance Authenticated API:**")
        try:
            request_params = {'proxies': proxies} if proxies else None
            auth_client = Client(api_key, api_secret, tld='com', requests_params=request_params)
            account = auth_client.get_account()
            can_trade = account.get('canTrade', False)
            report.append(f"✅ Auth Success!")
            report.append(f"- Can Trade: {can_trade}")
            report.append(f"- Account Type: {account.get('accountType', 'Unknown')}")
            
            # Check Futures Balance specifically if that's what we use
            try:
                futures_bal = auth_client.futures_account_balance()
                usdt_bal = next((item['balance'] for item in futures_bal if item['asset'] == 'USDT'), 0)
                report.append(f"- Futures USDT Balance: {float(usdt_bal):.2f}")
            except Exception as fe:
                report.append(f"- Futures check failed: {str(fe)}")
                
        except Exception as e:
            report.append(f"❌ Auth Failed:\n`{str(e)}`")
    else:
        report.append("\n**🔐 Auth Test Skipped (No Keys)**")

    return "\n".join(report)

if __name__ == "__main__":
    print(run_diagnostics())
