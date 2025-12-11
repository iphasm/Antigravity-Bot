from utils.trading_manager import SessionManager
import os
import shutil

def test_persistence():
    print("🧪 Testing Session Persistence")
    
    test_file = 'data/test_sessions.json'
    
    # Clean setup
    if os.path.exists(test_file):
        os.remove(test_file)
        
    # 1. Create Manager and Add Session
    print("   👉 Creating SessionManager (1)...")
    sm1 = SessionManager(data_file=test_file)
    
    chat_id = "123456789"
    key = "test_key_abc"
    secret = "test_secret_xyz"
    
    print(f"   👉 Adding session for {chat_id}...")
    sm1.create_or_update_session(chat_id, key, secret)
    
    # Verify file exists
    if os.path.exists(test_file):
        print("   ✅ File created.")
    else:
        print("   ❌ File NOT created.")
        return

    # 2. Reload Manager
    print("   👉 Reloading SessionManager (2)...")
    sm2 = SessionManager(data_file=test_file)
    
    saved_session = sm2.get_session(chat_id)
    if saved_session:
        print("   ✅ Session found in reloaded manager.")
        if saved_session.api_key == key and saved_session.api_secret == secret:
            print("   ✅ Keys match.")
        else:
            print(f"   ❌ Keys MISMATCH: {saved_session.api_key} vs {key}")
    else:
        print("   ❌ Session NOT found after reload.")
        
    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)
        print("   🧹 Cleanup done.")

if __name__ == "__main__":
    test_persistence()
