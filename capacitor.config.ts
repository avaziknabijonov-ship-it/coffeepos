import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'uz.coffeepos.hybrid',
  appName: 'CoffeePOS Hybrid',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
}

export default config
