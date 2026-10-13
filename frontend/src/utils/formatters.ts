export function inr(n: number): string {
  const s = Math.round(Math.abs(n)).toString();
  const last3 = s.slice(-3);
  const rest = s.slice(0, -3);
  const formatted = (rest !== '' ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' : '') + last3;
  return (n < 0 ? '-₹' : '₹') + formatted;
}

export function lakh(n: number): string {
  return '₹' + (n / 100000).toFixed(n >= 1000000 ? 1 : 2).replace(/\.00$/, '') + ' L';
}

export const initials = (n: string): string =>
  (n.includes('—') ? n.split('—')[1] : n)
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

export const clock = (): string => new Date().toTimeString().slice(0, 5);

export const esc = (s: unknown): string =>
  String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] || c));

export function toCSV(rows: (string | number | boolean | null | undefined)[][]): string {
  return rows
    .map((r) =>
      r
        .map((v) => {
          const s = String(v == null ? '' : v);
          return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
        })
        .join(',')
    )
    .join('\r\n');
}

export function downloadCSV(name: string, rows: (string | number | boolean | null | undefined)[][]): void {
  const url = URL.createObjectURL(new Blob(['\ufeff' + toCSV(rows)], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cur = '';
  let inQ = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    const n = text[i + 1];
    if (inQ) {
      if (c === '"' && n === '"') {
        cur += '"';
        i++;
      } else if (c === '"') {
        inQ = false;
      } else {
        cur += c;
      }
    } else {
      if (c === '"') {
        inQ = true;
      } else if (c === ',') {
        row.push(cur.trim());
        cur = '';
      } else if (c === '\r' || c === '\n') {
        if (c === '\r' && n === '\n') i++;
        row.push(cur.trim());
        if (row.some((x) => x.length > 0)) rows.push(row);
        row = [];
        cur = '';
      } else {
        cur += c;
      }
    }
  }
  if (cur.length > 0 || row.length > 0) {
    row.push(cur.trim());
    if (row.some((x) => x.length > 0)) rows.push(row);
  }
  return rows;
}
