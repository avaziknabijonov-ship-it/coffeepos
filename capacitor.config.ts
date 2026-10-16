import type { CapacitorConfig } from '@capacitor/cli'

const testApk = process.env.COFFEEPOS_TEST_APK === '1' || process.env.COFFEEPOS_TEST_APP === '1'

const config: CapacitorConfig = {
  appId: testApk ? 'uz.coffeepos.hybrid.test' : 'uz.coffeepos.hybrid',
  appName: testApk ? 'CoffeePOS TEST' : 'CoffeePOS Hybrid',
  webDir: 'dist',
  ios: { contentInset: 'automatic' },
  server: {
    // Permit reaching a development backend on the cafe's private Wi-Fi.
    // Production deployments must use HTTPS when hosted outside the LAN.
    androidScheme: 'http',
    cleartext: true,
  },
}

export default config
