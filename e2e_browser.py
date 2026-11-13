from playwright.sync_api import sync_playwright
import json, sys
B="http://127.0.0.1:5055/"
errs=[]
def newpage(br):
    ctx=br.new_context(); pg=ctx.new_page()
    pg.on("pageerror",lambda e:errs.append(str(e)))
    pg.on("console",lambda m:errs.append(m.text) if m.type=="error" else None)
    pg.goto(B); pg.wait_for_timeout(600); return pg
with sync_playwright() as p:
    br=p.chromium.launch()
    # ---- citizen
    a=newpage(br)
    st=a.evaluate("Object.keys(INDIA_LOCATIONS)[0]"); 
    a.fill("#an","Asha Rao"); a.fill("#ac","asha@example.com"); a.fill("#aph","9876543210"); a.fill("#ap","password123")
    a.select_option("#astate",st); a.wait_for_timeout(200)
    city=a.evaluate("document.querySelectorAll('#acity option')[1].value"); a.select_option("#acity",city); a.wait_for_timeout(200)
    loc=a.evaluate("document.querySelectorAll('#alocality option')[1].value"); a.select_option("#alocality",loc)
    a.click("#af button[type=submit]"); a.wait_for_timeout(800)
    txt=a.inner_text("#account"); print("verify screen has demo code:", "your code is" in txt)
    code=a.evaluate("demoCode"); a.fill("#av",code); a.click("#vf button[type=submit]"); a.wait_for_timeout(800)
    print("after verify, who:", a.inner_text("#who"))
    a.fill("#in","Street light not working near Market Road"); a.click("#f .send-btn"); a.wait_for_timeout(2500)
    a.get_by_role("button",name="Yes").first.click(); a.wait_for_timeout(2500)
    log=a.inner_text("#log"); print("chat tail:", log[-300:].replace("\n"," | "))
    tid=[t for t in a.evaluate("tickets") if t.get("owner")][0]["id"]; print("created", tid)
    # ---- official signs up (pending)
    o=newpage(br)
    o.select_option("#ar","official"); o.wait_for_timeout(200)
    o.fill("#an","Ravi Kumar"); o.fill("#ac","ravi@hubli.gov.in"); o.fill("#aph","9111111111"); o.fill("#ap","password123")
    o.fill("#ae","EMP1234"); o.set_input_files("#apf",{"name":"id.pdf","mimeType":"application/pdf","buffer":b"x"})
    o.click("#af button[type=submit]"); o.wait_for_timeout(800)
    print("official pending:", "Pending review" in o.inner_text("#account"))
    print("official dashboard blocked:", o.evaluate("isOff()"))
    # ---- admin approves
    d=newpage(br); d.click("[data-a=mode]"); d.fill("#ac","admin@dhawani.test"); d.fill("#ap","adminpass123")
    d.click("#af button[type=submit]"); d.wait_for_timeout(1000)
    d.click("#acct"); d.wait_for_timeout(1000)
    print("admin sees pending:", "Ravi Kumar" in d.inner_text("#account"))
    d.click("[data-a=apu]"); d.wait_for_timeout(800)
    # ---- official re-logs in, opens dashboard, changes status
    o.reload(); o.wait_for_timeout(1200)
    print("official verified after reload:", o.evaluate("isOff()"))
    o.evaluate("go('officials')"); o.wait_for_timeout(500)
    o.select_option(f"select[data-id='{tid}']","Resolved"); o.wait_for_timeout(1200)
    # ---- citizen on another device sees status
    a.evaluate("loadTickets()"); a.wait_for_timeout(800)
    print("citizen sees:", [t["status"] for t in a.evaluate("tickets") if t["id"]==tid])
    a.evaluate(f"trackShow('{tid}')"); print("track ok:", tid in a.inner_text("#tres"))
    # ---- guest can track, cannot file; logout works
    g=newpage(br); g.click("[data-a=guest]"); g.wait_for_timeout(500)
    g.evaluate(f"trackShow('{tid}')"); print("guest track:", tid in g.inner_text("#tres"))
    br.close()
print("JS errors:", errs)
