/** RFC 4180 CSV with spreadsheet formula injection neutralised (cells starting =, +, -, @). */
function cell(value: unknown): string {
  let text = value == null ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(text) && !/^-?\d/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(headers: readonly unknown[], rows: readonly (readonly unknown[])[]): string {
  return [headers, ...rows].map((row) => row.map(cell).join(',')).join('\n');
}
