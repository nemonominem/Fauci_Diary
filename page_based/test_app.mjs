// test_app.mjs -- runs index.html's real script against the real data files.
//
// Ported from PO_Slack's harness: this machine has no headless browser, so
// instead of pretending, this shims just enough of the DOM and of
// pdf.js/Chart.js for the app's own code to execute unmodified -- the
// script is extracted from index.html and run as-is, not re-implemented.
// That makes it a real functional test of the app's logic and of the HTML
// it generates; what it cannot cover is layout and CSS, which is why
// audit_app.py checks the markup separately.
//
// Run:  node test_app.mjs  (from server_based/ or page_based/)
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
function mkEl(id) {
  return {
    id, innerHTML: '', textContent: '', value: '', hidden: false, style: {}, dataset: {},
    classList: { _s: new Set(), add(c){this._s.add(c)}, remove(c){this._s.delete(c)},
      toggle(c,f){ const has=this._s.has(c); const want=f===undefined?!has:!!f;
        if(want)this._s.add(c); else this._s.delete(c); return want; }, contains(c){return this._s.has(c)} },
    children: [], attrs: {},
    addEventListener(ev,fn){ (this._ev||(this._ev={}))[ev]=fn; },
    removeEventListener(){}, appendChild(c){ this.children.push(c); return c; }, remove(){},
    setAttribute(k,v){ this.attrs[k]=v; }, getAttribute(k){ return this.attrs[k]; },
    querySelector(){ return null; }, querySelectorAll(){ return []; },
    closest(){ return null; }, focus(){}, click(){}, scrollIntoView(){},
    getBoundingClientRect(){ return {top:0,left:0,width:10,height:10}; },
    width: 800, height: 600,
    getContext(){ return { fillRect(){}, clearRect(){}, fillText(){}, measureText(){ return {width:10}; },
      save(){}, restore(){}, scale(){}, translate(){}, beginPath(){}, moveTo(){}, lineTo(){},
      stroke(){}, fill(){}, setTransform(){}, drawImage(){}, getImageData(){ return {data:[]}; },
      putImageData(){}, createLinearGradient(){ return {addColorStop(){}}; } }; },
    clientHeight:100, scrollHeight:100, scrollTop:0,
    setPointerCapture(){}, releasePointerCapture(){},
  };
}
const els = {};
globalThis.document = {
  getElementById(id){ return els[id] || (els[id] = mkEl(id)); },
  createElement(t){ return mkEl('#'+t); },
  querySelector(){ return null; }, querySelectorAll(){ return []; },
  addEventListener(){}, body: mkEl('body'), documentElement: mkEl('html'),
};
globalThis.window = { addEventListener(){}, devicePixelRatio:1, innerWidth:1600, innerHeight:900 };
globalThis.localStorage = { _m:{}, getItem(k){return this._m[k]??null}, setItem(k,v){this._m[k]=v}, removeItem(k){delete this._m[k]} };
globalThis.location = { protocol:'http:', pathname:'/index.html' };
globalThis.requestAnimationFrame = (fn)=>{ try{fn()}catch(e){} };
globalThis.setTimeout = (fn)=>{ try{fn()}catch(e){} return 0; };
globalThis.devicePixelRatio = 1;
globalThis.fetch = async (url) => {
  const f = path.join(HERE, String(url).split('?')[0]);
  if (!fs.existsSync(f)) return { ok:false, status:404 };
  if (/\.pdf$/i.test(f)) return { ok:true, status:200, arrayBuffer: async () => new ArrayBuffer(0) };
  return { ok:true, status:200, json: async () => JSON.parse(fs.readFileSync(f,'utf8')) };
};
globalThis.pdfjsLib = { GlobalWorkerOptions:{},
  getDocument: () => ({ promise: Promise.resolve({ numPages:1, getPage: async()=>({}) }) }) };
