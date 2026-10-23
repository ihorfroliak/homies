// Independent ec2bfa9 review probes retained; auth selector targets its newly restored dialog.
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { EngagementProvider, useSession } from '@/engagement/session';
import { ViewingPicker } from '@/engagement/viewings';
import { ReportDialog } from '@/engagement/conversations';
import { SavedProvider, SaveButton } from '@/engagement/saved';
import { e } from '@/engagement/copy';

const a = {authenticated:true,user:{id:'account-a',name:'A',phoneVerified:false,emailVerified:false}};
const b = {authenticated:true,user:{...a.user,id:'account-b',name:'B'}};
const anon = {authenticated:false};
const slot='2026-12-01T12:00:00Z';
const slots={slots:[slot],duration_minutes:30,timezone:'Europe/Warsaw'};
const fetchMock=vi.fn<typeof fetch>();
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
function deferred<T>() { let resolve!:(v:T)=>void; let reject!:(v:unknown)=>void; const promise=new Promise<T>((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}; }
function Identity(){const session=useSession();return <><output aria-label="identity">{session.ready ? session.user?.id??'anonymous':'loading'}</output><button onClick={()=>void session.refresh()}>Refresh identity</button></>}
beforeEach(()=>{fetchMock.mockReset();vi.stubGlobal('fetch',fetchMock);sessionStorage.clear();localStorage.clear();Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value(){this.open=true}});Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value(){this.open=false}})});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()});
async function confirmPicker(){await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));fireEvent.click(await screen.findByRole('radio'));fireEvent.click(screen.getByRole('button',{name:e.next}));await screen.findByLabelText(e.note);fireEvent.change(screen.getByLabelText(e.note),{target:{value:'Private note owned by account A'}})}
it.each(['anonymous','other account'])('clears private viewing note on authoritative %s change',async kind=>{
 let probes=0;fetchMock.mockImplementation(async path=>path==='/bff/auth/session'?response(++probes===1?a:kind==='anonymous'?anon:b):response(slots));
 render(<EngagementProvider><Identity/><ViewingPicker listingId="listing-1" onClose={()=>{}} onMessage={()=>{}}/></EngagementProvider>);await confirmPicker();
 fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent(kind==='anonymous'?'anonymous':'account-b'));
 expect(screen.queryByDisplayValue('Private note owned by account A')).not.toBeInTheDocument();
});
it('discards a late viewing success belonging to the previous account',async()=>{
 let probes=0;const post=deferred<Response>();fetchMock.mockImplementation(async(path,init)=>path==='/bff/auth/session'?response(++probes===1?a:b):init?.method==='POST'?post.promise:response(slots));
 render(<EngagementProvider><Identity/><ViewingPicker listingId="listing-1" onClose={()=>{}} onMessage={()=>{}}/></EngagementProvider>);await confirmPicker();fireEvent.click(screen.getByRole('button',{name:e.confirmViewing}));
 await waitFor(()=>expect(fetchMock.mock.calls.some(([,init])=>init?.method==='POST')).toBe(true));fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-b'));
 await act(async()=>post.resolve(response({id:'a-private-viewing',listing_id:'listing-1',starts_at:slot,status:'CONFIRMED'},201)));
 expect(screen.queryByText('Oglądanie potwierdzone')).not.toBeInTheDocument();
});
it('reopens authentication for a report write returning 401',async()=>{
 fetchMock.mockImplementation(async(path)=>path==='/bff/auth/session'?response(a):response({detail:'Authentication required'},401));
 render(<EngagementProvider><Identity/><ReportDialog messageId="message-1" onClose={()=>{}}/></EngagementProvider>);
 await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));fireEvent.click(screen.getByRole('button',{name:'Wyślij zgłoszenie'}));
 expect(await screen.findByRole('dialog',{name:e.authRequired})).toBeInTheDocument();expect(screen.getByLabelText(e.email)).toBeInTheDocument();
});
it('does not automatically retry an old-account save using a new account session',async()=>{
 let probes=0;let posts=0;const first=deferred<Response>();const calls:string[]=[];let owner='account-a';
 fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session'){owner=++probes===1?'account-a':'account-b';return response(probes===1?a:b)}if(init?.method==='POST'){calls.push(owner);return ++posts===1?first.promise:new Response(null,{status:204})}return response({items:[],total:0,limit:100,offset:0})});
 render(<EngagementProvider><Identity/><SavedProvider><SaveButton listingId="listing-1" title="Synthetic"/></SavedProvider></EngagementProvider>);
 const button=screen.getByRole('button',{name:'Zapisz: Synthetic'});await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));await waitFor(()=>expect(button).toBeEnabled());fireEvent.click(button);await waitFor(()=>expect(posts).toBe(1));
 fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-b'));await act(async()=>first.reject(new TypeError('synthetic lost response')));
 expect(calls).toEqual(['account-a']);
});
