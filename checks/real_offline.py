import http.server, socketserver, threading, functools, random
from playwright.sync_api import sync_playwright
PORT=random.randint(20000,40000)
h=functools.partial(http.server.SimpleHTTPRequestHandler); h.log_message=lambda *a:None
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("",PORT),h); threading.Thread(target=srv.serve_forever,daemon=True).start()
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(); pg=ctx.new_page(); pg.set_default_timeout(5000)
    pg.goto(f"http://localhost:{PORT}/STEMMate_Accessible_Prototype_v0.3.html"); pg.evaluate("localStorage.clear()"); pg.reload()
    pg.click("[data-open='a2']"); pg.click("#detailSave")
    ctx.set_offline(True)   # REAL network off, not the simulated button
    pg.click("nav button[data-page='saved']"); pg.click("#savedResults [data-open='a2']")
    print("Real offline, page already open: saved activity opens:", "Paper bridge" in pg.inner_text("#activityDetail"))
    pg.click("nav button[data-page='plans']"); pg.click("#newPlan"); pg.fill("#steps","typed offline")
    print("Real offline: plan editing works and draft saved:", "typed offline" in (pg.evaluate("localStorage.getItem('stem_plans')") or ""))
    try:
        pg.reload(); print("Real offline reload: page loads:", True)
    except Exception as e:
        print("Real offline reload: page loads: False (", str(e).split('\n')[0][:60],")")
    b.close()
srv.shutdown()
