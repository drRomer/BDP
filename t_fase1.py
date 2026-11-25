import asyncio, sys, os, json
from playwright.async_api import async_playwright
from PIL import Image
SRC='/home/claude/brigada/out/index.html'; TST='/home/claude/brigada/out/index_test.html'; SH='/home/claude/brigada/shots'
h=open(SRC,encoding='utf-8').read()
hook="window.__T={G:()=>G,startGame,state:()=>state,save:()=>save};\nboot();"
assert h.count('\nboot();')==1
open(TST,'w',encoding='utf-8').write(h.replace('\nboot();','\n'+hook))
LV=int(sys.argv[1]) if len(sys.argv)>1 else 3
async def main():
    async with async_playwright() as p:
        br=await p.chromium.launch(executable_path='/usr/bin/google-chrome',args=['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
        ctx=await br.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True)
        await ctx.add_init_script("localStorage.setItem('brigada-puente-v1',JSON.stringify({level:%d,coins:5000,best:%d,muted:true,up:{}}))"%(LV,LV))
        pg=await ctx.new_page(); errs=[]
        pg.on('pageerror',lambda e:errs.append(str(e)))
        pg.on('console',lambda m:errs.append(m.text) if m.type=='error' else None)
        await pg.goto('file://'+TST)
        await pg.wait_for_function("document.getElementById('loadScr').classList.contains('hidden')",timeout=60000)
        await pg.click('#bPlay'); await pg.wait_for_timeout(2500)
        await pg.screenshot(path=SH+'/f1_wall.png')
        crops=[]
        for wid in (sys.argv[2].split(',') if len(sys.argv)>2 else ['mini','fire','gren','elec','plas']):
            await pg.evaluate("""(wid)=>{const G=__T.G();const W={mini:['MINIGUN','255,214,110','#ffd45a'],fire:['LANZALLAMAS','255,130,40','#ff7a2a'],gren:['LANZAGRANADAS','150,230,90','#9be35a'],elec:['ELECTROCAÑÓN','120,190,255','#78bfff'],plas:['CAÑÓN DE PLASMA','255,110,255','#ff6bff']}[wid];
              clearInterval(window.__iv);G.zombies.length=0;for(let i=0;i<14;i++)G.zombies.push({x:(i%5-2)*1.3,z:G.squad.z+4+Math.floor(i/5)*1.7,sp:0.01,hp:1e6,max:1e6,br:false,run:false,ph:i,off:0,pal:0,hit:0,dead:false,kd:2,sz:0});const z0=G.squad.z;window.__iv=setInterval(()=>{G.squad.z=z0;G.zombies.forEach(z=>{z.hp=Math.min(1e6,z.hp);});},16);
              G.tw={w:{id:wid,name:W[0],col:W[1],hex:W[2]},t:9,max:10,acc:0,cd:0};}""",wid)
            await pg.wait_for_timeout(int(sys.argv[3]) if len(sys.argv)>3 else 900)
            await pg.screenshot(path=SH+'/f1_%s.png'%wid)
            dmg=await pg.evaluate("()=>__T.G().zombies.reduce((a,z)=>a+(1e6-z.hp),0)")
            print(wid,'daño total',round(dmg),await pg.evaluate("()=>{const G=__T.G();return [G.phase,G.soldiers.length,G.zombies.length,G.bullets.length,G.tw&&G.tw.t.toFixed(1),G.zombies[0]&&G.zombies[0].z-G.squad.z]}"))
            crops.append(Image.open(SH+'/f1_%s.png'%wid).crop((60,750,720,1330)).resize((330,290)))
            if wid=='fire':Image.open(SH+'/f1_fire.png').crop((0,300,780,1100)).save(SH+'/f1_fire_big.png')
        m=Image.new('RGB',(330*5,290))
        for i,c in enumerate(crops):m.paste(c,(i*330,0))
        m.save(SH+'/f1_weapons.png')
        # HUD y fps
        fps=await pg.evaluate("()=>new Promise(r=>{let n=0,t0=performance.now();const f=()=>{n++;if(performance.now()-t0>3000)r(n/3);else requestAnimationFrame(f);};requestAnimationFrame(f);})")
        print('fps',round(fps,1)); print('errores',errs[:5])
asyncio.run(main())
