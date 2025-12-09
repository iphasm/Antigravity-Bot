import os
import shutil
import json
from utils.trading_manager import SessionManager

TEST_DB = 'data/test_sessions.json'

def cleanup():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_session_isolation():
    cleanup()
    
    print("TEST: Initializing SessionManager...")
    sm = SessionManager(data_file=TEST_DB)
    
    # 1. Create Session A
    print("TEST: Creating Session A...")
    sess_a = sm.create_or_update_session("chat_A", "key_A", "secret_A")
    sess_a.update_config("leverage", 10)
    
    # 2. Create Session B
    print("TEST: Creating Session B...")
    sess_b = sm.create_or_update_session("chat_B", "key_B", "secret_B")
    sess_b.update_config("leverage", 20)
    
    sm.save_sessions()
    
    # 3. Reload
    print("TEST: Reloading Manager...")
    sm2 = SessionManager(data_file=TEST_DB)
    
    s_a = sm2.get_session("chat_A")
    s_b = sm2.get_session("chat_B")
    
    print(f"Session A Leverage: {s_a.config['leverage']} (Expected 10)")
    print(f"Session B Leverage: {s_b.config['leverage']} (Expected 20)")
    
    assert s_a.config['leverage'] == 10
    assert s_b.config['leverage'] == 20
    assert s_a.api_key == "key_A"
    assert s_b.api_key == "key_B"
    
    print("✅ TEST PASSED: Sessions are isolated.")
    cleanup()

if __name__ == "__main__":
    test_session_isolation()
