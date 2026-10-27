// Per-company enrollment is retained across staff logout; never shown in reports.
const key = (company: string) => 'coffeepos-device:' + company.trim().toLowerCase()
export const getDeviceSecret = (company: string) => localStorage.getItem(key(company))
export const saveDeviceSecret = (company: string, value: string) => localStorage.setItem(key(company), value)
export const forgetDeviceSecret = (company: string) => localStorage.removeItem(key(company))