function Chart(){
  return { data: { datasets: [], labels: [] }, options: {},
    destroy(){}, update(){}, resetZoom(){}, resize(){}, stop(){}, toBase64Image(){ return ''; },
    setDatasetVisibility(){}, getDatasetMeta(){ return { data: [] }; },
    scales: {}, $canvas: null, canvas: null, ctx: null };
}
Chart.defaults = { color:'#fff', font:{size:11} };
globalThis.Chart = Chart;
const pageHtml = fs.readFileSync(path.join(HERE,'index.html'),'utf8');
const scripts = [...pageHtml.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
const code = scripts[scripts.length - 1];
const tail = `
globalThis.__app = { SOURCES, KIND_DEFS, entryKind, kindDef,
  availableKinds, loadKindFilter, saveKindFilter, loadData, doSearch,
  displayResults, buildTimelineSeries, highlightWithHits,
  openEntryRef, rebuildThreadDownLinks, renderEntryPdf, toggleBookmark, isBookmarked,
  diaryBmKey, bookmarksPayload, diaryBmIndex, openEntryByBmKey,
  get diaryData(){ return diaryData; },
  get timelineSeries(){ return timelineSeries; } };
`;
const src = code + tail;
await import('data:text/javascript;base64,' + Buffer.from(src).toString('base64'));
const app = globalThis.__app;
await app.loadData();

let pass = 0, fail = 0;
const ok = (name, cond, extra='') => { if (cond) { pass++; console.log('  PASS  ' + name); }
  else { fail++; console.log('  FAIL  ' + name + (extra ? '  -> ' + extra : '')); } };
const sec = (t) => console.log('\n' + t);

sec('Data load');
ok('entries loaded (2713)', app.diaryData && app.diaryData.entries.length === 2713, app.diaryData && app.diaryData.entries.length);
const byKind = {};
app.diaryData.entries.forEach(e => { const k = app.entryKind(e); byKind[k] = (byKind[k]||0)+1; });
console.log('        kinds:', JSON.stringify(byKind));
ok('diary + email + attachment + note kinds present',
   (byKind.diary||0) > 2500 && (byKind.email||0) >= 20 && (byKind.attachment||0) >= 1 && (byKind.note||0) >= 1,
   JSON.stringify(byKind));
const srcs = {};
app.diaryData.entries.forEach(e => srcs[e.source] = (srcs[e.source]||0)+1);
console.log('        sources:', JSON.stringify(srcs));
ok('four sources merged', Object.keys(srcs).length === 4, JSON.stringify(srcs));
ok('missingyears contributes 695', srcs.missingyears === 695, String(srcs.missingyears));

sec('Chronology');
ok('timeline range 2001-01-26 .. 2022-12-17',
   app.diaryData.date_range.start === '2001-01-26' && app.diaryData.date_range.end === '2022-12-17',
   JSON.stringify(app.diaryData.date_range));

sec('Thread integrity');
const emails = app.diaryData.entries.filter(e => app.entryKind(e) === 'email');
const byFull = {};
app.diaryData.entries.forEach(e => { byFull[e.source + '|' + e.date + '|' + e.raw_date] = e; });
const replies = emails.filter(e => e.reply_to);
const fwd = emails.filter(e => e.forwarded_from);
ok('reply targets all exist',
   replies.every(e => byFull[e.reply_to] || byFull[e.source + '|' + e.reply_to]),
   replies.filter(e => !(byFull[e.reply_to] || byFull[e.source + '|' + e.reply_to])).length + ' dangling');
ok('forward targets all exist',
   fwd.every(e => byFull[e.forwarded_from] || byFull[e.source + '|' + e.forwarded_from]),
   fwd.filter(e => !(byFull[e.forwarded_from] || byFull[e.source + '|' + e.forwarded_from])).length + ' dangling');

sec('Page maps resolve');
const maps = {};
for (const s of Object.keys(app.SOURCES)) {
  maps[s] = JSON.parse(fs.readFileSync(path.join(HERE, app.SOURCES[s].pageMap), 'utf8'));
}
const unmapped = app.diaryData.entries.filter(e => !maps[e.source][e.date + '|' + e.raw_date]);
ok('every entry has a page-map key', unmapped.length === 0, unmapped.slice(0,3).map(e=>e.source+' '+e.date).join(', '));

sec('Search + rendering');
const input = document.getElementById('searchInput');
input.value = 'aerosolized';
app.doSearch();
const panel = document.getElementById('resultsPanel');
const html = panel.innerHTML;
console.log('        rendered', (html.match(/class="result-entry/g)||[]).length, 'cards');
ok('search produced cards', (html.match(/class="result-entry/g)||[]).length > 0);
ok('email cards carry a box-type badge', /class="entry-kind"/.test(html));
ok('cards carry a source badge', /Missing Years|Prequel|Ebola|Main/.test(html));
ok('every card has its own scroll box', (html.match(/class="box-scrollbar/g)||[]).length === (html.match(/class="result-entry/g)||[]).length);
ok('Full text expander present', /data-expand-toggle=/.test(html));

sec('Missing-years results carry the right badge');
input.value = 'ransomware';
app.doSearch();
const html2 = document.getElementById('resultsPanel').innerHTML;
ok('ransomware note found', /RANSOMWARE/i.test(html2));
ok('missing-years badge shown', /Missing Years/.test(html2));

sec('Thread chips navigate');
const threaded = app.diaryData.entries.find(e => (e.replied_by||[]).length || (e.forwarded_by||[]).length);
ok('some emails are threaded', !!threaded);
if (threaded) {
  const word = (threaded.content.match(/[a-z]{6,}/i)||['x'])[0];
  input.value = word;
  app.doSearch();
  const h3 = document.getElementById('resultsPanel').innerHTML;
  const chips = h3.match(/data-entry-ref="[^"]+"/g);
  ok('thread chips are navigable', !!chips && chips.length > 0,
     (chips ? chips.length : 0) + ' chips for "' + word + '"');
}

sec('Box types filter');
app.loadKindFilter();
const kindsBefore = app.availableKinds();
ok('kinds listed', Object.keys(kindsBefore).length >= 4, JSON.stringify(kindsBefore));

sec('Bookmarks');
ok('bookmark toggle defined', typeof app.toggleBookmark === 'function');
ok('diaryBmKey is source-qualified', typeof app.diaryBmKey === 'function');
const _e0 = app.diaryData.entries[10];
const _k0 = app.diaryBmKey(_e0);
ok('bm_key matches source|date|raw_date', _k0 === (_e0.source + '|' + _e0.date + '|' + _e0.raw_date), _k0);
const _added = app.toggleBookmark(_k0, { label: 't', sub: 's' });
ok('toggle adds', _added === true && app.isBookmarked(_k0));
const _added2 = app.toggleBookmark(_k0, { label: 't', sub: 's' });
ok('toggle again removes', _added2 === false && !app.isBookmarked(_k0));
const _payload = app.bookmarksPayload();
ok('payload names the drastic format', _payload.format === 'drastic-bookmarks' && _payload.app === 'fauci-diary');

sec('renderEntryPdf exists (on-demand PDF fix)');
ok('renderEntryPdf is defined', typeof app.renderEntryPdf === 'function');

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
