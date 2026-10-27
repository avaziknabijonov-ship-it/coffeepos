import { test } from 'node:test'
import assert from 'node:assert/strict'
import { discountAmount } from '../src/pricing.ts'

test('server-compatible integer pricing and strict percentage cap', () => {
  assert.equal(discountAmount(30000, 20), 6000)
  assert.equal(discountAmount(30000, 30), 9000)
  assert.equal(discountAmount(101, 50), 50)
  assert.equal(discountAmount(555, 50), 277)
  for (const amount of [0, 1, 99, 101, 555, 12500, 30000, 999999]) {
    for (const percent of [0, 1, 17, 50]) {
      const discount = discountAmount(amount, percent)
      assert.ok(Number.isInteger(discount))
      assert.ok(discount >= 0 && discount <= Math.floor(amount * percent / 100))
    }
  }
})
test('invalid monetary values cannot silently produce a checkout price', () => {
  for (const [amount, percent] of [[-1, 10], [100, 51], [100, -1], [NaN, 10], [100, 1.5], [Infinity, 50]]) {
    assert.throws(() => discountAmount(amount, percent))
  }
})
