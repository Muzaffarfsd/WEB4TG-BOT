#!/usr/bin/env python3
import sys
import importlib

def check_status():
    print("=" * 50)
    print("WEB4TG Studio AI Agent Bot — Status Check")
    print("=" * 50)
    
    modules = [
        ("src.config", "Configuration"),
        ("src.database", "Database module"),
        ("src.ai_client", "AI Client (Gemini)"),
        ("src.leads", "Lead Management"),
        ("src.calculator", "Cost Calculator"),
        ("src.referrals", "Referral Program"),
        ("src.loyalty", "Loyalty System"),
        ("src.tasks_tracker", "Tasks Tracker"),
        ("src.followup", "Follow-up System"),
        ("src.broadcast", "Broadcast System"),
        ("src.analytics", "Analytics"),
        ("src.security", "Security"),
        ("src.handlers", "Handlers"),
    ]
    
    ok = 0
    fail = 0
    for mod_name, label in modules:
        try:
            importlib.import_module(mod_name)
            print(f"  [OK] {label}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {label}: {e}")
            fail += 1
    
    print("-" * 50)
    print(f"Result: {ok} OK, {fail} FAIL out of {len(modules)} modules")
    
    if fail > 0:
        print("\nFix failed modules before deploying to Railway.")
        sys.exit(1)
    else:
        print("\nAll modules loaded successfully.")
        print("Ready for Railway deployment (python bot.py)")
        print("\nREMINDER: Do NOT run bot.py on Replit!")

if __name__ == "__main__":
    check_status()
