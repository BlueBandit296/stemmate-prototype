"""QR-02 / QR-04 check: response times under a throttled low-end profile (CPU 6x slower, Slow 3G network),
plus page weight and external requests. Run in headless Chromium."""
import http.server, socketserver, threading, functools, random, sys, time, os, datetime
from playwright.sync_api import sync_playwright
PORT=random.randint(20000,40000)
h=functools.partial(http.server.SimpleHTTPRequestHandler); h.log_message=lambda *a:None
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("",PORT),h); threading.Thread(target=srv.serve_forever,daemon=True).start()
F=sys.argv[1]; out=[]
with sync_playwright() as p:
    b=p.chromium.launch(); ctx=b.new_context(viewport={"width":360,"height":740}); pg=ctx.new_page(); pg.set_default_timeout(15000)
    cdp=ctx.new_cdp_session(pg)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions",{"offline":False,"latency":400,"downloadThroughput":400*1024/8,"uploadThroughput":400*1024/8})
    cdp.send("Emulation.setCPUThrottlingRate",{"rate":6})
    reqs=[]; pg.on("request",lambda r: reqs.append(r.url))
    t=time.perf_counter(); pg.goto(f"http://localhost:{PORT}/{F}",wait_until="load"); load=time.perf_counter()-t
    pg.evaluate("localStorage.clear()")
    ext=[u for u in reqs if not u.startswith(f"http://localhost:{PORT}")]
    def timed(name,fn,done):
        t=time.perf_counter(); fn(); pg.wait_for_function(done); out.append((name,time.perf_counter()-t))
    timed("Apply two filters",lambda:(pg.select_option("#topic","Physics"),pg.select_option("#level","Junior secondary")),"document.querySelectorAll('#activityResults h3').length===2")
    timed("Open activity detail",lambda:pg.click("[data-open='a2']"),"!document.getElementById('detail').classList.contains('hidden')")
    timed("Save for offline use",lambda:pg.click("#detailSave"),"document.getElementById('globalMessage').innerText.includes('saved')")
    timed("Go offline",lambda:pg.click("#networkBtn"),"document.getElementById('netText').innerText.includes('Offline')")
    timed("Open Offline library",lambda:pg.click("nav button[data-page='saved']"),"!document.getElementById('saved').classList.contains('hidden')")
    timed("Open plan editor",lambda:pg.click("nav button[data-page='plans']") or pg.click("#newPlan"),"!document.getElementById('editor').classList.contains('hidden')")
    for s,v in [("#steps","1. Predict 2. Fold"),("#timing","30 min"),("#planMaterials","Paper"),("#safety","Hands clear"),("#inclusion","Pairs")]: pg.fill(s,v)
    timed("Complete plan and queue",lambda:pg.click("#completePlan"),"document.querySelector('#planList .pill')&&document.querySelector('#planList .pill').innerText.startsWith('Pending')")
    timed("Retry sync while offline",lambda:pg.click("#planList [data-retry]"),"document.querySelector('#planList .pill').innerText==='Failed'")
    pg.click("#networkBtn")
    timed("Retry sync online",lambda:pg.click("#planList [data-retry]"),"document.querySelector('#planList .pill').innerText==='Synced'")
    b.close()
srv.shutdown()
print(f"Throttled performance check on {F} ({os.path.getsize(F)/1024:.1f} KB), Chromium, {datetime.date.today()}.")
print("Profile: phone-size viewport 360x740, CPU slowed 6x, network 400 kbit/s with 400 ms latency.")
print(f"First load over the throttled network: {load:.2f} s. Requests to other sites: {len(ext)}. Total requests: {len(reqs)}.")
for n,s in out: print(f"{'PASS' if s<=3 else 'FAIL'}  {n}: {s:.2f} s (target 3 s)")
print(f"Slowest response: {max(s for _,s in out):.2f} s")
