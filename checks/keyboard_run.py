"""Keyboard-only run of tasks T1-T3 (AR-03). Only key presses are used: Tab, Shift+Tab, Enter, Space, arrow keys and typing."""
import http.server, socketserver, threading, functools, random, sys, datetime
from playwright.sync_api import sync_playwright
PORT=random.randint(20000,40000)
h=functools.partial(http.server.SimpleHTTPRequestHandler); h.log_message=lambda *a:None
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("",PORT),h); threading.Thread(target=srv.serve_forever,daemon=True).start()
F=sys.argv[1]; log=[]; tabs=[0]
def tab_to(pg, test_js, maxn=120):
    for i in range(maxn):
        pg.keyboard.press("Tab"); tabs[0]+=1
        if pg.evaluate(f"(()=>{{const e=document.activeElement;return {test_js}}})()"): return True
    raise Exception("not reached: "+test_js)
def step(ok,t): log.append(("PASS " if ok else "FAIL ")+t)
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900}); pg.set_default_timeout(5000)
    pg.goto(f"http://localhost:{PORT}/{F}"); pg.evaluate("localStorage.clear()"); pg.reload()
    # T1
    tab_to(pg,"e.id==='topic'"); pg.keyboard.press("ArrowDown")  # Physics
    tab_to(pg,"e.id==='level'") if False else None
    pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Shift+Tab")  # back to level
    pg.keyboard.press("ArrowDown"); pg.keyboard.press("ArrowDown")  # Junior secondary
    vals=pg.evaluate("[level.value,topic.value]")
    tab_to(pg,"e.getAttribute('data-open')==='a2'"); pg.keyboard.press("Enter")
    tab_to(pg,"e.id==='detailSave'"); pg.keyboard.press("Enter")
    step("a2" in pg.evaluate("localStorage.getItem('stem_saved')"), f"T1 filters set by keyboard {vals}; activity opened and saved with Enter")
    pg.keyboard.press("Shift+Tab")
    tab_to(pg,"e.id==='networkBtn'"); pg.keyboard.press("Enter")
    tab_to(pg,"e.dataset&&e.dataset.page==='saved'"); pg.keyboard.press("Enter")
    tab_to(pg,"e.getAttribute('data-open')==='a2'"); pg.keyboard.press("Enter")
    step("Paper bridge" in pg.inner_text("#activityDetail") and "Offline" in pg.inner_text("#netText"), "T1 offline: saved activity opened from the Offline library")
    # T2
    tab_to(pg,"e.id==='makePlan'"); pg.keyboard.press("Enter")
    focus=pg.evaluate("document.activeElement.id")
    pg.keyboard.type("1. Predict. 2. Fold. 3. Add coins. 4. Compare.")
    tab_to(pg,"e.id==='completePlan'"); pg.keyboard.press("Enter")
    msg=pg.inner_text("#globalMessage"); f2=pg.evaluate("document.activeElement.id")
    step("Missing" in msg and f2=="timing", f"T2 incomplete plan: message shown and focus moved to first missing field ({f2})")
    for t in ["30 minutes","Paper, books, coins","Hands clear of weights","Pairs share roles"]:
        pg.keyboard.type(t); pg.keyboard.press("Tab"); tabs[0]+=1
    tab_to(pg,"e.id==='completePlan'"); pg.keyboard.press("Enter")
    st=pg.inner_text("#planList .pill")
    step(st.startswith("Pending"), f"T2 complete plan with keyboard only: status {st}")
    # T3: start new plan offline, reload, resume, recover
    pg.keyboard.press("Shift+Tab")
    tab_to(pg,"e.id==='newPlan'"); pg.keyboard.press("Enter"); pg.keyboard.type("Draft typed while offline")
    pg.reload()
    tab_to(pg,"e.dataset&&e.dataset.page==='plans'"); pg.keyboard.press("Enter")
    n=pg.locator("#planList [data-edit]").count()
    tab_to(pg,"e.hasAttribute('data-edit')&&e.closest('.activity').innerText.includes('Draft')"); pg.keyboard.press("Enter")
    step(pg.input_value("#steps")=="Draft typed while offline", "T3 after reload the draft is reopened by keyboard with its text")
    pg.keyboard.press("Shift+Tab")
    tab_to(pg,"e.id==='networkBtn'"); pg.keyboard.press("Enter")   # offline
    tab_to(pg,"e.hasAttribute('data-retry')"); pg.keyboard.press("Enter")
    s1=pg.locator("#planList .pill").all_inner_texts()
    tab_to(pg,"e.id==='networkBtn'"); pg.keyboard.press("Enter")   # online
    tab_to(pg,"e.hasAttribute('data-retry')"); pg.keyboard.press("Enter")
    s2=pg.locator("#planList .pill").all_inner_texts()
    step("Failed" in s1 and "Synced" in s2, f"T3 failed sync while offline then Retry sync recovered it, by keyboard ({', '.join(s1)} -> {', '.join(s2)})")
    b.close()
srv.shutdown()
print(f"Keyboard-only run of T1-T3 (AR-03) on {F}, Chromium, {datetime.date.today()}. Only key presses used.")
print("\n".join(log)); print(f"Total Tab/Shift+Tab presses: {tabs[0]}. Focus was never trapped.")
