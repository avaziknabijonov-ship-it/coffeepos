import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
const memory = new Map()
const localStorage = { getItem: k => memory.get(k) ?? null, setItem: (k,v) => memory.set(k,v), removeItem: k => memory.delete(k) }
let request
let respond = () => new Response(JSON.stringify({ok:true}))
function load(store) {
  const source = fs.readFileSync('src/api.ts','utf8').replace(/import\.meta\.env/g, 'BUILD_ENV')
  const code = ts.transpileModule(source, {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText
  const exports = {}
  vm.runInNewContext(code, {exports, URL, AbortSignal, AbortController, setTimeout, clearTimeout, BUILD_ENV:{VITE_STORE_BUILD:store?'1':'0'},localStorage,
    require: name => name === '@capacitor/core' ? {Capacitor:{isNativePlatform:()=>true}} : {t:s=>s,tServer:s=>s},
    fetch: async (url,options) => {request={url,options};return respond()} })
  return exports
}
const dev=load(false)
assert.equal(dev.normalizeServerUrl('http://192.168.1.2:8000'),'http://192.168.1.2:8000')
assert.throws(()=>dev.normalizeServerUrl('http://public.example'))
dev.setToken('server-a-secret');dev.saveServerUrl('https://api.example.com');assert.equal(dev.getToken(),null)
const store=load(true)
assert.throws(()=>store.normalizeServerUrl('http://192.168.1.2:8000'))
assert.throws(()=>store.normalizeServerUrl('https://user:pass@api.example.com'))
store.setToken('normal-session')
await store.api('/api/auth/login',{body:{company:'qa',pin:'1234'},authToken:null})
assert.equal(request.options.headers.Authorization,undefined)
assert(request.options.signal instanceof AbortSignal)
await store.api('/api/account',{method:'DELETE',body:{company:'qa',pin:'1234'},authToken:'reauth-session'})
assert.equal(request.options.headers.Authorization,'Bearer reauth-session')
assert.equal(store.getToken(),'normal-session')
respond=()=>{throw new DOMException('Timed out','TimeoutError')}
await assert.rejects(store.checkServerUrl('https://api.example.com'))
respond=()=>new Response('Bad gateway',{status:502})
await assert.rejects(store.api('/api/me'),e=>e.status===502)
console.log('PASS: store HTTPS, server token isolation, deletion reauthentication, timeouts and 502 recovery')
