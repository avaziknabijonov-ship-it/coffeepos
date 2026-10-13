import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'uz.coffeepos.hybrid',
  appName: 'CoffeePOS Hybrid',
  webDir: 'dist',
  server: {
    // Permit reaching a development backend on the cafe's private Wi-Fi.
    // Production deployments must use HTTPS when hosted outside the LAN.
    androidScheme: 'http',
    cleartext: true,
  },
}

export default config
