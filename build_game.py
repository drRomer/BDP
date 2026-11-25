"""Build Brigada del Puente index.html with the new baked sheets and animation code.
usage: build_game.py [out.html]
"""
import json, base64, io, os, sys, re
from PIL import Image

SRC = '/home/claude/brigada/src'
SH = '/home/claude/brigada/out/sheets'
OUT = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/brigada/out/index.html'
GUARD_HSTAND = 9.19

base = open(os.path.join(SRC, 'index_orig.html'), encoding='utf-8').read().split('\n')
assert base[150].startswith('window.__BAKED=')
old_baked = json.loads(base[150][len('window.__BAKED='):].rstrip(';'))
# cabecera (CSS/HTML) y juego editables: src/head.html y src/game.js (index_orig.html solo aporta los sprites viejos)
HEAD = open(os.path.join(SRC, 'head.html'), encoding='utf-8').read().split('\n')
lines = HEAD + base[150:152] + open(os.path.join(SRC, 'game.js'), encoding='utf-8').read().split('\n')
NH = len(HEAD)


def webp(path, q=80):
    im = path if isinstance(path, Image.Image) else Image.open(path).convert('RGBA')
    bio = io.BytesIO(); im.save(bio, 'WEBP', quality=q, method=6, alpha_quality=85)
    return 'data:image/webp;base64,' + base64.b64encode(bio.getvalue()).decode()


