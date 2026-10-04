import {beforeEach, afterEach, it, expect, vi} from 'vitest';

beforeEach(()=>{
  vi.resetModules();
  const values = new Map();
  vi.stubGlobal('sessionStorage', {getItem:key=>values.get(key)||null, setItem:(key,value)=>values.set(key,value), removeItem:key=>values.delete(key)});
  vi.stubGlobal('window', {dispatchEvent:vi.fn()});
});
afterEach(()=>vi.unstubAllGlobals());

it('partage un seul renouvellement rotatif entre deux appels concurrents',async()=>{
  let renewals=0;
  vi.stubGlobal('fetch',vi.fn(async(url,options)=>{
    if(url==='/api/v1/auth/refresh') {
      renewals++;
      return {ok:true,json:async()=>({token:'new',refresh:'new-refresh',user:{id:1}})};
    }
    return options.headers.Authorization==='Bearer new'
      ? {ok:true,status:200,json:async()=>({ok:true})}
      : {ok:false,status:401,json:async()=>({detail:{detail:'Session expirée'}})};
  }));
  const {api,setAuth}=await import('./api');
  setAuth({token:'old',refresh:'old-refresh',user:{id:1}});
  expect(await Promise.all([api('/dossiers'),api('/notifications')])).toEqual([{ok:true},{ok:true}]);
  expect(renewals).toBe(1);
});

it('présente une erreur d’authentification lisible et retire la session expirée',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>({ok:false,status:401,json:async()=>({detail:{detail:'Session expirée'}})})));
  const {api,setAuth,getAuth}=await import('./api');
  setAuth({token:'old',refresh:'old-refresh'});
  await expect(api('/dossiers')).rejects.toThrow('Session expirée');
  expect(getAuth()).toBeNull();
  expect(window.dispatchEvent).toHaveBeenCalledOnce();
});
