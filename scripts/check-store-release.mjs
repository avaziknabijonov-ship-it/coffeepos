// Fail before producing a store bundle with a demo identity or missing policy.
const errors = []
if (process.env.COFFEEPOS_STORE_BUILD !== '1') errors.push('Set COFFEEPOS_STORE_BUILD=1.')
if (process.env.COFFEEPOS_TEST_APK === '1' || process.env.COFFEEPOS_TEST_APP === '1') errors.push('Store builds cannot use the TEST identity.')
if (process.env.VITE_STORE_BUILD !== '1') errors.push('Set VITE_STORE_BUILD=1.')
if (process.env.VITE_ALLOW_PUBLIC_REGISTRATION !== '0') errors.push('Store builds use provisioned business accounts; set VITE_ALLOW_PUBLIC_REGISTRATION=0.')
try {
  const url = new URL(process.env.VITE_API_URL)
  if (url.protocol !== 'https:' || url.username || url.password || url.pathname !== '/' || url.search || url.hash
    || ['example.com','example.org','example.net','localhost'].includes(url.hostname) || /\.(invalid|test|example)$/.test(url.hostname) || url.hostname.endsWith('.local') || /^[\d.]+$/.test(url.hostname)) throw Error()
} catch { errors.push('Set VITE_API_URL to the real public HTTPS API origin.') }
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(process.env.VITE_SUPPORT_EMAIL || '')) errors.push('Set VITE_SUPPORT_EMAIL to the actual support address.')
const days = Number(process.env.VITE_PRIVACY_BACKUP_DAYS)
if (!Number.isInteger(days) || days < 1 || days > 365) errors.push('Set VITE_PRIVACY_BACKUP_DAYS to the implemented backup retention (1–365).')
if (!/^[1-9]\d*$/.test(process.env.COFFEEPOS_BUILD_NUMBER || '')) errors.push('Set a new positive COFFEEPOS_BUILD_NUMBER.')
if (errors.length) { console.error(errors.join('\n')); process.exit(1) }
console.log('Store build inputs validated. Deployment, policy contact and backup retention must still be verified before submission.')