PACK_STATS = []
def pack_sheet(path, m, e, gap=2, maxw=4096):
    """Recorta cada cuadro a su contenido y los empaqueta en estantes (sin espacio vacío).
    Agrega rx,ry,rw,rh (rectángulo en la hoja) y tx,ty (desplazamiento dentro de la celda original)."""
    import numpy as np
    im = Image.open(path).convert('RGBA'); A = np.asarray(im)
    fw, fh, n = m['fw'], m['fh'], m['n']; cols = m.get('cols', n)
    boxes = []
    for f in range(n):
        x0, y0 = (f % cols) * fw, (f // cols) * fh
        ys, xs = np.where(A[y0:y0 + fh, x0:x0 + fw, 3] > 1)
        if not len(xs): boxes.append((f, x0, y0, 0, 0, 0, 0)); continue
        bx0, bx1 = max(0, xs.min() - 1), min(fw, xs.max() + 2); by0, by1 = max(0, ys.min() - 1), min(fh, ys.max() + 2)
        boxes.append((f, x0, y0, bx0, by0, bx1 - bx0, by1 - by0))
    order = sorted([b for b in boxes if b[5]], key=lambda b: -b[6])
    best = None
    for W in range(1024, maxw + 1, 64):
        x = y = rowh = 0; pos = {}
        for b in order:
            if x + b[5] > W: x = 0; y += rowh + gap; rowh = 0
            pos[b[0]] = (x, y); x += b[5] + gap; rowh = max(rowh, b[6])
        Hh = y + rowh
        if Hh <= 4096 and (best is None or W * Hh < best[0]): best = (W * Hh, W, Hh, pos)
    _, W, Hh, pos = best
    out = Image.new('RGBA', (W, Hh), (0, 0, 0, 0))
    rx, ry, rw, rh, tx, ty = [], [], [], [], [], []
    for (f, x0, y0, bx, by, w, h) in boxes:
        if w:
            px, py = pos[f]; out.paste(im.crop((x0 + bx, y0 + by, x0 + bx + w, y0 + by + h)), (px, py))
        else: px = py = 0
        rx.append(int(px)); ry.append(int(py)); rw.append(int(w)); rh.append(int(h)); tx.append(int(bx)); ty.append(int(by))
    e.update(rx=rx, ry=ry, rw=rw, rh=rh, tx=tx, ty=ty)
    PACK_STATS.append((os.path.basename(path), im.size[0] * im.size[1], W * Hh))
    return out


baked = {}
H = {'sol0': 1.12, 'sol1': 1.12, 'zom0': 1.08, 'zom1': 1.08, 'zom2': 1.08, 'zom3': 1.08, 'zom4': 1.08}
for key in ['sol0', 'sol1', 'zom0', 'zom1', 'zom2', 'zom3', 'zom4', 'titan_walk', 'titan_atk', 'titan_swipe', 'titan_rise', 'guard_walk', 'guard_stand', 'guard_atk']:
    m = json.load(open(os.path.join(SH, key + '.json')))
    e = {k: m[k] for k in ('fw', 'fh', 'ax', 'ay', 'top', 'n', 'cols') if k in m}
    for k in ('axs', 'ays', 'mxs', 'mys', 'impF', 'mx', 'my'):
        if k in m: e[k] = m[k]
    e['h'] = H.get(key, 0)
    e['white'] = key.startswith('zom')
    if key == 'guard_atk':
        f = GUARD_HSTAND / m['h_model']
        e['imp'] = [round(m['impW'][0] * f, 2), round(m['impW'][1] * f, 2)]
    big = key.startswith(('titan', 'guard'))
    src = pack_sheet(os.path.join(SH, key + '.png'), m, e) if big else os.path.join(SH, key + '.png')
    e['src'] = webp(src, 80 if big else 82)
    baked[key] = e
# brute: keep previous sheets until the new model arrives
for k in ('bru0', 'bru1', 'brup0', 'brup1'):
    if os.path.exists(os.path.join(SH, k + '.json')):
        m = json.load(open(os.path.join(SH, k + '.json')))
        e = {kk: m[kk] for kk in ('fw', 'fh', 'ax', 'ay', 'top', 'n', 'cols') if kk in m}; e['h'] = 2.1; e['white'] = True
        e['src'] = webp(pack_sheet(os.path.join(SH, k + '.png'), m, e), 82); baked[k] = e

js = '\n'.join(lines[NH + 2:])


def rep(a, b, cnt=1):
    global js
    c = js.count(a)
    assert c == cnt, (a[:90], c)
    js = js.replace(a, b)


# ---------- loader: grids, per-frame anchors, no canvas copy for big sheets ----------
rep("""    im.onload=()=>{try{const c=mk(im.width,im.height);c.getContext('2d').drawImage(im,0,0);
      const S={img:c,fw:b.fw,fh:b.fh,n:Math.round(im.width/b.fw),ax:b.ax,ay:b.ay,top:b.top,mx:b.mx,my:b.my,mxs:b.mxs,mys:b.mys,k:b.h/Math.max(10,b.ay-b.top)};
      if(b.white)S.white=silhouette(c,'#fff');BSPR[key]=S;}catch(e){}fin();};""",
    """    im.onload=()=>{let wait=false;try{let c=im;if(b.white||!b.cols){c=mk(im.width,im.height);c.getContext('2d').drawImage(im,0,0);}
      const n=b.n||Math.round(im.width/b.fw);
      const S={img:c,fw:b.fw,fh:b.fh,n,cols:b.cols||n,ax:b.ax,ay:b.ay,axs:b.axs,ays:b.ays,top:b.top,mx:b.mx,my:b.my,mxs:b.mxs,mys:b.mys,impF:b.impF,imp:b.imp,rx:b.rx,ry:b.ry,rw:b.rw,rh:b.rh,tx:b.tx,ty:b.ty,k:b.h/Math.max(10,b.ay-b.top)};
      if(b.white)S.white=silhouette(c,'#fff');BSPR[key]=S;
      // hojas grandes: decodificar ya (ImageBitmap) para que no se decodifiquen en plena partida
      if(c===im&&typeof createImageBitmap==='function'){wait=true;createImageBitmap(im).then(bm=>{S.img=bm;fin();},()=>fin());}}catch(e){}if(!wait)fin();};""")
rep("function bakedSet(pre){", """function warmGPU(){ // sube todas las hojas a la GPU durante la carga
  ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=.01;
  const L=Object.values(BSPR).map(S=>S&&S.img);if(TEX.ground)L.push(TEX.ground.c);
  for(const im of L){if(!im)continue;try{ctx.drawImage(im,0,0,Math.min(4,im.width),Math.min(4,im.height),0,0,1,1);}catch(e){}}
  ctx.restore();
}
function bakedSet(pre){""")

# frame helpers + blit
rep("""function blit(S,fr,x,y,sc,white){const k=S.k*PJ.s*(sc||1);ctx.drawImage(white?S.white:S.img,fr*S.fw,0,S.fw,S.fh,x-S.ax*k,y-S.ay*k,S.fw*k,S.fh*k);}""",
    """function frXY(S,fr){if(S.rx)return [S.rx[fr],S.ry[fr]];const c=S.cols||S.n;return [(fr%c)*S.fw,((fr/c)|0)*S.fh];}
function frA(S,fr){return [S.axs?S.axs[fr]:S.ax,S.ays?S.ays[fr]:S.ay];}
function blit(S,fr,x,y,sc,white){const k=S.k*PJ.s*(sc||1),[sx,sy]=frXY(S,fr),[ax,ay]=frA(S,fr),im=white?S.white:S.img;
  if(S.rx){const w=S.rw[fr],h=S.rh[fr];if(w>0)ctx.drawImage(im,sx,sy,w,h,x+(S.tx[fr]-ax)*k,y+(S.ty[fr]-ay)*k,w*k,h*k);return;}
  ctx.drawImage(im,sx,sy,S.fw,S.fh,x-ax*k,y-ay*k,S.fw*k,S.fh*k);}
/* dibuja un cuadro en coordenadas locales (ya escaladas) con su ancla propia */
function drawFr(S,fr,kl,img){const [sx,sy]=frXY(S,fr),[ax,ay]=frA(S,fr);
  if(S.rx){const w=S.rw[fr],h=S.rh[fr];if(w>0)ctx.drawImage(img||S.img,sx,sy,w,h,(S.tx[fr]-ax)*kl,(S.ty[fr]-ay)*kl,w*kl,h*kl);return;}
  ctx.drawImage(img||S.img,sx,sy,S.fw,S.fh,-ax*kl,-ay*kl,S.fw*kl,S.fh*kl);}
/* fundido corto entre animaciones: o = objeto con estado, S/fr = cuadro actual */
const XF=.15;
function drawXF(o,S,fr,kl){
  if(o._cs&&o._cs!==S){o._ps=o._cs;o._pf=o._cf;o._xt=T;}
  o._cs=S;o._cf=fr;
  const a=o._ps?1-(T-o._xt)/XF:0;
  if(a>0){const ga=ctx.globalAlpha;ctx.globalAlpha=ga*a*.9;drawFr(o._ps,o._pf,kl);ctx.globalAlpha=ga;}else o._ps=null;
  drawFr(S,fr,kl);
}""")

# soldiers / zombies / corpses: frame count per sheet
rep("""  const sc=s.pop>0?1-s.pop/.3*.6:1,S=SPR.sol[s.v%SPR.sol.length];
  const fr=G.squad.sp<.6?0:(((s.ph/TAU*NF)|0)%NF+NF)%NF;""",
    """  const sc=s.pop>0?1-s.pop/.3*.6:1,S=SPR.sol[s.v%SPR.sol.length],nf=S.n||NF;
  const fr=G.squad.sp<.6?0:(((s.ph/TAU*nf)|0)%nf+nf)%nf;""")
rep("""  const fr=(((z.ph/TAU*NF)|0)%NF+NF)%NF,S=z.br?SPR.bru[z.pal%SPR.bru.length]:SPR.zom[z.pal%SPR.zom.length];
  blit(S,fr,PJ.x,PJ.y);""",
    """  const S=z.br?SPR.bru[z.pal%SPR.bru.length]:SPR.zom[z.pal%SPR.zom.length],nf=S.n||NF,fr=(((z.ph/TAU*nf)|0)%nf+nf)%nf;
  blit(S,fr,PJ.x,PJ.y);""")
rep("""  const k=c.t/.55,fr=(((c.ph/TAU*NF)|0)%NF+NF)%NF,S=c.br?SPR.bru[c.pal%SPR.bru.length]:SPR.zom[c.pal%SPR.zom.length],q=S.k*PJ.s;
  ctx.save();ctx.globalAlpha=Math.max(0,1-k);ctx.translate(PJ.x,PJ.y);ctx.rotate(c.side*k*.9);ctx.scale(1,1-k*.55);
  ctx.drawImage(S.img,fr*S.fw,0,S.fw,S.fh,-S.ax*q,-S.ay*q,S.fw*q,S.fh*q);ctx.restore();""",
    """  const k=c.t/.55,S=c.br?SPR.bru[c.pal%SPR.bru.length]:SPR.zom[c.pal%SPR.zom.length],nf=S.n||NF,fr=(((c.ph/TAU*nf)|0)%nf+nf)%nf,q=S.k*PJ.s;
  ctx.save();ctx.globalAlpha=Math.max(0,1-k);ctx.translate(PJ.x,PJ.y);ctx.rotate(c.side*k*.9);ctx.scale(1,1-k*.55);
  drawFr(S,fr,q);ctx.restore();""")

# ---------- applyBaked: new Titán / Guardián sets ----------
rep("""  if(BSPR.titan_walk&&BSPR.titan_raise){const w=BSPR.titan_walk;SPR.titan={walk:w,raise:BSPR.titan_raise,kl:10.4/Math.max(10,w.ay-w.top)};}
  if(BSPR.guard_stand&&BSPR.guard_walk&&BSPR.guard_raise){const w=BSPR.guard_walk,st=BSPR.guard_stand,kl=GUARD_HSTAND/Math.max(10,w.ay-w.top);
    SPR.guard3={stand:st,walk:w,raise:BSPR.guard_raise,kl,cs:clamp((st.ay-st.top)*kl/7.5*1.18,.72,1)};}""",
    """  if(BSPR.titan_walk&&BSPR.titan_atk){const w=BSPR.titan_walk;SPR.titan={walk:w,atk:BSPR.titan_atk,swipe:BSPR.titan_swipe,rise:BSPR.titan_rise,kl:10.4/Math.max(10,w.ay-w.top)};}
  if(BSPR.guard_stand&&BSPR.guard_walk&&BSPR.guard_atk){const w=BSPR.guard_walk,st=BSPR.guard_stand,kl=GUARD_HSTAND/Math.max(10,w.ay-w.top),h0=(st.ays?st.ays[0]:st.ay)-1;
    SPR.guard3={stand:st,walk:w,atk:BSPR.guard_atk,kl,cs:clamp(h0*kl/7.5*1.18,.72,1)};}""")

# ---------- Guardián: golpe completo con recuperación ----------
rep("""      if(gd.raiseT>0){gd.raiseT-=dt;gd.raise=Math.min(1,gd.raise+dt*2.6);if(gd.raiseT<=0)guardSlam();}
      else{gd.raise=Math.max(0,gd.raise-dt*7);gd.atk-=dt;if(gd.atk<=0&&(G.phase==='run'||G.phase==='boss'))guardPick();}""",
    """      if(gd.raiseT>0){if(!gd.raiseT0)gd.raiseT0=gd.raiseT;gd.raiseT-=dt;gd.raise=Math.min(1,gd.raise+dt*2.6);if(gd.raiseT<=0){guardSlam();gd.raiseT0=0;gd.rec=GUARD_REC;}}
      else{if(gd.rec>0)gd.rec-=dt;gd.raise=Math.max(0,gd.raise-dt*7);gd.atk-=dt;if(gd.atk<=0&&(G.phase==='run'||G.phase==='boss'))guardPick();}""")
rep("gd.tgt={x:b.x,z:b.z-1.8,boss:true};gd.raiseT=.55;gd.atk=2.4;return;", "gd.tgt={x:b.x,z:b.z-1.8,boss:true};gd.raiseT=.65;gd.atk=2.4;return;")
rep("gd.tgt={x:clamp(best.x,-4.6,3.4),z:best.z-best.sp*.9};gd.raiseT=.5;gd.atk=2.6;return;", "gd.tgt={x:clamp(best.x,-4.6,3.4),z:best.z-best.sp*1.05};gd.raiseT=.6;gd.atk=2.6;return;")
rep("if(cr){gd.tgt={x:cr.x,z:cr.z};gd.raiseT=.5;gd.atk=2.6;return;}", "if(cr){gd.tgt={x:cr.x,z:cr.z};gd.raiseT=.6;gd.atk=2.6;return;}")
rep("const ox=gd.x+3.9*GUARD_K,oz=gd.z-.6,dist=Math.hypot(t.x-ox,t.z-oz);",
    "const im=SPR.guard3&&SPR.guard3.atk&&SPR.guard3.atk.imp,ox=gd.x+(im?im[0]:3.9)*GUARD_K,oz=gd.z+(im?im[1]*GUARD_K:-.6),dist=Math.hypot(t.x-ox,t.z-oz);")
rep("const GUARD_X=-7.9,","const GUARD_X=-7.5,")
rep("gd.x+=(-7.1-gd.x)*Math.min(1,dt*1.5);","gd.x+=(-3.8-gd.x)*Math.min(1,dt*1.5);")
rep("const GUARD_HSTAND=9.19;", "const GUARD_HSTAND=9.19,GUARD_REC=.95,BOSS_REC=.7,BOSS_RISE=1.5,BOSS_SWIPE=1.2;")
rep("""    if(gd.st==='ally'){if(gd.raise>.02){S=GG.raise;fr=Math.min(S.n-1,Math.round(ease(gd.raise)*(S.n-1)));}else{S=GG.walk;fr=(((gd.walk*S.n)|0)%S.n+S.n)%S.n;}}
    else{S=GG.stand;fr=gd.st==='wake'?Math.min(S.n-1,Math.round((1-gd.kneel)*(S.n-1))):0;}
    const dx=-S.ax*kl,dy=-S.ay*kl,dw=S.fw*kl,dh=S.fh*kl;
    if(gd.st==='lost')ctx.globalAlpha=.85;
    ctx.drawImage(S.img,fr*S.fw,0,S.fw,S.fh,dx,dy,dw,dh);
    if(gd.flash>0&&gd.st!=='lock'){ctx.globalCompositeOperation='lighter';ctx.globalAlpha=.3;ctx.drawImage(S.img,fr*S.fw,0,S.fw,S.fh,dx,dy,dw,dh);ctx.globalCompositeOperation='source-over';}""",
    """    if(gd.st==='ally'){const A=GG.atk,ip=A.impF;
      if(gd.raiseT>0&&gd.raiseT0){S=A;fr=Math.min(ip,Math.round((1-gd.raiseT/gd.raiseT0)*ip));}
      else if(gd.rec>0){S=A;const u=Math.max(0,(1-gd.rec/GUARD_REC-.12)/.88);fr=Math.min(A.n-1,ip+Math.round(u*(A.n-1-ip)));} // pausa breve en el impacto: se siente el peso
      else{S=GG.walk;fr=(((gd.walk*S.n)|0)%S.n+S.n)%S.n;}}
    else{S=GG.stand;fr=gd.st==='wake'?Math.min(S.n-1,Math.round((1-gd.kneel)*(S.n-1))):0;}
    if(gd.st==='lost')ctx.globalAlpha=.85;
    drawXF(gd,S,fr,kl);
    if(gd.flash>0&&gd.st!=='lock'){ctx.globalCompositeOperation='lighter';ctx.globalAlpha=.3;drawFr(S,fr,kl);ctx.globalCompositeOperation='source-over';}""")

# ---------- Titán: levantarse, salto completo, manotazo ----------
rep("function startBoss(){const b=G.boss;b.st='fight';b.atk=2.4;b.sum=6;sfx.roar();shake=.5;buzz(80);}",
    "function startBoss(){const b=G.boss;b.st='fight';b.atk=2.4;b.sum=6;b.rise=BOSS_RISE;sfx.roar();shake=.5;buzz(80);}")
rep("""    if(b.raiseT>0){b.raiseT-=dt;b.raise=Math.min(1,b.raise+dt*3);if(b.raiseT<=0){shake=.6;sfx.quake();buzz(90);dust(b.x-2.5*BOSS_K,b.z-1,8,1.6);dust(b.x+2.5*BOSS_K,b.z-1,8,1.6);}}
    else{b.raise=Math.max(0,b.raise-dt*6);b.z-=b.spd*dt;b.walk+=dt*2.2;b.x+=clamp(sq.x*.4-b.x,-1,1)*dt*.6;}""",
    """    if(b.rise>0)b.rise-=dt;
    if(b.sw>0)b.sw-=dt;
    if(b.raiseT>0){if(!b.raiseT0)b.raiseT0=b.raiseT;b.raiseT-=dt;b.raise=Math.min(1,b.raise+dt*3);if(b.raiseT<=0){b.raiseT0=0;b.rec=BOSS_REC;shake=.6;sfx.quake();buzz(90);dust(b.x-2.5*BOSS_K,b.z-1,8,1.6);dust(b.x+2.5*BOSS_K,b.z-1,8,1.6);}}
    else if(b.rise>0){b.raise=0;}
    else{if(b.rec>0)b.rec-=dt;b.raise=Math.max(0,b.raise-dt*6);const mv=b.rec>0?(b.rec<BOSS_REC*.5?.6:0):1.12;b.z-=b.spd*dt*mv;b.walk+=dt*2.2*Math.min(1,mv);b.x+=clamp(sq.x*.4-b.x,-1,1)*dt*.6*mv;}""")
rep("    if(b.atk<=0&&b.raiseT<=0){b.atk=Math.max(2.2,3.8-.12*G.lv);b.raiseT=.9;",
    "    if(b.atk<=0&&b.raiseT<=0&&!(b.rise>0)){b.atk=Math.max(2.2,3.8-.12*G.lv);b.raiseT=.9;")
rep("    if(b.z-sq.z<4.2&&G.soldiers.length){removeSoldiers(G.soldiers.length);shake=1.2;sfx.quake();b.raise=1;}",
    "    if(b.z-sq.z<4.2&&G.soldiers.length){removeSoldiers(G.soldiers.length);shake=1.2;sfx.quake();b.raise=1;b.sw=BOSS_SWIPE;b.raiseT=0;b.raiseT0=0;b.rec=0;}")
rep("""  const TT=SPR.titan,kl=TT.kl;let S,fr;
  if(b.raise>.02){S=TT.raise;fr=Math.min(S.n-1,Math.round(ease(b.raise)*(S.n-1)));}else{S=TT.walk;fr=(((b.walk/TAU*S.n)|0)%S.n+S.n)%S.n;}
  const dx=-S.ax*kl,dy=-S.ay*kl,dw=S.fw*kl,dh=S.fh*kl;
  ctx.drawImage(S.img,fr*S.fw,0,S.fw,S.fh,dx,dy,dw,dh);
  if(b.flash>0){ctx.globalCompositeOperation='lighter';ctx.globalAlpha*=.3;ctx.drawImage(S.img,fr*S.fw,0,S.fw,S.fh,dx,dy,dw,dh);ctx.globalCompositeOperation='source-over';}
  const pu=.55+.3*Math.sin(b.t*6),gx=S.mxs?(S.mxs[fr]-S.ax)*kl:0,gy=S.mys?(S.mys[fr]-S.ay)*kl:-4.3,gr=S.mxs?1.5:2.2;""",
    """  const TT=SPR.titan,kl=TT.kl;let S,fr;const A=TT.atk;
  if(b.st==='idle'&&TT.rise){S=TT.rise;fr=0;}
  else if(b.rise>0&&TT.rise){S=TT.rise;fr=Math.min(S.n-1,Math.round((1-b.rise/BOSS_RISE)*(S.n-1)));}
  else if(b.sw>0&&TT.swipe){S=TT.swipe;fr=Math.min(S.n-1,Math.round((1-b.sw/BOSS_SWIPE)*(S.n-1)));}
  else if(b.raiseT>0&&b.raiseT0){S=A;fr=Math.min(A.impF,Math.round((1-b.raiseT/b.raiseT0)*A.impF));}
  else if(b.rec>0){S=A;fr=Math.min(A.n-1,A.impF+Math.round((1-b.rec/BOSS_REC)*(A.n-1-A.impF)));}
  else{S=TT.walk;fr=(((b.walk/TAU*S.n)|0)%S.n+S.n)%S.n;}
  drawXF(b,S,fr,kl);
  if(b.flash>0){ctx.globalCompositeOperation='lighter';ctx.globalAlpha*=.3;drawFr(S,fr,kl);ctx.globalCompositeOperation='source-over';}
  const [fax,fay]=frA(S,fr),pu=.55+.3*Math.sin(b.t*6),gx=S.mxs?(S.mxs[fr]-fax)*kl:0,gy=S.mys?(S.mys[fr]-fay)*kl:-4.3,gr=S.mxs?1.5:2.2;""")


# ---------- Bruto: se detiene y lanza golpes cuando tiene soldados al alcance ----------
rep("const GUARD_HSTAND=9.19,", "const BRU_PUNCH=.82,BRU_HITS=[.215,.535],GUARD_HSTAND=9.19,")
rep("""    z.z-=z.sp*dt;z.ph+=dt*(z.br?5.4:z.sp*2.6+1.2);
    const dz=z.z-sq.z;
    if(dz<18){const tx=sq.x+z.off;z.x+=clamp(tx-z.x,-1,1)*z.sp*.5*dt;}""",
    """    const punching=z.br&&z.pT>=0;
    if(z.br&&SPR.brup&&SPR.brup.length){
      if(punching){const t0=z.pT;z.pT+=dt;for(const h of BRU_HITS)if(t0<h&&z.pT>=h){bruHit(z);if(z.dead)break;}
        if(z.dead)continue;if(z.pT>=BRU_PUNCH)z.pT=bruReach(z)?z.pT-BRU_PUNCH:-1;}
      else if(bruReach(z))z.pT=0;}
    if(!(z.br&&z.pT>=0)){z.z-=z.sp*dt;z.ph+=dt*(z.br?5.4:z.sp*2.6+1.2);}
    const dz=z.z-sq.z;
    if(dz<18&&!(z.br&&z.pT>=0)){const tx=sq.x+z.off;z.x+=clamp(tx-z.x,-1,1)*z.sp*.5*dt;}""")
rep("function updZombies(dt){",
    """function bruReach(z){for(const s of G.soldiers){const d=z.z-s.wz;if(Math.abs(s.wx-z.x)<1.5&&d>-.3&&d<3.2)return true;}return false;}
function bruHit(z){const S=G.soldiers;let bi=-1,bd=1e9;
  for(let i=0;i<S.length;i++){const s=S[i],dx=Math.abs(s.wx-z.x),d=z.z-s.wz;if(dx<1.7&&d>-.4&&d<3.4){const q=dx+Math.abs(d-1.4);if(q<bd){bd=q;bi=i;}}}
  if(bi<0)return;const s=S[bi];burst(s.wx,.9,s.wz,10,'255,190,120');dust(s.wx,s.wz,2,.7);killSoldierAt(bi);shake=Math.max(shake,.18);buzz(15);
  z.hp-=z.max*.2;z.hit=.07;if(z.hp<=0)killZombie(z,false);}
function updZombies(dt){""")
rep("""  const S=z.br?SPR.bru[z.pal%SPR.bru.length]:SPR.zom[z.pal%SPR.zom.length],nf=S.n||NF,fr=(((z.ph/TAU*nf)|0)%nf+nf)%nf;
  blit(S,fr,PJ.x,PJ.y);""",
    """  let S=z.br?SPR.bru[z.pal%SPR.bru.length]:SPR.zom[z.pal%SPR.zom.length],nf=S.n||NF,fr=(((z.ph/TAU*nf)|0)%nf+nf)%nf;
  if(z.br&&z.pT>=0&&SPR.brup&&SPR.brup.length){S=SPR.brup[z.pal%SPR.brup.length];fr=Math.min(S.n-1,(z.pT/BRU_PUNCH*S.n)|0);}
  blit(S,fr,PJ.x,PJ.y);""")
rep("  const s=bakedSet('sol'),z=bakedSet('zom'),b=bakedSet('bru');if(s.length)SPR.sol=s;if(z.length)SPR.zom=z;if(b.length)SPR.bru=b;",
    "  const s=bakedSet('sol'),z=bakedSet('zom'),b=bakedSet('bru'),bp=bakedSet('brup');if(s.length)SPR.sol=s;if(z.length)SPR.zom=z;if(b.length)SPR.bru=b;\n  if(bp.length&&b.length){bp.forEach((P,i)=>{P.k=b[i%b.length].k;});SPR.brup=bp;}")


# ---------- Utilería horneada desde los modelos de Tripo ----------
PM = json.load(open('/home/claude/brigada/out/props/props.json'))
for k, m in PM.items():
    e = {'fw': 1, 'fh': 1, 'ax': 0, 'ay': 0, 'top': 0, 'n': 1, 'cols': 1, 'h': 0, 'prop': 1}
    e.update({kk: (v if isinstance(v, list) else float(v)) for kk, v in m.items()})
    e['src'] = webp('/home/claude/brigada/out/props/%s.png' % k, 82)
    baked['prop_' + k] = e
rep("""function buildProps(){
  PROPS.cars=[propCar(['#c45a4c','#8f3a30','#5a221c']),propCar(['#dfe2e4','#a4a9ae','#6c7177']),propCar(['#5f7b95','#3d566e','#253546'])];
  PROPS.barrier=propBarrier();PROPS.cone=propCone();PROPS.barrel=propBarrel();PROPS.bags=propSandbags();
}""", """function buildProps(){
  PROPS.cars=[propCar(['#c45a4c','#8f3a30','#5a221c']),propCar(['#dfe2e4','#a4a9ae','#6c7177']),propCar(['#5f7b95','#3d566e','#253546'])];
  PROPS.barrier=propBarrier();PROPS.cone=propCone();PROPS.barrel=propBarrel();PROPS.bags=propSandbags();
}
/* reemplaza la utilería dibujada por las versiones horneadas de los modelos 3D */
function applyBakedProps(){
  const P=k=>{const b=BAKED['prop_'+k],S=BSPR['prop_'+k];return b&&S?{img:S.img,w:b.w,h:b.h,axf:b.axf,ayf:b.ayf,hxf:b.hxf,hyf:b.hyf}:null;};
  const cars=['sedanA','sedanB','pickupA','pickupB','sedanA','pickupB','truck'].map(P).filter(Boolean);if(cars.length)PROPS.cars=cars;
  const ba=[P('barrierA'),P('barrierB')].filter(Boolean);if(ba.length)PROPS.barriers=ba;
  for(const k of ['cone','barrel','bags']){const p=P(k);if(p)PROPS[k]=p;}
  PROPS.lampL=P('lampL');PROPS.lampR=P('lampR');
}""")
rep("    if(r<.3)pr=PROPS.cars[(Math.random()*3)|0];else if(r<.5)pr=PROPS.barrier;",
    "    if(r<.3)pr=PROPS.cars[(Math.random()*PROPS.cars.length)|0];else if(r<.5)pr=PROPS.barriers?PROPS.barriers[(Math.random()*PROPS.barriers.length)|0]:PROPS.barrier;")
rep("""function drawProp(o){
  if(!proj(o.x,WALK_Y,o.z))return;const p=o.p,h=p.h*PJ.s,w=p.w*PJ.s;
  ctx.drawImage(p.img,PJ.x-w/2,PJ.y-h*.95,w,h);
}""", """function drawProp(o){
  if(!proj(o.x,WALK_Y,o.z))return;const p=o.p,h=p.h*PJ.s,w=p.w*PJ.s;
  ctx.drawImage(p.img,PJ.x-w*(p.axf!=null?p.axf:.5),PJ.y-h*(p.ayf!=null?p.ayf:.95),w,h);
}
// torre del puente: los pedestales bajan hasta el agua (TOWER_DEPTH bajo el tablero), con reflejo y espuma en la línea de flotación
const TOWER_DEPTH=5.2,TOWER_CUT=.95,TOWER_SLICE=.9;
function towerPeds(p){if(p.ped)return p.ped;p.ped=[[.18,.36],[.81,.36]];
  try{const c=p.img,g=c.getContext&&c.getContext('2d');if(!g)return p.ped;const y=Math.round(c.height*.93),d=g.getImageData(0,y,c.width,1).data,R=[];let a=-1;
    for(let x=0;x<=c.width;x++){const on=x<c.width&&d[x*4+3]>128;if(on&&a<0)a=x;if(!on&&a>=0){if(x-a>c.width*.08)R.push([(a+x)/2/c.width,(x-a)/c.width]);a=-1;}}
    if(R.length)p.ped=R;}catch(e){}return p.ped;}
function towerPier(p){if(p.pier!==undefined)return p.pier;p.pier=null;
  try{const I=p.img,iw=I.width,ih=I.height,r0=Math.round(ih*.855),r1=Math.round(ih*TOWER_CUT),bh=r1-r0,eh=Math.round(iw*(TOWER_DEPTH+WALK_Y)/p.w)+4;
    const c=mk(iw,eh),g=c.getContext('2d');
    for(let y=0,k=0;y<eh;y+=bh,k++){g.save();if(k%2===0){g.translate(0,y+bh);g.scale(1,-1);g.drawImage(I,0,r0,iw,bh,0,0,iw,bh);}else g.drawImage(I,0,r0,iw,bh,0,y,iw,bh);g.restore();}
    g.globalCompositeOperation='source-atop';const gr=g.createLinearGradient(0,0,0,eh);
    gr.addColorStop(0,'rgba(10,16,24,0)');gr.addColorStop(.55,'rgba(10,16,24,.12)');gr.addColorStop(.9,'rgba(10,18,26,.38)');gr.addColorStop(1,'rgba(6,12,18,.55)');
    g.fillStyle=gr;g.fillRect(0,0,iw,eh);p.pier=c;}catch(e){}return p.pier;}
function drawTower(o){
  const p=o.p,I=p.img;if(!proj(o.x,WALK_Y,o.z))return;const s=PJ.s,h=p.h*s,w=p.w*s,ayf=p.ayf!=null?p.ayf:.95,x0=PJ.x-w*(p.axf!=null?p.axf:.5),y0=PJ.y-h*ayf,xb=PJ.x;
  // la torre es una imagen plana: el pedestal baja recto (sin inclinación) para no quebrarse
  if(!proj(o.x,-TOWER_DEPTH,o.z))return;const xw=xb,yw=PJ.y,sw=PJ.s;
  const yc=y0+h*TOWER_CUT,k=0,iw=I.width,ih=I.height,t=G.time||0,PD=towerPeds(p),lw=Math.max(.8,sw*.06);
  const ring=(cx,rx,ry,a0,a1)=>{ctx.beginPath();ctx.ellipse(cx,yw,rx,ry,0,a0,a1);ctx.stroke();};
  // el tablero más cercano tapa la base: se recorta la zona del puente por delante de la torre
  const L=o.x<0,ex=L?WALK_L:WALK_R;ctx.save();
  if(proj(ex,1.0,o.z)){const P1x=PJ.x,P1y=PJ.y;proj(ex,1.0,cam.z+2);const t=(H+200-P1y)/Math.max(1,PJ.y-P1y),P2x=P1x+(PJ.x-P1x)*t,P2y=H+200,X=L?W+200:-200;
    ctx.beginPath();ctx.rect(-200,-200,W+400,H+400);ctx.moveTo(P1x,P1y);ctx.lineTo(P2x,P2y);ctx.lineTo(X,P2y);ctx.lineTo(X,P1y);ctx.closePath();ctx.clip('evenodd');}
  // reflejo en el agua: la mitad baja de la torre, invertida y aplastada
  ctx.save();ctx.globalAlpha=.2;ctx.translate(xw,yw);ctx.transform(1,0,-k*.55,-.55,0,0);
  ctx.drawImage(I,0,ih*.5,iw,ih*(TOWER_CUT-.5),x0-xb,-h*(TOWER_CUT-.5),w,h*(TOWER_CUT-.5));ctx.restore();
  // agua alrededor de cada pedestal: sombra de contacto, ondas y la mitad trasera de la espuma
  for(let i=0;i<PD.length;i++){const cx=xw+x0-xb+w*PD[i][0],rx=w*PD[i][1]*.62,ry=rx*.45;
    ctx.fillStyle='rgba(6,14,26,.38)';ctx.beginPath();ctx.ellipse(cx,yw,rx*1.12,ry*1.15,0,0,TAU);ctx.fill();
    for(let j=0;j<2;j++){const q=(t*.35+j*.5+i*.27)%1;ctx.strokeStyle='rgba(205,225,242,'+((1-q)*.2).toFixed(3)+')';ctx.lineWidth=Math.max(.7,sw*.045);ring(cx,rx*(1.1+q*.75),ry*(1.1+q*.75),0,TAU);}
    ctx.strokeStyle='rgba(225,238,248,.28)';ctx.lineWidth=lw;ring(cx,rx,ry,Math.PI,TAU);}
  // pedestal alargado hasta el agua, inclinado según la perspectiva
  const PI=towerPier(p);
  if(PI){const ph=Math.max(1,yw-yc+1.5),sh=Math.min(PI.height,PI.width*ph/w);ctx.drawImage(PI,0,0,PI.width,sh,x0,yc-1,w,ph);}
  else ctx.drawImage(I,0,ih*TOWER_SLICE,iw,ih*(TOWER_CUT-TOWER_SLICE),x0,yc-1,w,yw-yc+1.5);
  // torre
  ctx.drawImage(I,0,0,iw,ih*TOWER_CUT,x0,y0,w,h*TOWER_CUT+.5);
  // espuma delante de cada pedestal
  ctx.strokeStyle='rgba(235,244,252,.42)';ctx.lineWidth=lw;
  for(let i=0;i<PD.length;i++){const cx=xw+x0-xb+w*PD[i][0],rx=w*PD[i][1]*.62;ring(cx,rx,rx*.45,0,Math.PI);}
  ctx.restore();
}""")
rep("case 10:drawProp(e);break;", "case 10:if(e.p===PROPS.tower)drawTower(e);else drawProp(e);break;")
rep("""function drawLamp(l){
  if(!proj(l.x,1.0,l.z))return;""", """function drawLamp(l){
  const LP=l.x>0?PROPS.lampR:PROPS.lampL;
  if(LP){if(!proj(l.x,WALK_Y,l.z))return;const w=LP.w*PJ.s,h=LP.h*PJ.s,x0=PJ.x-w*LP.axf,y0=PJ.y-h*LP.ayf;ctx.drawImage(LP.img,x0,y0,w,h);
    if(SCN.pal.night){const hx=x0+w*LP.hxf,hy=y0+h*(LP.hyf+.03),s=PJ.s;ctx.globalCompositeOperation='lighter';const g=ctx.createRadialGradient(hx,hy,0,hx,hy,s*1.5);g.addColorStop(0,'rgba(255,210,140,.55)');g.addColorStop(1,'rgba(255,210,140,0)');ctx.fillStyle=g;ctx.fillRect(hx-s*1.5,hy-s*1.5,s*3,s*3);ctx.globalCompositeOperation='source-over';}
    return;}
  if(!proj(l.x,1.0,l.z))return;""")
rep("  loadBaked(()=>build3D(ok=>{if(!ok)buildSprites();applyBaked();READY=true;",
    "  loadBaked(()=>build3D(ok=>{if(!ok)buildSprites();applyBaked();applyBakedProps();warmGPU();READY=true;")

# ---------- Muerte del Titán: se desploma, se recalienta y estalla en rocas ----------
rep("""  if(b.st==='dying'){b.dieT+=dt;if(Math.random()<.6)burst(b.x+rnd(-4,4),rnd(2,12),b.z-1,4,'255,200,120');if(Math.random()<.25)dust(b.x+rnd(-4,4),b.z,2,1.5);if(b.dieT>2.2)b.st='dead';}""",
    """  if(b.st==='dying'){const t0=b.dieT;b.dieT+=dt;const K=BOSS_K,t=b.dieT;
    if(t<TDIE_BOOM){const heat=Math.min(1,t/TDIE_BOOM);
      if(Math.random()<.35+heat*.5)part({x:b.x+rnd(-3,3)*K,y:rnd(1.5,8)*K*(t<TDIE_FALL?1:.6),z:b.z-1,vx:rnd(-2,2),vy:rnd(1,4),vz:rnd(-1,1),l:rnd(.4,.8),m:.6,sz:rnd(.08,.18),c:'255,'+((120+Math.random()*90)|0)+',40',t:0});
      if(Math.random()<.25)debris(b.x+rnd(-2.5,2.5)*K,rnd(2,7)*K,b.z-1,1,'80,72,66');
      if(t0<TDIE_FALL&&t>=TDIE_FALL){shake=Math.max(shake,.9);sfx.quake();buzz(60);dust(b.x-2.2*K,b.z-1,10,2);dust(b.x+2.2*K,b.z-1,10,2);debris(b.x,1,b.z-1,14,'90,82,74');}
      if(t>TDIE_FALL)shake=Math.max(shake,.25*heat);}
    if(t0<TDIE_BOOM&&t>=TDIE_BOOM){shake=1.6;G.flashScr=.35;sfx.boom();buzz(200);
      for(let i=0;i<70;i++)part({x:b.x+rnd(-2,2)*K,y:rnd(1,6)*K,z:b.z-1+rnd(-.5,.5),vx:rnd(-9,9),vy:rnd(3,14),vz:rnd(-5,4),l:rnd(.8,1.5),m:1.2,sz:rnd(.25,.7),c:Math.random()<.35?'255,'+((90+Math.random()*80)|0)+',30':(Math.random()<.5?'86,78,70':'60,54,50'),t:2});
      for(let i=0;i<50;i++)part({x:b.x+rnd(-1.5,1.5)*K,y:rnd(2,6)*K,z:b.z-1,vx:rnd(-7,7),vy:rnd(2,10),vz:rnd(-3,3),l:rnd(.5,1),m:.8,sz:rnd(.15,.35),c:'255,'+((150+Math.random()*90)|0)+',60',t:0});
      for(let i=0;i<4;i++)dust(b.x+rnd(-3,3)*K,b.z-1+rnd(-1,1),8,2.6,rnd(.5,3));}
    if(t>TDIE_BOOM&&Math.random()<.4)dust(b.x+rnd(-3,3)*K,b.z-1,1,2.2,rnd(.3,2));
    if(t>TDIE_END)b.st='dead';}""")
rep("GUARD_HSTAND=9.19,GUARD_REC", "TDIE_FALL=.95,TDIE_BOOM=1.55,TDIE_END=2.25,GUARD_HSTAND=9.19,GUARD_REC")
rep("""  if(b.st==='dying'){const k=Math.min(1,b.dieT/1.3);ctx.rotate(k*.4*b.dieDir);ctx.translate(0,k*s*1.2);ctx.globalAlpha=Math.max(0,1-Math.max(0,b.dieT-1.2));}
  ctx.scale(s,s);
  ctx.fillStyle=rg(ctx,0,0,.2,4.8,'rgba(0,0,0,.5)','rgba(0,0,0,0)');el(ctx,0,0,4.8,1.15);ctx.fill();
  const TT=SPR.titan,kl=TT.kl;let S,fr;const A=TT.atk;""",
    """  const dying=b.st==='dying'&&SPR.titan&&SPR.titan.rise,dt2=b.dieT||0;
  if(b.st==='dying'&&!dying){const k=Math.min(1,b.dieT/1.3);ctx.rotate(k*.4*b.dieDir);ctx.translate(0,k*s*1.2);ctx.globalAlpha=Math.max(0,1-Math.max(0,b.dieT-1.2));}
  if(dying){const j=dt2<TDIE_BOOM?(.04+.1*Math.min(1,dt2/TDIE_BOOM))*s:0;ctx.translate(Math.sin(dt2*47)*j,Math.cos(dt2*39)*j*.5);
    if(dt2>TDIE_BOOM){const q=(dt2-TDIE_BOOM)/.3;ctx.globalAlpha=Math.max(0,1-q);ctx.scale(1+q*.12,1-q*.25);}}
  ctx.scale(s,s);
  ctx.fillStyle=rg(ctx,0,0,.2,4.8,'rgba(0,0,0,.5)','rgba(0,0,0,0)');el(ctx,0,0,4.8,1.15);ctx.fill();
  const TT=SPR.titan,kl=TT.kl;let S,fr;const A=TT.atk;""")
rep("""  if(b.st==='idle'&&TT.rise){S=TT.rise;fr=0;}""",
    """  if(dying){S=TT.rise;fr=dt2<TDIE_FALL?Math.round((1-dt2/TDIE_FALL)*(S.n-1)):0;}
  else if(b.st==='idle'&&TT.rise){S=TT.rise;fr=0;}""")
rep("""  if(b.flash>0){ctx.globalCompositeOperation='lighter';ctx.globalAlpha*=.3;drawFr(S,fr,kl);ctx.globalCompositeOperation='source-over';}
  const [fax,fay]=frA(S,fr)""",
    """  if(b.flash>0){ctx.globalCompositeOperation='lighter';ctx.globalAlpha*=.3;drawFr(S,fr,kl);ctx.globalCompositeOperation='source-over';}
  if(dying&&TT.hot&&dt2<TDIE_BOOM+.3){const heat=Math.min(1,Math.max(0,(dt2-.3)/(TDIE_BOOM-.3)))*(.7+.3*Math.sin(dt2*26)),ga=ctx.globalAlpha;ctx.globalCompositeOperation='lighter';ctx.globalAlpha=ga*heat*.75;drawFr(S,fr,kl,TT.hot);ctx.globalAlpha=ga;ctx.globalCompositeOperation='source-over';}
  const [fax,fay]=frA(S,fr)""")
rep("""  if(BSPR.titan_walk&&BSPR.titan_atk){const w=BSPR.titan_walk;SPR.titan={walk:w,atk:BSPR.titan_atk,swipe:BSPR.titan_swipe,rise:BSPR.titan_rise,kl:10.4/Math.max(10,w.ay-w.top)};}""",
    """  if(BSPR.titan_walk&&BSPR.titan_atk){const w=BSPR.titan_walk;SPR.titan={walk:w,atk:BSPR.titan_atk,swipe:BSPR.titan_swipe,rise:BSPR.titan_rise,kl:10.4/Math.max(10,w.ay-w.top)};
    if(SPR.titan.rise){try{SPR.titan.hot=silhouette(SPR.titan.rise.img,'rgb(255,104,26)');}catch(e){}}}""")


# ---------- Escombros con forma de roca (en vez de cuadrados) ----------
rep("""    else{ctx.fillStyle='rgba('+p.c+','+a+')';ctx.fillRect(PJ.x-r,PJ.y-r,r*2,r*1.4);}}""",
    """    else{if(!p.sh){p.sh=[];const k=5+((Math.random()*3)|0);for(let i=0;i<k;i++)p.sh.push(.6+Math.random()*.55);p.ro=Math.random()*TAU;p.vr=rnd(-9,9);p.hot=/^255,/.test(p.c);}
      const ro=p.ro+p.vr*(p.m-p.l),k=p.sh.length;ctx.save();ctx.translate(PJ.x,PJ.y);ctx.rotate(ro);
      if(p.hot)ctx.globalCompositeOperation='lighter';
      ctx.fillStyle='rgba('+p.c+','+a+')';ctx.beginPath();for(let i=0;i<k;i++){const an=i/k*TAU,rr2=r*p.sh[i];ctx.lineTo(Math.cos(an)*rr2,Math.sin(an)*rr2*.8);}ctx.closePath();ctx.fill();
      if(!p.hot){ctx.fillStyle='rgba(255,255,255,'+(a*.16)+')';ctx.beginPath();for(let i=0;i<k;i++){const an=i/k*TAU,rr2=r*p.sh[i]*.55;ctx.lineTo(Math.cos(an)*rr2-r*.18,Math.sin(an)*rr2*.8-r*.18);}ctx.closePath();ctx.fill();}
      ctx.restore();}}""")


# ======================= FX, texturas, utilería 2 =======================
FXM = json.load(open('/home/claude/brigada/out/fx/fx.json'))
for k in ('fire', 'smoke', 'rockL', 'rockC'):
    m = FXM[k]; e = {'fw': m['fw'], 'fh': m['fh'], 'ax': 0, 'ay': 0, 'top': 0, 'n': m['n'], 'cols': m['cols'], 'h': 0}
    e['src'] = webp('/home/claude/brigada/out/fx/%s.png' % k, 84); baked['fx_' + k] = e
for k in ('road', 'walk', 'sky'):
    im = Image.open('/home/claude/brigada/out/tex/%s.png' % k)
    e = {'fw': im.width, 'fh': im.height, 'ax': 0, 'ay': 0, 'top': 0, 'n': 1, 'cols': 1, 'h': 0}
    e['src'] = webp('/home/claude/brigada/out/tex/%s.png' % k, 86); baked['tex_' + k] = e

# sin humo pintado del Guardián ni del Titán
rep("      if(Math.random()<dt*4)for(const sd of [-1,1])smoke(gd.x+sd*1.9*GUARD_K,(5.6+3.2)*GUARD_K,gd.z+.4);\n", "")
rep("    if(Math.random()<dt*3)for(const sd of [-1,1])smoke(b.x+sd*2.4*BOSS_K,7.6*BOSS_K,b.z+.5);\n", "")
# sin la capa naranja sobre el Titán: el núcleo del pecho brilla más fuerte
rep("""  if(dying&&TT.hot&&dt2<TDIE_BOOM+.3){const heat=Math.min(1,Math.max(0,(dt2-.3)/(TDIE_BOOM-.3)))*(.7+.3*Math.sin(dt2*26)),ga=ctx.globalAlpha;ctx.globalCompositeOperation='lighter';ctx.globalAlpha=ga*heat*.75;drawFr(S,fr,kl,TT.hot);ctx.globalAlpha=ga;ctx.globalCompositeOperation='source-over';}""",
    """  const heatD=dying&&dt2<TDIE_BOOM?Math.min(1,Math.max(0,(dt2-.15)/(TDIE_BOOM-.15)))*(.8+.2*Math.sin(dt2*30)):0;""")
rep("gr=S.mxs?1.5:2.2;ctx.globalCompositeOperation='lighter';ctx.fillStyle=rg(ctx,gx,gy,0,gr,'rgba(255,120,60,'+(.45*pu)+')','rgba(255,60,20,0)');",
    "gr=(S.mxs?1.5:2.2)*(1+heatD*2.6);ctx.globalCompositeOperation='lighter';ctx.fillStyle=rg(ctx,gx,gy,0,gr,'rgba(255,'+((120+90*heatD)|0)+','+((60+60*heatD)|0)+','+Math.min(1,.45*pu+heatD*.55)+')','rgba(255,60,20,0)');")
rep("""
    if(SPR.titan.rise){try{SPR.titan.hot=silhouette(SPR.titan.rise.img,'rgb(255,104,26)');}catch(e){}}}""", "}")

# partículas: brillos suaves, humo volumétrico, rocas 3D y bola de fuego
rep("function part(o){if(G.parts.length<750)G.parts.push(o);}",
    """function part(o){if(G.parts.length<750)G.parts.push(o);}
function lavaRocks(x,y,z,n,spd,a,b){for(let i=0;i<n;i++)part({x:x+rnd(-1,1),y:y+rnd(-1,1),z:z+rnd(-.5,.5),vx:rnd(-spd,spd),vy:rnd(spd*.4,spd*1.4),vz:rnd(-spd*.6,spd*.5),l:rnd(.9,1.6),m:1.6,sz:rnd(a,b),c:'80,70,64',t:2,lava:1});}
const GLOWS={};
function glowSprite(r,g,b){const c=mk(64,64),x=c.getContext('2d'),gr=x.createRadialGradient(32,32,0,32,32,32);gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(.2,'rgba('+r+','+g+','+b+',.9)');gr.addColorStop(.5,'rgba('+r+','+g+','+b+',.3)');gr.addColorStop(1,'rgba('+r+','+g+','+b+',0)');x.fillStyle=gr;x.fillRect(0,0,64,64);return c;}
function glowFor(c){let k=GLOWS[c];if(k)return k;const v=c.split(',').map(Number),r=v[0],g=v[1],b=v[2];
  const key=r>200&&b<140?(g>185?'hot':'warm'):(r>200&&g>200&&b>200?'white':'cyan');
  k=GLOWS['_'+key]||(GLOWS['_'+key]=key==='hot'?glowSprite(255,222,150):key==='warm'?glowSprite(255,140,50):key==='white'?glowSprite(240,242,255):glowSprite(140,230,255));GLOWS[c]=k;return k;}""")
rep("p.x+=p.vx*dt;p.y+=p.vy*dt;p.z+=p.vz*dt;if(p.t!==1)p.vy-=12*dt;else{p.sz+=dt*.8;p.vy*=.96;}",
    "p.x+=p.vx*dt;p.y+=p.vy*dt;p.z+=p.vz*dt;if(p.t===4)p.vy*=.98;else if(p.t!==1)p.vy-=12*dt;else{p.sz+=dt*.8;p.vy*=.96;}")
rep("""    if(p.t===0){ctx.globalCompositeOperation='lighter';ctx.fillStyle='rgba('+p.c+','+a+')';ctx.fillRect(PJ.x-r,PJ.y-r,r*2,r*2);ctx.globalCompositeOperation='source-over';}
    else if(p.t===1){ctx.fillStyle='rgba('+p.c+','+(a*.35)+')';ctx.beginPath();ctx.arc(PJ.x,PJ.y,r,0,TAU);ctx.fill();}""",
    """    if(p.t===0){ctx.globalCompositeOperation='lighter';ctx.globalAlpha=Math.min(1,a*1.15);const R=r*2.6;ctx.drawImage(glowFor(p.c),PJ.x-R,PJ.y-R,R*2,R*2);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';}
    else if(p.t===1){const F=BSPR.fx_smoke;if(F){if(p.vi==null){p.vi=(Math.random()*F.n)|0;p.ro=Math.random()*TAU;}const R=r*1.8,[sx,sy]=frXY(F,p.vi);ctx.save();ctx.globalAlpha=a*.55;ctx.translate(PJ.x,PJ.y);ctx.rotate(p.ro+(p.m-p.l)*.35);ctx.drawImage(F.img,sx,sy,F.fw,F.fh,-R,-R,R*2,R*2);ctx.restore();}
      else{ctx.fillStyle='rgba('+p.c+','+(a*.35)+')';ctx.beginPath();ctx.arc(PJ.x,PJ.y,r,0,TAU);ctx.fill();}}
    else if(p.t===4){const FB=BSPR.fx_fire;if(FB){const fr=Math.min(FB.n-1,((1-p.l/p.m)*FB.n)|0),R=p.sz*PJ.s,[sx,sy]=frXY(FB,fr);ctx.drawImage(FB.img,sx,sy,FB.fw,FB.fh,PJ.x-R,PJ.y-R,R*2,R*2);}}""")
rep("""    else{if(!p.sh){p.sh=[];""", """    else if((p.lava?BSPR.fx_rockL:BSPR.fx_rockC)){const RS=p.lava?BSPR.fx_rockL:BSPR.fx_rockC;if(p.vi==null){p.vi=(Math.random()*4)|0;p.ro=Math.random()*TAU;p.vr=rnd(-9,9);}
      const an=p.ro+p.vr*(p.m-p.l),k=((Math.floor(an/TAU*8)%8)+8)%8,R=r*1.35,[sx,sy]=frXY(RS,p.vi*8+k);ctx.globalAlpha=Math.min(1,a*1.6);ctx.drawImage(RS.img,sx,sy,RS.fw,RS.fh,PJ.x-R,PJ.y-R,R*2,R*2);ctx.globalAlpha=1;
      if(p.lava&&a>.5){ctx.globalCompositeOperation='lighter';ctx.globalAlpha=(a-.5)*.9;const G2=glowFor('255,150,50'),Q2=R*1.6;ctx.drawImage(G2,PJ.x-Q2,PJ.y-Q2,Q2*2,Q2*2);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';}}
    else{if(!p.sh){p.sh=[];""")
# muerte del Titán: rocas de lava y bolas de fuego
rep("      if(Math.random()<.25)debris(b.x+rnd(-2.5,2.5)*K,rnd(2,7)*K,b.z-1,1,'80,72,66');",
    "      if(Math.random()<.3)lavaRocks(b.x+rnd(-2.2,2.2)*K,rnd(2,7)*K,b.z-1,1,2.5,.12,.28);")
i0 = js.index("    if(t0<TDIE_BOOM&&t>=TDIE_BOOM){shake=1.6;")
i1 = js.index("    if(t>TDIE_BOOM&&Math.random()<.4)dust(")
js = js[:i0] + """    if(t0<TDIE_BOOM&&t>=TDIE_BOOM){shake=1.6;G.flashScr=.3;sfx.boom();buzz(200);
      part({x:b.x,y:5*K,z:b.z-1.6,vx:0,vy:.9,vz:0,l:1.25,m:1.25,sz:7.2*K,t:4});
      part({x:b.x-2.5*K,y:3.2*K,z:b.z-1.2,vx:-.8,vy:.6,vz:0,l:1.05,m:1.05,sz:4.8*K,t:4});
      part({x:b.x+2.7*K,y:6.8*K,z:b.z-1.3,vx:.7,vy:1,vz:0,l:1.12,m:1.12,sz:5*K,t:4});
      lavaRocks(b.x,5*K,b.z-1,34,9,.3,.8);debris(b.x,1,b.z-1,12,'90,82,74');
      for(let i=0;i<44;i++)part({x:b.x+rnd(-1.5,1.5)*K,y:rnd(2,7)*K,z:b.z-1,vx:rnd(-8,8),vy:rnd(2,11),vz:rnd(-3,3),l:rnd(.5,1.1),m:1.1,sz:rnd(.1,.22),c:'255,'+((140+Math.random()*90)|0)+',60',t:0});
      for(let i=0;i<10;i++)part({x:b.x+rnd(-3,3)*K,y:rnd(.5,6)*K,z:b.z-1+rnd(-1,1),vx:rnd(-1.5,1.5),vy:rnd(.6,2),vz:rnd(-.5,.5),l:rnd(1.6,2.4),m:2.4,sz:rnd(1.4,2.6),c:'110,104,98',t:1});}
""" + js[i1:]

# texturas de asfalto y vereda (proyección por franjas) + skyline de Gemini
rep("function applyBakedProps(){", """const TEX={};let SKYIMG=null;
function zAtRow(Y,dy){const a=(CY+shY-Y)/F,den=a*cosP-sinP;if(den>=-1e-4)return null;return cam.z+dy*(cosP+a*sinP)/den;}
// Suelo texturizado en UNA pasada: asfalto + ambas veredas en un solo lienzo "calcomanía"
// (negro con alfa = 1-luminancia, equivalente exacto a multiplicar por la textura gris),
// una franja por fila de pantalla y composición normal (sin 'multiply', que es lenta en GPU).
const GT={pu:80,per:9.6};
function buildGroundTex(road,walk){
  const pu=GT.pu,x0=WALK_L,wd=Math.round((WALK_R-WALK_L)*pu),per=Math.round(GT.per*pu),ht=per+256,c=mk(wd,ht),g=c.getContext('2d');
  const lay=(img,xa,xb,tile)=>{const tw=tile*pu;g.save();g.beginPath();g.rect(Math.round((xa-x0)*pu),0,Math.round((xb-xa)*pu),ht);g.clip();
    for(let k=Math.floor(xa/tile);k*tile<xb;k++)for(let j=0;j*tw<ht;j++)g.drawImage(img,Math.round((k*tile-x0)*pu),Math.round(j*tw),tw,tw);g.restore();};
  lay(walk,WALK_L,-CURB,2.4);lay(road,-CURB,CURB,3.2);lay(walk,CURB,WALK_R,2.4);
  const d=g.getImageData(0,0,wd,ht),a=d.data,cl=Math.round((-CURB-x0)*pu),cr=Math.round((CURB-x0)*pu);
  for(let y=0;y<ht;y++)for(let x=0;x<wd;x++){const i=(y*wd+x)*4,s=(x>=cl&&x<cr)?.95:.9,l=(a[i]+a[i+1]+a[i+2])/3;a[i]=a[i+1]=a[i+2]=0;a[i+3]=Math.round((255-l)*s);}
  g.putImageData(d,0,0);return {c,per};
}
function texGround(zN,zF){
  const T=TEX.ground;if(!T)return;
  ctx.save();ctx.beginPath();gqa(WALK_L,zN,-CURB,zF,WALK_Y);gqa(-CURB,zN,CURB,zF,0);gqa(CURB,zN,WALK_R,zF,WALK_Y);ctx.clip();ctx.setTransform(1,0,0,1,0,0);
  const D=DPR,dy=-CAM_H,pu=GT.pu;if(!proj(0,0,zN))return ctx.restore();let Yd=Math.round(Math.min(H,PJ.y)*D);proj(0,0,zF);const yTd=Math.round(Math.max(HORY+2,PJ.y)*D);
  while(Yd>yTd){const hh=Math.max(1,Math.min(Math.round(4*D),Math.round((Yd/D-HORY)*.02*D))),z0=zAtRow(Yd/D,dy),z1=zAtRow((Yd-hh)/D,dy);if(z0==null||z1==null)break;
    const fa=Math.min(1,Math.max(0,1-(z0-cam.z-45)/55));if(fa<=.01)break;
    const v1=((-z1/GT.per)%1+1)%1*T.per,sh=Math.min(255,Math.max(.05,(z1-z0)*pu));
    const s=F/((z0-cam.z)*cosP-dy*sinP),ox=CX+shX-cam.x*s,xa=Math.max(WALK_L,-ox/s),xb=Math.min(WALK_R,(W-ox)/s);
    if(xb>xa){ctx.globalAlpha=fa;ctx.drawImage(T.c,(xa-WALK_L)*pu,v1,(xb-xa)*pu,sh,(ox+xa*s)*D,Yd-hh,(xb-xa)*s*D,hh);}Yd-=hh;}
  ctx.restore();
}
function skyFromImg(p){
  const c=mk(1600,320),g=c.getContext('2d');g.drawImage(SKYIMG,0,0,1600,320);
  g.globalCompositeOperation='source-atop';g.globalAlpha=p.night?.8:.34;g.fillStyle=p.night?'#0c1324':p.bld[1];g.fillRect(0,0,1600,320);g.globalAlpha=1;
  const fg=g.createLinearGradient(0,120,0,320);fg.addColorStop(0,'rgba('+p.fog+',0)');fg.addColorStop(1,'rgba('+p.fog+',.7)');g.fillStyle=fg;g.fillRect(0,0,1600,320);g.globalCompositeOperation='source-over';
  const B=[];if(p.night)for(let i=0;i<12;i++)B.push([rnd(40,1560),rnd(110,190)]);return {img:c,beacons:B};
}
function applyBakedProps(){
  if(BSPR.tex_road&&BSPR.tex_walk){try{TEX.ground=buildGroundTex(BSPR.tex_road.img,BSPR.tex_walk.img);}catch(e){}}
  if(BSPR.tex_sky)SKYIMG=BSPR.tex_sky.img;""")
# las veredas se pintan antes de las líneas de la calzada (no se tocan en pantalla) para texturizar todo el suelo en una sola pasada
WALKFILL = "  ctx.fillStyle=p.curbF;if(xq(-CURB,0,WALK_Y,zN,zF))ctx.fill();if(xq(CURB,0,WALK_Y,zN,zF))ctx.fill();\n  if(gq(WALK_L,zN,-CURB,zF,WALK_Y)){const g=ctx.createLinearGradient(0,H,0,HORY);g.addColorStop(0,p.walk);g.addColorStop(1,p.roadF);ctx.fillStyle=g;ctx.fill();}\n  if(gq(CURB,zN,WALK_R,zF,WALK_Y)){ctx.fillStyle=p.walk;ctx.fill();}\n"
rep(WALKFILL, "")
rep("  if(gq(-CURB,zN,CURB,zF)){const g=ctx.createLinearGradient(0,H,0,HORY);g.addColorStop(0,p.road);g.addColorStop(1,p.roadF);ctx.fillStyle=g;ctx.fill();}\n",
    "  if(gq(-CURB,zN,CURB,zF)){const g=ctx.createLinearGradient(0,H,0,HORY);g.addColorStop(0,p.road);g.addColorStop(1,p.roadF);ctx.fillStyle=g;ctx.fill();}\n" + WALKFILL + "  texGround(zN,zF);\n")
rep("  ctx.fillStyle=p.walkD;ctx.beginPath();\n  for(let z=Math.floor(cam.z/2.5)*2.5;", "  ctx.fillStyle=p.walkD;ctx.beginPath();\n  if(!TEX.ground)for(let z=Math.floor(cam.z/2.5)*2.5;")
rep("  const sl=makeSkyline(pal);", "  const sl=SKYIMG?skyFromImg(pal):makeSkyline(pal);")

# utilería nueva: barricadas, señal de peligro y pórtico
rep("  const ba=[P('barrierA'),P('barrierB')].filter(Boolean);if(ba.length)PROPS.barriers=ba;",
    "  const ba=[P('barrierA'),P('barrierB'),P('barricadeA'),P('barricadeB')].filter(Boolean);if(ba.length)PROPS.barriers=ba;\n  PROPS.warn=P('warn');const gp=P('gantry');if(gp){gp.panels=BAKED.prop_gantry.panels;PROPS.gantry=gp;}")
rep("    if(r<.3)pr=PROPS.cars[(Math.random()*PROPS.cars.length)|0];else if(r<.5)pr=PROPS.barriers?PROPS.barriers[(Math.random()*PROPS.barriers.length)|0]:PROPS.barrier;else if(r<.68)pr=PROPS.bags;else if(r<.84)pr=PROPS.barrel;else pr=PROPS.cone;",
    "    if(r<.28)pr=PROPS.cars[(Math.random()*PROPS.cars.length)|0];else if(r<.48)pr=PROPS.barriers?PROPS.barriers[(Math.random()*PROPS.barriers.length)|0]:PROPS.barrier;else if(r<.62)pr=PROPS.bags;else if(r<.75)pr=PROPS.barrel;else if(r<.88)pr=PROPS.cone;else pr=PROPS.warn||PROPS.cone;")
rep("    if(Math.random()<.45){const pr2=Math.random()<.6?PROPS.cone:PROPS.barrel;",
    "    if(Math.random()<.45){const q2=Math.random(),pr2=q2<.5?PROPS.cone:q2<.8?PROPS.barrel:(PROPS.warn||PROPS.cone);")
rep("""function drawGantry(gy){
  const z=gy.z,fa=clamp((z-cam.z-22)/12,0,1);if(fa<=0)return;ctx.globalAlpha=fa;""",
    """function drawGantry(gy){
  const z=gy.z,fa=clamp((z-cam.z-22)/12,0,1);if(fa<=0)return;
  const GP=PROPS.gantry;
  if(GP){if(!proj(.25,0,z))return;ctx.globalAlpha=fa;const w=GP.w*PJ.s,h=GP.h*PJ.s,x0=PJ.x-w*GP.axf,y0=PJ.y-h*GP.ayf;ctx.drawImage(GP.img,x0,y0,w,h);
    const sg=[gy.s,SIGNS[(SIGNS.indexOf(gy.s)+1)%SIGNS.length]];
    if(GP.panels)GP.panels.forEach((q,i)=>{const rx=x0+w*q[0],ry=y0+h*q[1],rw=w*(q[2]-q[0]),rh=h*(q[3]-q[1]),S2=sg[i],k=Math.min(rw*.93/S2.width,rh*.88/S2.height),dw=S2.width*k,dh=S2.height*k;ctx.drawImage(S2,rx+(rw-dw)/2,ry+(rh-dh)/2,dw,dh);});
    ctx.globalAlpha=1;return;}
  ctx.globalAlpha=fa;""")


# ======================= Sonidos realistas, fogonazos, cajas, puertas, chevrón, torres =======================
FXM = json.load(open('/home/claude/brigada/out/fx/fx.json'))
m = FXM['flash']; baked['fx_flash'] = {'fw': m['fw'], 'fh': m['fh'], 'ax': 0, 'ay': 0, 'top': 0, 'n': m['n'], 'cols': m['cols'], 'h': 0, 'cy': m['cy'],
                                     'src': webp('/home/claude/brigada/out/fx/flash.png', 86)}
SFXM = json.load(open('/home/claude/brigada/out/sfx/sfx.json'))
SFX = {k: ['data:audio/mpeg;base64,' + base64.b64encode(open('/home/claude/brigada/out/sfx/' + f, 'rb').read()).decode() for f in v] for k, v in SFXM.items()}
rep("const sfx={\n", """let SFXDATA=(typeof window.__SFX==="object"&&window.__SFX)||null;
function loadSfx(){if(!AU.ctx||AU.loading||!SFXDATA)return;AU.loading=true;AU.buf={};
  for(const k in SFXDATA){AU.buf[k]=[];SFXDATA[k].forEach((u,i)=>{try{const bin=atob(u.split(',')[1]),arr=new Uint8Array(bin.length);for(let j=0;j<bin.length;j++)arr[j]=bin.charCodeAt(j);
    const p=AU.ctx.decodeAudioData(arr.buffer,b=>{AU.buf[k][i]=b;},()=>{});if(p&&p.catch)p.catch(()=>{});}catch(e){}});}}
function playS(name,vol,rate){const c=AU.ctx;if(!c||save.muted||!AU.buf)return false;const L=AU.buf[name];if(!L||!L.length)return false;const b=L[(Math.random()*L.length)|0];if(!b)return false;
  try{const s=c.createBufferSource();s.buffer=b;s.playbackRate.value=rate||1;const g=c.createGain();g.gain.value=vol;s.connect(g);g.connect(AU.master);s.start();return true;}catch(e){return false;}}
const sfx8={
""")
rep("  click(){tone(700,.05,'square',.04);}\n};", """  click(){tone(700,.05,'square',.04);}
};
const SFXV={shot:[.26,.16,.065],kill:[.42,.2,.045],hurt:[.45,.12,.08],good:[.6,0],bad:[.55,0],tick:[.28,.12,.05],tink:[.22,.2,.045],crate:[.7,.08],roar:[.95,.06],quake:[.95,.05],slash:[.65,.05],boom:[1,.03],shatter:[.7,.05],mech:[.7,0],slam:[.85,.08],impact:[.7,.1],win:[.7,0],lose:[.7,0],click:[.45,.1]};
const sfx={};
for(const k in sfx8){const v=SFXV[k]||[.6,.05];sfx[k]=function(){if(v[2]&&!thr('s_'+k,v[2]))return;if(!playS(k,v[0],1+(Math.random()-.5)*v[1]))sfx8[k]();};}""")
rep("    if(AU.ctx.state==='suspended')AU.ctx.resume();", "    if(AU.ctx.state==='suspended')AU.ctx.resume();\n    loadSfx();")

# fogonazos realistas (4 variantes, giro y tamaño al azar)
rep("  for(let i=0;i<Fl.length;i+=3){const r=Fl[i+2]*.42;ctx.drawImage(SPR.flash,Fl[i]-r,Fl[i+1]-r*1.2,r*2,r*2);}",
    "  const FF=BSPR.fx_flash;\n  for(let i=0;i<Fl.length;i+=3){if(FF){const R=Fl[i+2]*(.5+Math.random()*.22),v=(Math.random()*FF.n)|0,cy=(BAKED.fx_flash.cy||.5);ctx.save();ctx.translate(Fl[i],Fl[i+1]);ctx.rotate((Math.random()-.5)*.5);ctx.drawImage(FF.img,v*FF.fw,0,FF.fw,FF.fh,-R,-R*2*cy,R*2,R*2);ctx.restore();}else{const r=Fl[i+2]*.42;ctx.drawImage(SPR.flash,Fl[i]-r,Fl[i+1]-r*1.2,r*2,r*2);}}")

# cajas ARMA / TROPA con los modelos
rep("""function drawCrate(c){
  const a=c.dead?Math.max(0,1-c.ft/.3):1;if(a<=0)return;""", """function drawCrate(c){
  const a=c.dead?Math.max(0,1-c.ft/.3):1;if(a<=0)return;
  const cw=c.type==='w',CP=cw?PROPS.crateW:PROPS.crateM;
  if(CP){if(!proj(c.x,0,c.z))return;ctx.globalAlpha=a;const W2=CP.w*PJ.s,H2=CP.h*PJ.s,x0=PJ.x-W2*CP.axf,y0=PJ.y-H2*CP.ayf;ctx.drawImage(CP.img,x0,y0,W2,H2);
    if(c.fl>0){if(!CP.white)CP.white=silhouette(CP.img,'#fff');ctx.globalAlpha=a*Math.min(.6,c.fl*8);ctx.drawImage(CP.white,x0,y0,W2,H2);ctx.globalAlpha=a;}
    {const fs=Math.max(7,PJ.s*.34);otext(cw?'ARMA':'TROPA',PJ.x,y0+H2*(cw?.66:.7),fs,cw?'#ffe27a':'#e6f3ff','#14181f',.2);}
    const hh=cw?1.15:1.9;
    if(!c.dead&&proj(c.x,hh+.65,c.z)){const fs=Math.max(9,PJ.s*.6),r=fs*.95;
      ctx.fillStyle='rgba(0,0,0,.45)';ctx.beginPath();ctx.arc(PJ.x,PJ.y,r,0,TAU);ctx.fill();
      ctx.strokeStyle=cw?'#ffd34a':'#6fb6ff';ctx.lineWidth=Math.max(2,fs*.16);ctx.beginPath();ctx.arc(PJ.x,PJ.y,r,-Math.PI/2,-Math.PI/2+TAU*c.hp/c.max);ctx.stroke();
      otext(String(Math.ceil(c.hp)),PJ.x,PJ.y,fs*.62,'#fff');}
    ctx.globalAlpha=1;return;}""")

# puertas: marco 3D (pilares a escala, viga estirada) con el vidrio de color por dentro
rep("""  ctx.globalAlpha=a;
  for(const px of [x0,x1]){if(vq(px-.16,0,px+.16,2.5,z)){ctx.fillStyle=lg(ctx,Q[0],0,Q[2],0,'#4d5564','#a6b0bf','#2c323d');ctx.fill();}
    if(vq(px-.2,2.36,px+.2,2.64,z)){ctx.fillStyle='rgb('+col+')';ctx.fill();}}
  if(vq(x0,2.3,x1,2.5,z)){ctx.fillStyle='#262c36';ctx.fill();}
  if(vq(x0+.2,2.36,x1-.2,2.42,z)){ctx.fillStyle='rgba('+col+',.95)';ctx.fill();}""",
    """  ctx.globalAlpha=a;
  const GF=good?(gt.k==='mul'?PROPS.gateM:PROPS.gateA):PROPS.gateB;
  if(!GF){
  for(const px of [x0,x1]){if(vq(px-.16,0,px+.16,2.5,z)){ctx.fillStyle=lg(ctx,Q[0],0,Q[2],0,'#4d5564','#a6b0bf','#2c323d');ctx.fill();}
    if(vq(px-.2,2.36,px+.2,2.64,z)){ctx.fillStyle='rgb('+col+')';ctx.fill();}}
  if(vq(x0,2.3,x1,2.5,z)){ctx.fillStyle='#262c36';ctx.fill();}
  if(vq(x0+.2,2.36,x1-.2,2.42,z)){ctx.fillStyle='rgba('+col+',.95)';ctx.fill();}}""")
rep("""  if(vq(x0+.16,2.02,x1-.16,2.26,z)){ctx.fillStyle='rgba(255,255,255,.2)';ctx.fill();}
  if(proj((x0+x1)/2,1.2,z)){""", """  if(vq(x0+.16,2.02,x1-.16,2.26,z)){ctx.fillStyle='rgba(255,255,255,.2)';ctx.fill();}
  if(GF&&proj(x0-.12,0,z)){const xl=PJ.x,yb=PJ.y,s=PJ.s;proj(x1+.12,0,z);const xr=PJ.x,Hp=GF.h*s,Wn=GF.w*s,iw=GF.img.width,ih=GF.img.height,y0=yb-Hp*GF.ayf;
    const lw=GF.pl*Wn,rw=(1-GF.pr)*Wn;
    ctx.drawImage(GF.img,0,0,iw*GF.pl,ih,xl,y0,lw,Hp);
    ctx.drawImage(GF.img,iw*GF.pl,0,iw*(GF.pr-GF.pl),ih,xl+lw-.5,y0,Math.max(1,xr-xl-lw-rw+1),Hp);
    ctx.drawImage(GF.img,iw*GF.pr,0,iw*(1-GF.pr),ih,xr-rw,y0,rw,Hp);
    ctx.globalCompositeOperation='lighter';ctx.fillStyle='rgba('+col+',.55)';ctx.fillRect(xl+lw*.38,y0+Hp*.32,lw*.24,Hp*.6);ctx.fillRect(xr-rw*.62,y0+Hp*.32,rw*.24,Hp*.6);ctx.fillRect(xl+lw,y0+Hp*.1,xr-xl-lw-rw,Math.max(1,Hp*.02));ctx.globalCompositeOperation='source-over';}
  if(proj((x0+x1)/2,1.2,z)){""")
rep("  PROPS.warn=P('warn');", "  PROPS.warn=P('warn');PROPS.chevron=P('chevron');PROPS.tower=P('tower');PROPS.crateW=P('crateW');PROPS.crateM=P('crateM');if(PROPS.crateW){PROPS.crateW.w*=1.3;PROPS.crateW.h*=1.3;}if(PROPS.crateM){PROPS.crateM.w*=1.25;PROPS.crateM.h*=1.25;}\n  for(const k of ['gateA','gateM','gateB']){const p=P(k);if(p){const b=BAKED['prop_'+k];p.pl=b.pl;p.pr=b.pr;p.bh=b.bh;PROPS[k]=p;}}")
rep("else if(r<.88)pr=PROPS.cone;else pr=PROPS.warn||PROPS.cone;", "else if(r<.86)pr=PROPS.cone;else if(r<.93)pr=PROPS.warn||PROPS.cone;else pr=PROPS.chevron||PROPS.cone;")
rep("const q2=Math.random(),pr2=q2<.5?PROPS.cone:q2<.8?PROPS.barrel:(PROPS.warn||PROPS.cone);", "const q2=Math.random(),pr2=q2<.45?PROPS.cone:q2<.72?PROPS.barrel:q2<.86?(PROPS.warn||PROPS.cone):(PROPS.chevron||PROPS.cone);")
rep("  const gantries=[];", "  if(PROPS.tower)for(let z=110;z<L+260;z+=190){props.push({x:-15.2,z,p:PROPS.tower,kd:10,sz:z});props.push({x:11.8,z:z+95,p:PROPS.tower,kd:10,sz:z+95});}\n  const gantries=[];")

# ---------- plataforma con jaula del Guardián (Tripo) y campo de energía ----------
rep("const GUARD_X=-7.5,","const GUARD_X=-8.0,")
rep("  PROPS.lampL=P('lampL');PROPS.lampR=P('lampR');",
    "  PROPS.lampL=P('lampL');PROPS.lampR=P('lampR');\n  {const V=[20,27,34].map(k=>{const b=BAKED['prop_plat'+k],pl=P('plat'+k),pf=P('platF'+k);return b&&pl&&pf?{p:b.pitch,b:pl,f:pf}:null;}).filter(Boolean),b=BAKED.prop_plat20;\n   if(V.length&&b)PROPS.plat={V,deck:b.deck,beam:b.beam,pil:(b.pil||[]).map(q=>[-q[0],q[1]]).sort((a,c)=>Math.atan2(a[1],a[0])-Math.atan2(c[1],c[0]))};}")
rep("tgt:null,kd:8,sz:gz,slab:true};",
    "tgt:null,kd:8,sz:gz,slab:true,pl:{b:{kd:13,x:GUARD_X,z:gz,sz:gz+6.8},f:{kd:14,x:GUARD_X,z:gz,sz:gz-6.2}}};")
rep("if(G.guard&&G.guard.z>zMin&&G.guard.z<zMax)DL.push(G.guard);",
    "if(G.guard&&G.guard.z>zMin&&G.guard.z<zMax)DL.push(G.guard);\n    {const gp=G.guard&&G.guard.pl;if(gp&&PROPS.plat&&gp.b.z>zMin-8&&gp.b.z<zMax)DL.push(gp.b,gp.f);}")
rep("case 10:if(e.p===PROPS.tower)drawTower(e);else drawProp(e);break;",
    "case 10:if(e.p===PROPS.tower)drawTower(e);else drawProp(e);break;case 13:drawPlat(e,0);break;case 14:drawPlat(e,1);break;")
rep("  ctx.fillStyle=rg(ctx,0,0,.2,6,'rgba(0,0,0,.5)','rgba(0,0,0,0)');el(ctx,0,0,6,1.2);ctx.fill();\n  if(gd.slab){",
    "  const onPlat=gd.slab&&PROPS.plat&&gd.pl;\n  if(!onPlat){ctx.fillStyle=rg(ctx,0,0,.2,6,'rgba(0,0,0,.5)','rgba(0,0,0,0)');el(ctx,0,0,6,1.2);ctx.fill();}\n  if(onPlat)ctx.translate(0,-PROPS.plat.deck*Math.cos(platView(gd.pl.b.z).a*Math.PI/180)/GUARD_K);\n  else if(gd.slab){")
rep("function drawGuardian(gd){\n  if(!proj(gd.x,WALK_Y,gd.z))return;",
    "function drawGuardian(gd){\n  const fld=PROPS.plat&&gd.pl&&(gd.st==='sleep'||gd.st==='lock'||gd.st==='lost'||(gd.st==='wake'&&gd.t<.08));\n  if(fld)drawField(gd,0);\n  if(!proj(gd.x,WALK_Y,gd.z))return;")
rep("  // cristal de sello\n  if(locked||(gd.st==='wake'&&gd.t<.08)){\n    if(gd.slab)ctx.translate(0,1.25);",
    "  // cristal de sello (solo si no hay plataforma con jaula)\n  if(!fld&&(locked||(gd.st==='wake'&&gd.t<.08))){\n    if(gd.slab)ctx.translate(0,1.25);")
rep("  }\n  ctx.restore();\n}\nconst DL=[];",
    """  }
  ctx.restore();
  if(fld)drawField(gd,1);
}
// la jaula se horneó a 3 inclinaciones de cámara; se usa la que corresponde a la distancia (con un fundido breve entre dos)
function platView(z){const V=PROPS.plat.V,a=Math.atan2(CAM_H-WALK_Y,Math.max(1,z-cam.z))*180/Math.PI;
  if(a<=V[0].p)return {i:0,j:0,w:0,a:V[0].p};const L=V.length-1;if(a>=V[L].p)return {i:L,j:L,w:0,a:V[L].p};
  let k=0;while(k<L-1&&a>=V[k+1].p)k++;const t=(a-V[k].p)/(V[k+1].p-V[k].p),w=clamp((t-.4)/.2,0,1);return {i:k,j:k+1,w,a:lerp(V[k].p,V[k+1].p,w)};}
function drawPlat(e,front){if(!PROPS.plat||!proj(e.x,WALK_Y,e.z))return;const v=platView(e.z),bx=PJ.x,by=PJ.y,s=PJ.s,V=PROPS.plat.V;
  const one=(o,al)=>{const p=front?o.f:o.b,h=p.h*s,w=p.w*s;ctx.globalAlpha=al;ctx.drawImage(p.img,bx-w*p.axf,by-h*p.ayf,w,h);};
  one(V[v.i],1);if(v.w>0)one(V[v.j],v.w);ctx.globalAlpha=1;}
// campo de energía entre los pilares de la jaula: caras traseras antes del Guardián, delanteras después (con las grietas de vida)
function drawField(gd,front){
  const PL=PROPS.plat,P=PL.pil,n=P.length;if(n<3)return;
  // mismo espacio que la imagen de la jaula (ortográfica a la inclinación de horneado, escalada en la base) para que calce con los pilares
  if(!proj(gd.pl.b.x,WALK_Y,gd.pl.b.z))return;const bx=PJ.x,by=PJ.y,bs=PJ.s,pa=platView(gd.pl.b.z).a*Math.PI/180,CP=Math.cos(pa),SP=Math.sin(pa);
  const y0=PL.deck+.05,y1=PL.beam-.95,k=.9,lost=gd.st==='lost',fl=gd.flash>0?Math.min(1,gd.flash*4):0;
  const c=lost?'170,180,192':'120,222,255',T0=G.time||0;
  ctx.save();ctx.setTransform(DPR,0,0,DPR,0,0);
  const faces=[];
  for(let i=0;i<n;i++){const a=P[i],b=P[(i+1)%n];if(((a[1]+b[1])/2<0)!==!!front)continue;
    const q=[];for(const [x,y,z] of [[a[0],y0,a[1]],[b[0],y0,b[1]],[b[0],y1,b[1]],[a[0],y1,a[1]]])q.push([bx+x*k*bs,by-(y*CP+z*k*SP)*bs]);
    faces.push(q);}
  const quad=(q,t0,t1)=>{const L=(u,v,t)=>[u[0]+(v[0]-u[0])*t,u[1]+(v[1]-u[1])*t],A=L(q[0],q[3],t0),B=L(q[1],q[2],t0),C=L(q[1],q[2],t1),D=L(q[0],q[3],t1);ctx.beginPath();ctx.moveTo(A[0],A[1]);ctx.lineTo(B[0],B[1]);ctx.lineTo(C[0],C[1]);ctx.lineTo(D[0],D[1]);ctx.closePath();};
  for(const q of faces){
    const g=ctx.createLinearGradient(0,q[0][1],0,q[3][1]);g.addColorStop(0,'rgba('+c+','+(.3+fl*.3)+')');g.addColorStop(.5,'rgba('+c+','+(.12+fl*.25)+')');g.addColorStop(1,'rgba('+c+','+(.2+fl*.3)+')');
    quad(q,0,1);ctx.fillStyle=g;ctx.fill();
    if(!lost){ctx.globalCompositeOperation='lighter';
      for(let j=0;j<2;j++){const t=(T0*.32+j*.5)%1;quad(q,Math.max(0,t-.05),Math.min(1,t+.05));ctx.fillStyle='rgba(170,240,255,.13)';ctx.fill();}
      ctx.strokeStyle='rgba(170,240,255,.18)';ctx.lineWidth=1;for(const t of [.34,.67]){const u=[q[0][0]+(q[1][0]-q[0][0])*t,q[0][1]+(q[1][1]-q[0][1])*t],v=[q[3][0]+(q[2][0]-q[3][0])*t,q[3][1]+(q[2][1]-q[3][1])*t];ctx.beginPath();ctx.moveTo(u[0],u[1]);ctx.lineTo(v[0],v[1]);ctx.stroke();}
      ctx.strokeStyle='rgba(185,245,255,'+(.55+.15*Math.sin(T0*3))+')';ctx.lineWidth=1.6;ctx.beginPath();ctx.moveTo(q[0][0],q[0][1]);ctx.lineTo(q[1][0],q[1][1]);ctx.moveTo(q[3][0],q[3][1]);ctx.lineTo(q[2][0],q[2][1]);ctx.stroke();
      ctx.globalCompositeOperation='source-over';}}
  if(front&&faces.length){let x0=1e9,x1=-1e9,ya=1e9,yb=-1e9;for(const q of faces)for(const p of q){x0=Math.min(x0,p[0]);x1=Math.max(x1,p[0]);ya=Math.min(ya,p[1]);yb=Math.max(yb,p[1]);}
    ctx.beginPath();for(const q of faces){ctx.moveTo(q[0][0],q[0][1]);for(let i=1;i<4;i++)ctx.lineTo(q[i][0],q[i][1]);ctx.closePath();}ctx.clip();
    const frac=1-gd.hp/gd.max,mx=x=>x0+(x+6.2)/12.8*(x1-x0),my=y=>yb+(y-.2)/12.8*(yb-ya);
    ctx.strokeStyle='rgba(255,255,255,.85)';ctx.lineWidth=1.3;
    for(const cr of gd.cracks){if(cr.th>frac)continue;ctx.beginPath();ctx.moveTo(mx(cr.pts[0][0]),my(cr.pts[0][1]));for(let i=1;i<cr.pts.length;i++)ctx.lineTo(mx(cr.pts[i][0]),my(cr.pts[i][1]));ctx.stroke();}}
  ctx.restore();
}
const DL=[];""")
rep("lamps.push({x:-10.05,z,kd:5,sz:z});", "if(!(guardZ&&Math.abs(z-guardZ)<9))lamps.push({x:-10.05,z,kd:5,sz:z});")
rep("props.push({x:-15.2,z,p:PROPS.tower,kd:10,sz:z});", "if(!(guardZ&&Math.abs(z-guardZ)<14))props.push({x:-15.2,z,p:PROPS.tower,kd:10,sz:z});")
# golpe del Guardián a dos manos: carga más larga (giro y martillo sobre la cabeza) y anticipación del blanco acorde
rep("gd.tgt={x:b.x,z:b.z-1.8,boss:true};gd.raiseT=.65;gd.atk=2.4;", "gd.tgt={x:b.x,z:b.z-1.8,boss:true};gd.raiseT=.95;gd.atk=2.6;")
rep("gd.tgt={x:clamp(best.x,-4.6,3.4),z:best.z-best.sp*1.05};gd.raiseT=.6;gd.atk=2.6;", "gd.tgt={x:clamp(best.x,-4.6,3.4),z:best.z-best.sp*1.45};gd.raiseT=.95;gd.atk=2.8;")
rep("gd.tgt={x:cr.x,z:cr.z};gd.raiseT=.6;gd.atk=2.6;", "gd.tgt={x:cr.x,z:cr.z};gd.raiseT=.95;gd.atk=2.8;")
# allBaked / build3D checks referenced old raise sheets only by walk keys -> fine
# ---------- muro lateral con baranda (Tripo): textura continua en perspectiva + tapa de concreto ----------
rep("PROPS.crateW=P('crateW');", "PROPS.wall=P('wall');PROPS.crateW=P('crateW');")
rep("  ctx.fillStyle=p.curbF;if(xq(WALK_L,WALK_Y,1.0,zN,zF))ctx.fill();if(xq(WALK_R,WALK_Y,1.0,zN,zF))ctx.fill();\n",
    "  if(!drawWalls(zN,zF,p)){\n  ctx.fillStyle=p.curbF;if(xq(WALK_L,WALK_Y,1.0,zN,zF))ctx.fill();if(xq(WALK_R,WALK_Y,1.0,zN,zF))ctx.fill();\n")
rep("  ctx.fillStyle='rgba(255,255,255,.14)';for(const x of [WALK_L+.1,WALK_R-.1])if(xq(x,1.88,1.92,zN,zF))ctx.fill();\n",
    "  ctx.fillStyle='rgba(255,255,255,.14)';for(const x of [WALK_L+.1,WALK_R-.1])if(xq(x,1.88,1.92,zN,zF))ctx.fill();\n  }\n")
rep("function drawRoad(){", r"""const WALL_H=1.9, WALL_CAP=1.34, WALL_T=.75, WT=new Map();
function wallTex(p){let t=WT.get(p);if(t!==undefined)return t;t=null;const W=PROPS.wall;
  if(W&&W.img){const c=mk(W.img.width,W.img.height),g=c.getContext('2d');g.drawImage(W.img,0,0);
    const tint=p.night?'#6c7a9e':(p.grade&&p.grade.indexOf('255,150')>=0)?'#f2d2c2':null;
    if(tint){g.globalCompositeOperation='multiply';g.fillStyle=tint;g.fillRect(0,0,c.width,c.height);g.globalCompositeOperation='destination-in';g.drawImage(W.img,0,0);}
    t=c;}
  WT.set(p,t);return t;}
function drawWalls(zN,zF,p){
  const T=wallTex(p);if(!T)return false;
  const iw=T.width,ih=T.height,TL=(WALL_H-WALK_Y)*iw/ih,D=DPR;
  for(const x of [WALK_L,WALK_R]){
    // tapa de concreto (se ve desde arriba)
    const xo=x<0?x-WALL_T:x+WALL_T;ctx.fillStyle=p.night?'#4e5260':'#8f8d89';if(gq(Math.min(x,xo),zN,Math.max(x,xo),zF,WALL_CAP))ctx.fill();
    let z=zN;
    while(z<zF){
      const k=Math.floor(z/TL),zt=(k+1)*TL;
      if(!proj(x,WALL_H,z))break;const ax=PJ.x,ay=PJ.y,s0=PJ.s;if(!proj(x,WALK_Y,z))break;const cy=PJ.y;
      const depth=Math.max(1,(z-cam.z)),dz=Math.min(zt-z,Math.max(.3,13*depth*depth/(Math.abs(x-cam.x)*F+1)),zF-z);let z1=z+dz;if(z1-z<.02)z1=z+.02;
      if(!proj(x,WALL_H,z1))break;const bx=PJ.x,by=PJ.y;
      const fa=Math.min(1,Math.max(0,1-(z-cam.z-50)/50));
      if(fa<=.01)break;
      const su0=(z-k*TL)/TL*iw,su1=(z1-k*TL)/TL*iw,du=su1-su0;
      if(bx!==ax&&du>0){const a=(bx-ax)/du,b=(by-ay)/du,d=(cy-ay)/ih;
        ctx.setTransform(a*D,b*D,0,d*D,(ax-a*su0)*D,(ay-b*su0)*D);ctx.globalAlpha=fa;
        const sw=Math.min(iw-su0,du+.8);ctx.drawImage(T,su0,0,sw,ih,su0,0,sw,ih);}
      z=z1;
    }
    ctx.setTransform(D,0,0,D,0,0);ctx.globalAlpha=1;
  }
  return true;
}
function drawRoad(){""")
# cajas de arma especial (pre-sorteada) con su aura de color
rep("const cw=c.type==='w',CP=cw?PROPS.crateW:PROPS.crateM;", "const tq=c.type==='t',cw=c.type==='w'||tq,CP=cw?PROPS.crateW:PROPS.crateM;")
rep("ctx.drawImage(CP.img,x0,y0,W2,H2);\n    if(c.fl>0)", "if(tq){ctx.globalCompositeOperation='lighter';const gy=PJ.y-H2*.4,gr=ctx.createRadialGradient(PJ.x,gy,0,PJ.x,gy,W2*.95);gr.addColorStop(0,'rgba('+c.wp.col+',.6)');gr.addColorStop(1,'rgba('+c.wp.col+',0)');ctx.fillStyle=gr;ctx.fillRect(PJ.x-W2,PJ.y-H2*1.7,W2*2,H2*2.3);ctx.globalCompositeOperation='source-over';}\n    ctx.drawImage(CP.img,x0,y0,W2,H2);\n    if(c.fl>0)")
rep("otext(cw?'ARMA':'TROPA',PJ.x,y0+H2*(cw?.66:.7),fs,cw?'#ffe27a':'#e6f3ff','#14181f',.2);", "otext(tq?c.wp.sh:cw?'ARMA':'TROPA',PJ.x,y0+H2*(cw?.66:.7),fs*(tq&&c.wp.sh.length>5?.78:1),tq?c.wp.hex:cw?'#ffe27a':'#e6f3ff','#14181f',.2);")
rep("ctx.strokeStyle=cw?'#ffd34a':'#6fb6ff';", "ctx.strokeStyle=tq?c.wp.hex:cw?'#ffd34a':'#6fb6ff';")
baked_line = 'window.__BAKED=' + json.dumps(baked, separators=(',', ':')) + ';window.__SFX=' + json.dumps(SFX, separators=(',', ':')) + ';'
html = '\n'.join(HEAD + [baked_line] + [lines[NH + 1]] + [js])
open(OUT, 'w', encoding='utf-8').write(html)
print('pack',[(a,round(b/1e6,2),round(c/1e6,2)) for a,b,c in PACK_STATS]);print('wrote', OUT, len(html) // 1024, 'KB; baked', {k: len(v['src']) // 1024 for k, v in baked.items()})
