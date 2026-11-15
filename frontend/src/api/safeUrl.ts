/** Return the URL only if it is an absolute http(s) link; anything else (e.g. javascript:) becomes "#". */
export function safeUrl(url: string | null | undefined): string {
  if (!url) return '#';
  try {
    const u = new URL(url);
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : '#';
  } catch {
    return '#';
  }
}
