const digits = (s: string) => s.replace(/\D/g, '');

/**
 * True when the query is in one of the texts (any case), or its digits are in one of
 * the phone numbers however they're written ("+91 76719 53289", "7671953289", "07671953289").
 */
export function matchesQuery(query: string, texts: (string | undefined)[], phones: (string | undefined)[] = []): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (texts.some((t) => t?.toLowerCase().includes(q))) return true;
  const d = digits(q).replace(/^0+/, '');
  return d.length >= 3 && phones.some((p) => !!p && digits(p).includes(d));
}

/** A–Z by name, ignoring case; "Shop 2" comes before "Shop 10" */
export const byName = <T extends { name: string }>(a: T, b: T) =>
  a.name.localeCompare(b.name, 'en', { sensitivity: 'base', numeric: true });
