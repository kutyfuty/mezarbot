// docs/ekran/sahneler.json → Discord (koyu tema) görünümünde PNG'ler: docs/ekran/<sahne>.png
// Gerekenler: Chromium + playwright-core (npm i playwright-core). Çalıştırma: node docs/ekran/cizici.js
const fs = require('fs');
const path = require('path');

function playwright() {
  for (const yol of ['playwright-core', process.env.PLAYWRIGHT_CORE].filter(Boolean)) {
    try { return require(yol); } catch (_) { /* sıradaki */ }
  }
  throw new Error('playwright-core bulunamadı: npm i playwright-core (ya da PLAYWRIGHT_CORE=/yol/playwright-core)');
}

const DIZIN = __dirname;
const veri = JSON.parse(fs.readFileSync(path.join(DIZIN, 'sahneler.json'), 'utf8'));
const KISILER = veri.kisiler, KANALLAR = veri.kanallar, ROLLER = veri.roller;

const kacis = (m) => String(m).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

// Discord markdown'ının README için yeterli alt kümesi
function satirIci(m) {
  const kodlar = [];
  m = m.replace(/`([^`]+)`/g, (_, k) => { kodlar.push(k); return `\u0000${kodlar.length - 1}\u0000`; });
  m = kacis(m);
  m = m.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<span class="lnk">$1</span>');
  m = m.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  m = m.replace(/(^|[^*])\*(?!\s)(.+?)\*/g, '$1<i>$2</i>');
  m = m.replace(/&lt;@&amp;(\d+)&gt;/g, (_, id) => `<span class="men">@${kacis(ROLLER[id] || 'rol')}</span>`);
  m = m.replace(/&lt;@!?(\d+)&gt;/g, (_, id) => `<span class="men">@${kacis(KISILER[id] || 'kullanıcı')}</span>`);
  m = m.replace(/&lt;#(\d+)&gt;/g, (_, id) => `<span class="men">#${kacis(KANALLAR[id] || 'kanal')}</span>`);
  return m.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${kacis(kodlar[+i])}</code>`);
}

function md(metin) {
  if (!metin) return '';
  return metin.split('\n').map((s) => {
    if (s.startsWith('> ')) return `<div class="bq">${satirIci(s.slice(2)) || '&nbsp;'}</div>`;
    if (s.startsWith('-# ')) return `<div class="sub">${satirIci(s.slice(3))}</div>`;
    return `<div>${satirIci(s) || '&nbsp;'}</div>`;
  }).join('');
}

const renk = (c) => '#' + (c || 0x1e1f22).toString(16).padStart(6, '0');

function embedHtml(e) {
  const alanlar = (e.fields || []).map((f) =>
    `<div class="fld${f.inline ? ' in' : ''}"><div class="fn">${satirIci(f.name)}</div><div class="fv">${md(f.value)}</div></div>`).join('');
  const kapak = e.thumbnail ? '<div class="thumb"><span>♫</span></div>' : '';
  return `<div class="embed" style="border-left-color:${renk(e.color)}"><div class="eg">
    <div class="ebody">
      ${e.author ? `<div class="auth">${satirIci(e.author.name)}</div>` : ''}
      ${e.title ? `<div class="title${e.url ? ' lnk' : ''}">${satirIci(e.title)}</div>` : ''}
      ${e.description ? `<div class="desc">${md(e.description)}</div>` : ''}
      ${alanlar ? `<div class="flds">${alanlar}</div>` : ''}
    </div>${kapak}</div>
    ${e.footer ? `<div class="foot">${kacis(e.footer.text)}${e.timestamp ? ' • ' + ZAMAN : ''}</div>` : ''}
  </div>`;
}

function bilesenHtml(satirlar) {
  return satirlar.map((s) => `<div class="row">${s.map((b) => b.tur === 'menu'
    ? `<div class="sel"><span>${kacis(b.yer_tutucu)}</span><span class="car">⌄</span></div>`
    : `<div class="btn ${b.stil}${b.kapali ? ' off' : ''}">${b.emoji ? `<span class="em">${b.emoji}</span>` : ''}${b.etiket ? `<span>${kacis(b.etiket)}</span>` : ''}</div>`).join('')}</div>`).join('');
}

let ZAMAN = '';
function sayfa(s) {
  const en = /-en$/.test(s.ad);
  ZAMAN = en ? 'Today at 21:30' : 'Bugün 21:30';
  const komut = s.komut ? `<div class="reply"><span class="rav"></span><b>Deniz</b> ${en ? `<span class="used">used</span> <span class="lnk">${kacis(s.komut)}</span>` : `<span class="lnk">${kacis(s.komut)}</span> <span class="used">kullandı</span>`}</div>` : '';
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  body{margin:0;background:#313338;font-family:"gg sans","Noto Sans","DejaVu Sans","Noto Color Emoji",sans-serif;color:#dbdee1;font-size:15px;line-height:1.375}
  #m{display:inline-block;padding:14px 22px 16px 16px;width:${s.genislik + 80}px;box-sizing:border-box}
  .reply{display:flex;align-items:center;gap:5px;font-size:13px;color:#b5bac1;margin:0 0 4px 30px}
  .reply .rav{width:16px;height:16px;border-radius:50%;background:#c27c0e;display:inline-block}
  .reply b{color:#f2f3f5;font-weight:600}.used{color:#b5bac1}
  .msg{display:flex;gap:16px}.av{width:40px;height:40px;border-radius:50%;background:#1f6f4a;display:flex;align-items:center;justify-content:center;font-size:22px;flex:none}
  .hd{display:flex;align-items:center;gap:6px}.nm{color:#f2f3f5;font-weight:600}
  .app{background:#5865f2;color:#fff;font-size:10px;font-weight:700;border-radius:3px;padding:1px 4px}.tm{color:#949ba4;font-size:12px}
  .embed{margin-top:4px;background:#2b2d31;border-left:4px solid;border-radius:4px;padding:8px 16px 16px 12px;max-width:${s.genislik}px;box-sizing:border-box}
  .eg{display:flex;gap:16px}.ebody{flex:1;min-width:0}
  .auth{font-size:14px;font-weight:600;color:#f2f3f5;margin-top:8px}.title{font-size:16px;font-weight:600;color:#f2f3f5;margin-top:8px}
  .desc{font-size:14px;margin-top:8px;white-space:pre-wrap}.desc div,.fv div{min-height:1em}
  .lnk{color:#00a8fc}.men{background:rgba(88,101,242,.3);color:#c9cdfb;border-radius:3px;padding:0 2px}
  code{background:#1e1f22;border-radius:3px;padding:0 3px;font-size:85%;font-family:"DejaVu Sans Mono",monospace}
  .bq{border-left:4px solid #4e5058;padding-left:10px}.sub{font-size:12px;color:#949ba4}
  .flds{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 12px;margin-top:8px}
  .fld{grid-column:1/-1;font-size:14px}.fld.in{grid-column:auto}.fn{font-weight:600;color:#f2f3f5;margin-bottom:2px}
  .thumb{width:80px;height:80px;border-radius:4px;flex:none;margin-top:8px;background:linear-gradient(135deg,#ff5f6d,#ffc371);display:flex;align-items:center;justify-content:center;font-size:36px;color:#fff}
  .foot{font-size:12px;color:#b5bac1;margin-top:8px}
  .row{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
  .btn{height:32px;min-width:52px;padding:0 14px;border-radius:8px;display:flex;align-items:center;justify-content:center;gap:6px;font-size:14px;font-weight:500;color:#fff;box-sizing:border-box}
  .btn .em{font-size:16px}.primary{background:#5865f2}.secondary{background:#4e5058}.success{background:#248046}.danger{background:#da373c}.off{opacity:.5}
  .sel{width:400px;height:40px;background:#1e1f22;border:1px solid #1e1f22;border-radius:4px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;box-sizing:border-box;color:#949ba4;font-size:14px}
  .car{font-size:18px;color:#dbdee1}
  </style></head><body><div id="m">${komut}<div class="msg"><div class="av">🪦</div><div style="min-width:0;flex:1">
  <div class="hd"><span class="nm">MezarBot</span><span class="app">${en ? 'APP' : 'UYGULAMA'}</span><span class="tm">${ZAMAN}</span></div>
  ${embedHtml(s.embed)}${bilesenHtml(s.bilesenler)}</div></div></div></body></html>`;
}

