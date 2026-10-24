const KEY = 'coffeepos-paper-width'
export type ReceiptWidth = 58 | 80

export function getReceiptWidth(): ReceiptWidth {
  return localStorage.getItem(KEY) === '58' ? 58 : 80
}
export function setReceiptWidth(width: ReceiptWidth): void {
  localStorage.setItem(KEY, String(width))
  document.documentElement.style.setProperty('--receipt-width', width + 'mm')
}
export function initReceiptWidth(): void {
  document.documentElement.style.setProperty('--receipt-width', getReceiptWidth() + 'mm')
}
