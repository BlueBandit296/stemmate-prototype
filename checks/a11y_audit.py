import sys, http.server, socketserver, threading, functools, json
from playwright.sync_api import sync_playwright
import random; PORT=random.randint(20000,40000); f=sys.argv[1]
h=functools.partial(http.server.SimpleHTTPRequestHandler); h.log_message=lambda *a:None
socketserver.TCPServer.allow_reuse_address=True
srv=socketserver.TCPServer(("",PORT),h); threading.Thread(target=srv.serve_forever,daemon=True).start()
JS_CONTRAST="""(()=>{
function rgb(s){const m=s.match(/[\\d.]+/g);return m?m.map(Number):[0,0,0,0]}
function lum(c){const a=c.slice(0,3).map(v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)});return .2126*a[0]+.7152*a[1]+.0722*a[2]}
function bg(el){while(el){const c=rgb(getComputedStyle(el).backgroundColor);if(c.length<4||c[3]>0)return c;el=el.parentElement}return [255,255,255]}
const out=[];const seen=new Set();
document.querySelectorAll('body *').forEach(el=>{if(!el.offsetParent&&el.tagName!=='BODY')return;
 const t=[...el.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim()).map(n=>n.textContent.trim()).join(' ');if(!t)return;
 const cs=getComputedStyle(el);const fg=rgb(cs.color),b=bg(el);const L1=lum(fg),L2=lum(b);const r=(Math.max(L1,L2)+.05)/(Math.min(L1,L2)+.05);
 const size=parseFloat(cs.fontSize),bold=parseInt(cs.fontWeight)>=700;const large=size>=24||(bold&&size>=18.66);
 const key=cs.color+'|'+b.join(',')+'|'+large; if(seen.has(key))return;seen.add(key);
 out.push({sample:t.slice(0,40),fg:cs.color,bg:'rgb('+b.slice(0,3).join(',')+')',ratio:Math.round(r*100)/100,need:large?3:4.5,size})});
return out})()"""
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1280,"height":900}); pg.set_default_timeout(5000)
    pg.goto(f"http://localhost:{PORT}/{f}"); pg.evaluate("localStorage.clear()"); pg.reload()
    res={}
    pg.click("[data-open='a2']")
    res["contrast_normal"]=pg.evaluate(JS_CONTRAST)
    pg.click("#contrast"); res["contrast_high"]=pg.evaluate(JS_CONTRAST); pg.click("#contrast")
    pg.reload(); res["contrast_btn_aria_pressed_initial"]=pg.get_attribute("#contrast","aria-pressed")
    # non-text contrast: input borders & focus outline
    res["input_border"]=pg.evaluate("getComputedStyle(document.querySelector('#level')).borderColor+' width '+getComputedStyle(document.querySelector('#level')).borderWidth")
    # keyboard tab order
    order=[]
    for i in range(30):
        pg.keyboard.press("Tab")
        info=pg.evaluate("""(()=>{const e=document.activeElement;const cs=getComputedStyle(e);return {t:(e.innerText||e.id||e.tagName).trim().slice(0,30),outline:cs.outlineStyle+' '+cs.outlineWidth+' '+cs.outlineColor}})()""")
        order.append(info)
    res["tab_order"]=order
    # target sizes
    res["small_targets"]=pg.evaluate("""[...document.querySelectorAll('button,select,input,textarea')].filter(e=>e.offsetParent).map(e=>{const r=e.getBoundingClientRect();return [(e.innerText||e.id).trim().slice(0,25),Math.round(r.width),Math.round(r.height)]}).filter(x=>x[1]<24||x[2]<24)""")
    res["min_target"]=pg.evaluate("""Math.min(...[...document.querySelectorAll('button,select')].filter(e=>e.offsetParent).map(e=>e.getBoundingClientRect().height))""")
    # text size max
    for i in range(10): pg.click("#textUp")
    res["max_root_font_px"]=pg.evaluate("getComputedStyle(document.documentElement).fontSize")
    res["overflow_at_max_text_1280"]=pg.evaluate("document.documentElement.scrollWidth>document.documentElement.clientWidth")
    # reflow at 320 css px (=400% of 1280)
    for w in (640,320):
        pg2=b.new_page(viewport={"width":w,"height":800}); pg2.set_default_timeout(5000); pg2.goto(f"http://localhost:{PORT}/{f}")
        for page_id in ("browse","saved","plans","account"):
            pg2.click(f"nav button[data-page='{page_id}']")
            if page_id=="plans": pg2.click("#newPlan")
            res[f"hscroll_{w}_{page_id}"]=pg2.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
        pg2.screenshot(path=f"reflow_{w}.png",full_page=False); pg2.close()
    # 200% text via browser-like zoom: 640px viewport with A+ max
    pg3=b.new_page(viewport={"width":640,"height":800}); pg3.set_default_timeout(5000); pg3.goto(f"http://localhost:{PORT}/{f}")
    for i in range(10): pg3.click("#textUp")
    res["hscroll_640_maxtext"]=pg3.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
    # text spacing 1.4.12
    pg3.add_style_tag(content="*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}")
    res["hscroll_640_textspacing"]=pg3.evaluate("document.documentElement.scrollWidth-document.documentElement.clientWidth")
    # validation behaviour
    pg.click("nav button[data-page='plans']"); pg.click("#newPlan"); pg.fill("#steps","x"); pg.click("#completePlan")
    res["after_incomplete_submit"]={"globalMessage":pg.inner_text("#globalMessage"),"focused":pg.evaluate("document.activeElement.id"),"validationMessage":pg.evaluate("document.activeElement.validationMessage"),"aria_invalid":pg.evaluate("[...document.querySelectorAll('[aria-invalid]')].map(e=>e.id)")}
    # focus after navigation
    pg.click("nav button[data-page='saved']"); res["focus_after_nav"]=pg.evaluate("document.activeElement.innerText||document.activeElement.id")
    # headings
    res["headings"]=pg.evaluate("[...document.querySelectorAll('h1,h2,h3')].filter(e=>e.offsetParent).map(e=>e.tagName+':'+e.innerText.slice(0,30))")
    res["contrast_btn_text"]=pg.inner_text("#contrast")
    b.close()
srv.shutdown()
print(json.dumps(res,indent=1,ensure_ascii=False))