(async () => {
  const { chromium } = playwright();
  const tarayici = await chromium.launch({ executablePath: process.env.CHROMIUM || '/usr/bin/chromium', headless: true, args: ['--no-sandbox'] });
  const sekme = await tarayici.newPage({ deviceScaleFactor: 2, viewport: { width: 900, height: 1200 } });
  for (const s of veri.sahneler) {
    await sekme.setContent(sayfa(s), { waitUntil: 'load' });
    await sekme.evaluate(() => document.fonts.ready);
    const cikti = path.join(DIZIN, `${s.ad}.png`);
    await (await sekme.$('#m')).screenshot({ path: cikti });
    console.log('✓', path.relative(process.cwd(), cikti));
  }
  // Banner (README başlığı)
  const banner = await tarayici.newPage({ deviceScaleFactor: 2, viewport: { width: 1280, height: 360 } });
  await banner.setContent(fs.readFileSync(path.join(DIZIN, 'banner.html'), 'utf8'), { waitUntil: 'load' });
  await banner.evaluate(() => document.fonts.ready);
  await banner.screenshot({ path: path.join(DIZIN, 'banner.png') });
  console.log('✓', path.relative(process.cwd(), path.join(DIZIN, 'banner.png')));
  await tarayici.close();
})().catch((e) => { console.error(e); process.exit(1); });
