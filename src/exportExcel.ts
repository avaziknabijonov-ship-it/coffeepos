/** Excel opens UTF-8 BOM CSV with semicolon separators. No customer secrets in exports by default. */
export function exportExcel(filename: string, headers: string[], rows: (string | number | null | undefined)[][]): void {
  const safe = (raw: string | number | null | undefined) => {
    let value = String(raw ?? '')
    // Neutralize formulas to prevent CSV injection when opened in Excel.
    if (/^[\s]*[=+@-]/.test(value)) value = "'" + value
    return '"' + value.replaceAll('"', '""') + '"'
  }
  const csv = '\uFEFF' + [headers, ...rows].map(row => row.map(safe).join(';')).join('\r\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url; a.download = filename.replace(/[^a-zA-Z0-9._-]/g, '_') + '.csv'
  document.body.appendChild(a); a.click(); a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
