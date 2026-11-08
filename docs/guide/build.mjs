// Build the guide: HTML -> PDF (Chromium), table of contents with real page numbers (two passes).
import { createRequire } from 'module'; const { chromium } = createRequire(import.meta.url)('playwright');
import fs from 'fs';
import { execFileSync } from 'child_process';

const html = 'file://' + process.cwd() + '/guide.html';
const footer = `<div style="width:100%;font-family:Inter,sans-serif;font-size:7.5pt;color:#7A8193;padding:0 17mm;display:flex;justify-content:space-between">
  <span>reverse-motion · Guide pas à pas</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`;

async function render(pages, out) {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto(html); await p.evaluate(() => document.fonts.ready);
  await p.evaluate((pages) => {
    const toc = document.getElementById('toc'); toc.innerHTML = '';
    const parts = { p1: 'Partie 1 · Comprendre', p2: 'Partie 2 · Installer', p3: 'Partie 3 · Préparer vos éléments', p4: 'Partie 4 · Utiliser le skill', p5: 'Partie 5 · Aide' };
    for (const s of document.querySelectorAll('section[id]')) {
      const id = s.id;
      if (parts[id]) { toc.insertAdjacentHTML('beforeend', `<li class="pt"><a href="#${id}">${parts[id]}</a></li>`); continue; }
      const t = s.dataset.toc; if (!t) continue;
      const k = s.querySelector('.kicker')?.textContent || '';
      const n = (k.match(/\d+/) || [''])[0];
      toc.insertAdjacentHTML('beforeend', `<li class="ch"><a href="#${id}">${n ? n + '. ' : ''}${t}</a><span class="dots"></span><span class="pg">${pages[id] || '00'}</span></li>`);
    }
  }, pages);
  await p.pdf({ path: out, format: 'A4', printBackground: true, displayHeaderFooter: true, headerTemplate: '<div></div>',
    footerTemplate: footer, margin: { top: '18mm', bottom: '20mm', left: '17mm', right: '17mm' }, outline: true, tagged: true });
  // where does each section start? (marker text = its h1, searched in the PDF)
  const ids = await p.evaluate(() => [...document.querySelectorAll('section[data-toc]')].map(s => [s.id, s.querySelector('h1').textContent.trim()]));
  await b.close();
  return ids;
}

const ids = await render({}, 'pass1.pdf');
fs.writeFileSync('ids.json', JSON.stringify(ids));
const pages = JSON.parse(execFileSync('python3', ['find_pages.py', 'pass1.pdf', 'ids.json']).toString());
await render(pages, 'pass2.pdf');
console.log(JSON.stringify(pages));
// cover without page number: same page rendered without footer, swapped in with pypdf
{
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto(html); await p.evaluate(() => document.fonts.ready);
  await p.pdf({ path: 'cover.pdf', format: 'A4', printBackground: true, pageRanges: '1',
    margin: { top: '18mm', bottom: '20mm', left: '17mm', right: '17mm' } });
  await b.close();
}
execFileSync('python3', ['-c', `
from pypdf import PdfReader, PdfWriter
w = PdfWriter(clone_from='pass2.pdf')
c = PdfReader('cover.pdf').pages[0]
w.pages[0].replace_contents(c.get_contents()) if False else None
w.insert_page(c, 0); w.remove_page(1)
w.add_metadata({'/Title': 'reverse-motion — Guide pas à pas', '/Subject': 'Installer et utiliser le skill reverse-motion', '/Author': 'reverse-motion'})
w.page_mode = '/UseOutlines'
w.write('GUIDE_reverse-motion.pdf')
`]);
console.log('GUIDE_reverse-motion.pdf');
