export function discountAmount(subtotal: number, percent: number): number {
  if (!Number.isSafeInteger(subtotal) || subtotal < 0 || !Number.isInteger(percent) || percent < 0 || percent > 50) throw new Error('Invalid discount')
  const raw = subtotal * percent
  const quotient = Math.floor(raw / 10000), remainder = raw % 10000
  const rounded = quotient + (remainder > 5000 || (remainder === 5000 && quotient % 2 === 1) ? 1 : 0)
  return Math.min(rounded * 100, Math.floor(raw / 100))
}
