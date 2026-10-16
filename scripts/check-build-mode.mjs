// Keep the ordinary browser/LAN build unchanged. Fail mismatched store builds.
if (process.env.COFFEEPOS_STORE_BUILD === '1' || process.env.VITE_STORE_BUILD === '1') {
  await import('./check-store-release.mjs')
}
