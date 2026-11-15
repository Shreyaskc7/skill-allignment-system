/** Mirrors the backend rule (the server validates again). Returns a message or ''. */
export function passwordProblem(pw: string): string {
  if (pw.length < 8) return 'Use at least 8 characters';
  if (pw.length > 128) return 'Use at most 128 characters';
  if (!/[A-Za-z]/.test(pw) || !/\d/.test(pw)) return 'Include at least one letter and one number';
  if (pw.trim() !== pw) return 'Do not start or end with spaces';
  return '';
}
