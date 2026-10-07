"""STEMMate scripted checks: baseline tasks T1-T4 against the Team Design Baseline
acceptance indicators, run in a real headless Chromium browser (Playwright).
Technical walkthrough of the code, not user testing.
Usage: python prototype_checks.py <prototype.html> [more files...]
"""
import sys, datetime, threading, http.server, socketserver, os, functools
from playwright.sync_api import sync_playwright

import random
PORT = random.randint(20000, 40000)
results = []

def rec(status, cid, req, text, detail=""):
    results.append(f"{status:<5} {cid:<5} {req:<6} {text}" + (f"  [{detail}]" if detail else ""))

def check(cid, req, text, ok, detail=""):
    rec("PASS" if ok else "FAIL", cid, req, text, detail)

def fill_all(page, partial=False):
    page.fill("#steps", "1. Discuss forces. 2. Fold paper. 3. Add coins. 4. Compare.")
    if partial:
        return
    page.fill("#timing", "30 minutes")
    page.fill("#planMaterials", "Paper, books, coins")
    page.fill("#safety", "Keep hands clear when removing weights.")
    page.fill("#inclusion", "Pairs share roles; diagrams and spoken steps.")

def run_file(pw, fname):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    url = f"http://localhost:{PORT}/{fname}"
    page.goto(url)
    page.evaluate("localStorage.clear()")
    page.reload()
    footer = page.inner_text("footer").split("•")[1].strip()
    results.append(f"\n########## {fname}\nFooter: {footer}\nRun: {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}  Browser: Chromium {b.version}\n")

    # T1 find and save
    page.select_option("#topic", "Physics")
    page.select_option("#level", "Junior secondary")
    titles = page.locator("#activityResults h3").all_inner_texts()
    check("T1-a", "FR-01", "Two filters return only matching activities",
          len(titles) > 0 and all(t in ("Paper bridge challenge", "Pendulum patterns") for t in titles), ", ".join(titles))
    page.click("[data-open='a2']")
    page.click("#detailSave")
    check("T1-b", "FR-02", "Save stores the activity on the device",
          "a2" in page.evaluate("localStorage.getItem('stem_saved')"))
    page.click("#networkBtn")
    page.click("nav button[data-page='saved']")
    page.click("#savedResults [data-open='a2']")
    ok = "Paper bridge challenge" in page.inner_text("#activityDetail")
    check("T1-c", "FR-02", "Offline: saved activity appears in the Offline library and opens", ok, page.inner_text("#netText"))
    page.reload()
    page.click("nav button[data-page='saved']")
    check("T1-d", "FR-02", "After a reload the saved activity is still in the Offline library",
          page.locator("#savedResults [data-open='a2']").count() == 1)

    # T2 create a plan (online)
    page.click("nav button[data-page='plans']")
    page.click("#newPlan")
    page.select_option("#planActivity", "a2")
    fill_all(page, partial=True)
    page.click("#completePlan")
    m = page.inner_text("#globalMessage")
    check("T2-b", "FR-03", "Incomplete plan shows a clear message and is not completed",
          "five required sections" in m and page.is_visible("#editor"), m.strip())
    page.click("#saveDraft")
    st = page.locator("#planList .pill").all_inner_texts()
    check("T2-c", "FR-03", "Incomplete plan can be kept as a draft", "Draft" in st, ", ".join(st))
    page.click("#planList [data-edit]")
    fill_all(page)
    page.click("#completePlan")
    st = page.locator("#planList .pill").all_inner_texts()
    check("T2-a", "FR-03", "A plan with all five fields completes and is queued",
          any(s.startswith("Pending") for s in st), ", ".join(st))
    ids = page.eval_on_selector_all("#planForm input, #planForm textarea, #planForm select", "els=>els.map(e=>e.id)")
    bad = [i for i in ids if any(k in i.lower() for k in ("name", "email", "phone", "learner", "pupil"))]
    check("T2-d", "PR-01", "Plan form has no name, email or phone field (participation count only)", not bad, ", ".join(ids))

    # T3 connection lost mid-edit, then sync failure and recovery
    page.evaluate("localStorage.clear()"); page.reload()
    page.click("nav button[data-page='plans']")
    page.click("#networkBtn")  # offline
    page.click("#newPlan")
    page.select_option("#planActivity", "a1")
    fill_all(page)
    page.reload()  # simulates the app closing after connection loss
    page.click("nav button[data-page='plans']")
    listed = page.locator("#planList [data-edit]").count()
    check("T3-a", "QR-03", "After connection loss mid-edit and a reload, the draft is listed", listed == 1,
          "draft listed" if listed else "no draft after reload (typed text was lost)")
    if listed:
        page.click("#planList [data-edit]")
        vals = [page.input_value(s) for s in ("#steps", "#timing", "#planMaterials", "#safety", "#inclusion")]
        check("T3-b", "QR-03", "Reopening the draft shows all previously typed fields", all(vals))
        page.click("#networkBtn")  # offline again (reload resets to online)
        page.click("#completePlan")
    else:
        check("T3-b", "QR-03", "Reopening the draft shows all previously typed fields", False, "no draft to reopen")
        page.click("#networkBtn")
        page.click("#newPlan"); page.select_option("#planActivity", "a1"); fill_all(page)
        page.click("#completePlan")
    st = page.inner_text("#planList .pill")
    pill_offline = page.inner_text("#syncPill")
    page.click("#networkBtn")  # reconnect
    retry = page.locator("#planList [data-retry]").count()
    check("T3-c", "FR-04", "Plan completed offline shows a Retry sync button after reconnecting", retry == 1, "status " + st)
    check("T3-d", "FR-04", "Status bar tells the user action is needed while a plan is waiting",
          "action needed" in pill_offline, pill_offline)
    if retry:
        page.evaluate("window.forceFail=true")
        page.click("#planList [data-retry]")
        m1 = page.inner_text("#globalMessage").strip(); st1 = page.inner_text("#planList .pill")
        page.click("#planList [data-retry]")
        st2 = page.inner_text("#planList .pill")
        check("T3-e", "FR-04", "Forced failed sync is explained, the plan stays on the device, and Retry recovers it",
              st1 == "Failed" and "remains on this device" in m1 and st2 == "Synced", f"{m1} | {st1} -> {st2}")
    else:
        check("T3-e", "FR-04", "Forced failed sync is explained, the plan stays on the device, and Retry recovers it",
              False, "no Retry sync button for a plan completed offline")
    page.click("#newPlan"); page.select_option("#planActivity", "a4"); fill_all(page)
    page.click("#networkBtn"); page.click("#completePlan")
    r = page.locator("#planList [data-retry]").count()
    if r:
        page.locator("#planList [data-retry]").first.click()
        m = page.inner_text("#globalMessage").strip(); stx = page.locator("#planList .pill").first.inner_text()
        check("T3-g", "FR-04", "Retry while offline fails safely: message shown and the plan stays on the device",
              stx == "Failed" and "safe on this device" in m, f"{m} | {stx}")
    else:
        check("T3-g", "FR-04", "Retry while offline fails safely: message shown and the plan stays on the device", False, "no Retry sync button")
    page.click("#networkBtn")
    rec("NOTE", "T3-f", "FR-04", "How a failed sync is triggered",
        "No visible control: a failure is shown by retrying while offline, or forced with window.forceFail in the console.")

    # T4 shared-device sign-out
    page.click("#newPlan"); page.select_option("#planActivity", "a3"); fill_all(page)
    page.click("#networkBtn")  # offline
    page.click("#completePlan")
    dialog = {}
    page.once("dialog", lambda d: (dialog.setdefault("m", d.message), d.accept()))
    page.click("nav button[data-page='account']")
    page.click("#signOut")
    cleared = page.evaluate("localStorage.getItem('stem_plans')") is None
    check("T4-a", "SR-02", "Sign-out warns about unsynced work and clears local data",
          dialog.get("m", "").startswith("Warning: you have unsynced plans") and cleared, dialog.get("m", "")[:60])
    page.click("nav button[data-page='plans']")
    check("T4-b", "SR-02", "After sign-out, plan content is hidden until signing in again",
          "Sign in to view" in page.inner_text("#planList"))
    rec("NOTE", "T4-c", "SR-01", "Second facilitator cannot see the first one's plans",
        "Not demonstrable: one simulated account (Facilitator A) and shared storage keys, as the on-screen limitation says.")

    # Static checks (AR-03)
    page.evaluate("localStorage.clear()"); page.reload()
    unlabeled = page.evaluate("""[...document.querySelectorAll('input,select,textarea')].filter(e=>!(e.labels&&e.labels.length)&&!e.getAttribute('aria-label')).map(e=>e.id)""")
    check("S-1", "AR-03", "Every form control has an associated label", not unlabeled, ", ".join(unlabeled))
    check("S-2", "AR-03", "Page language is set", bool(page.get_attribute("html", "lang")), page.get_attribute("html", "lang") or "")
    live = page.evaluate("""[...document.querySelectorAll('[aria-live]')].map(e=>e.id||e.tagName)""")
    check("S-3", "AR-03", "Status and error messages are in live regions with text", "globalMessage" in live, ", ".join(live))
    bad = page.evaluate("""[...document.querySelectorAll('[onclick]')].filter(e=>!['BUTTON','A','INPUT'].includes(e.tagName)).length""")
    check("S-4", "AR-03", "Actions use native buttons (no click handlers on non-interactive elements)", bad == 0)
    b.close()

def main(files):
    os.chdir(os.path.dirname(os.path.abspath(files[0])) or ".")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler)
    handler.log_message = lambda *a: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("", PORT), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    results.append("STEMMate prototype scripted checks (Playwright, headless Chromium). Tasks T1-T4 against the\n"
                   "Team Design Baseline acceptance indicators. Technical walkthrough of the code, not user testing.")
    with sync_playwright() as pw:
        for f in files:
            start = len(results)
            run_file(pw, os.path.basename(f))
            sec = results[start:]
            p = sum(l.startswith("PASS") for l in sec); fl = sum(l.startswith("FAIL") for l in sec); n = sum(l.startswith("NOTE") for l in sec)
            results.append(f"\nSummary: {p} pass, {fl} fail, {n} observations")
    srv.shutdown()
    print("\n".join(results))

if __name__ == "__main__":
    main(sys.argv[1:])
