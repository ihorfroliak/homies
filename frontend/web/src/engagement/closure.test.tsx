import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, afterEach, it, expect, vi } from 'vitest';
import { EngagementProvider, useSession } from '@/engagement/session';
import { ViewingPicker } from '@/engagement/viewings';
import { ReportDialog, ConversationWorkspace } from '@/engagement/conversations';
import { SavedProvider, SaveButton } from '@/engagement/saved';
import { Modal } from '@/engagement/ui';
import { INTENT_KEY } from '@/engagement/intent';
import { e } from '@/engagement/copy';
const a={authenticated:true,user:{id:'account-a',name:'A',phoneVerified:false,emailVerified:false}};
const b={authenticated:true,user:{...a.user,id:'account-b'}};
const anon={authenticated:false}; const slot='2026-12-01T12:00:00Z';const slots={slots:[slot],duration_minutes:30,timezone:'Europe/Warsaw'};
const fetchMock=vi.fn<typeof fetch>();const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
function deferred<T>(){let resolve!:(v:T)=>void;let reject!:(v:unknown)=>void;const promise=new Promise<T>((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
let frames:FrameRequestCallback[]=[];
function Identity(){const session=useSession();return <><output aria-label="identity">{session.ready?session.user?.id??'anonymous':'loading'}</output><button onClick={()=>void session.refresh()}>Refresh identity</button></>}
beforeEach(()=>{fetchMock.mockReset();vi.stubGlobal('fetch',fetchMock);frames=[];sessionStorage.clear();localStorage.clear();vi.stubGlobal('requestAnimationFrame',(cb:FrameRequestCallback)=>{frames.push(cb);return frames.length});vi.stubGlobal('cancelAnimationFrame',vi.fn());Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value(){this.open=true}});Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value(){this.open=false}})});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks()});
async function flushFrames(){await act(async()=>{for(const cb of frames.splice(0))cb(performance.now())})}
async function login(){const dialog=screen.getByRole('dialog',{name:e.authRequired});fireEvent.change(within(dialog).getByLabelText(e.email),{target:{value:'synthetic@example.com'}});fireEvent.change(within(dialog).getByLabelText(e.password),{target:{value:'Synthetic-password!'}});fireEvent.submit(within(dialog).getByLabelText(e.password).closest('form')!);await waitFor(()=>expect(screen.queryByRole('dialog',{name:e.authRequired})).not.toBeInTheDocument());await flushFrames()}
async function confirmPicker(){await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));fireEvent.click(await screen.findByRole('radio'));fireEvent.click(screen.getByRole('button',{name:e.next}));await screen.findByLabelText(e.note)}
it('preserves guest selected instant through post-commit authentication and requires deliberate request',async()=>{
 let signedIn=false;const viewingWrites:RequestInit[]=[];fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session')return response(signedIn?a:anon);if(path==='/bff/auth/login'){signedIn=true;return response({authenticated:true})}if(init?.method==='POST'){viewingWrites.push(init);return response({status:'REQUESTED',starts_at:slot},201)}return response(slots)});
 render(<EngagementProvider><Identity/><ViewingPicker listingId="listing-1" onClose={()=>{}} onMessage={()=>{}}/></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('anonymous'));fireEvent.click(await screen.findByRole('radio'));fireEvent.click(screen.getByRole('button',{name:e.next}));await screen.findByRole('dialog',{name:e.authRequired});await login();await screen.findByLabelText(e.note);expect(viewingWrites).toHaveLength(0);fireEvent.click(screen.getByRole('button',{name:e.confirmViewing}));await waitFor(()=>expect(viewingWrites).toHaveLength(1));expect(JSON.parse(String(viewingWrites[0]!.body)).starts_at).toBe(slot);
});
it('guest save resumes only after new account initial saved-set read commits',async()=>{
 let signedIn=false;const reads=deferred<Response>();let writes=0;fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session')return response(signedIn?a:anon);if(path==='/bff/auth/login'){signedIn=true;return response({authenticated:true})}if(init?.method==='POST'){writes++;return new Response(null,{status:204})}return reads.promise});
 render(<EngagementProvider><Identity/><SavedProvider><SaveButton listingId="listing-1" title="Synthetic"/></SavedProvider></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('anonymous'));fireEvent.click(screen.getByRole('button',{name:'Zapisz: Synthetic'}));await screen.findByRole('dialog',{name:e.authRequired});await login();expect(writes).toBe(0);await act(async()=>reads.resolve(response({items:[],total:0,limit:100,offset:0})));await screen.findByRole('button',{name:'Usuń z zapisanych: Synthetic'});expect(writes).toBe(1);
});
it('report401 login restores same-account draft and requires another explicit report press',async()=>{
 let writes=0;fetchMock.mockImplementation(async(path)=>path==='/bff/auth/session'?response(a):path==='/bff/auth/login'?response({authenticated:true}):response(++writes===1?{detail:'expired'}:{id:'report-1'},writes===1?401:201));render(<EngagementProvider><Identity/><ReportDialog messageId="message-1" onClose={()=>{}}/></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));fireEvent.change(screen.getByLabelText(e.reportText),{target:{value:'Private report text'}});fireEvent.click(screen.getByRole('button',{name:'Wyślij zgłoszenie'}));await screen.findByRole('dialog',{name:e.authRequired});await login();expect(writes).toBe(1);expect(screen.getByLabelText(e.reportText)).toHaveValue('Private report text');fireEvent.click(screen.getByRole('button',{name:'Wyślij zgłoszenie'}));await screen.findByText(e.reportAccepted);expect(writes).toBe(2);
});
it('drops late failed viewing request without reading B private viewings',async()=>{
 let probes=0;const post=deferred<Response>();let privateReads=0;fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session')return response(++probes===1?a:b);if(path==='/bff/v1/me/viewings'){privateReads++;return response([])}if(init?.method==='POST')return post.promise;return response(slots)});render(<EngagementProvider><Identity/><ViewingPicker listingId="listing-1" onClose={()=>{}} onMessage={()=>{}}/></EngagementProvider>);await confirmPicker();fireEvent.click(screen.getByRole('button',{name:e.confirmViewing}));fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-b'));await act(async()=>post.reject(new TypeError('response lost')));expect(privateReads).toBe(0);expect(screen.queryByLabelText(e.note)).toBeNull();
});
it('drops late viewing reconciliation after account switch',async()=>{
 let probes=0;const read=deferred<Response>();let privateReads=0;fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session')return response(++probes===1?a:b);if(path==='/bff/v1/me/viewings'){privateReads++;return read.promise}if(init?.method==='POST')throw new TypeError('response lost');return response(slots)});render(<EngagementProvider><Identity/><ViewingPicker listingId="listing-1" onClose={()=>{}} onMessage={()=>{}}/></EngagementProvider>);await confirmPicker();fireEvent.click(screen.getByRole('button',{name:e.confirmViewing}));await waitFor(()=>expect(privateReads).toBe(1));fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-b'));await act(async()=>read.resolve(response([{listing_id:'listing-1',starts_at:slot,status:'CONFIRMED'}])));expect(screen.queryByText('Oglądanie potwierdzone')).toBeNull();
});
it('does not revive an invalidated save after A logs out and back into A',async()=>{
 let probes=0;let writes=0;const first=deferred<Response>();fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session')return response(++probes===2?anon:a);if(init?.method==='POST')return ++writes===1?first.promise:new Response(null,{status:204});return response({items:[],total:0,limit:100,offset:0})});render(<EngagementProvider><Identity/><SavedProvider><SaveButton listingId="listing-1" title="Synthetic"/></SavedProvider></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));const button=screen.getByRole('button',{name:'Zapisz: Synthetic'});await waitFor(()=>expect(button).toBeEnabled());fireEvent.click(button);await waitFor(()=>expect(writes).toBe(1));fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('anonymous'));fireEvent.click(screen.getByRole('button',{name:'Refresh identity'}));await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));await act(async()=>first.reject(new TypeError('lost old-session response')));expect(writes).toBe(1);
});
it('reopens a valid restored report intent on its authorized thread without auto-submitting',async()=>{
 const conversation={id:'thread-1',listing_id:'listing-1',my_side:'tenant',status:'ACTIVE',created_at:slot,last_message_at:slot};const message={id:'message-1',body:'Other participant message',sender_user_id:'provider',message_type:'USER',moderation_state:'NONE',created_at:slot};let writes=0;sessionStorage.setItem(INTENT_KEY,JSON.stringify({action:'report',message_id:'message-1',initiator_id:'engagement-status',created_at:Date.now()}));fetchMock.mockImplementation(async(path,init)=>{if(init?.method==='POST')writes++;if(path==='/bff/auth/session')return response(a);if(path==='/bff/v1/conversations')return response([conversation]);if(path==='/bff/v1/conversations/thread-1')return response({conversation,messages:[message]});return response({title:'Synthetic',district:null})});render(<EngagementProvider><Identity/><ConversationWorkspace conversationId="thread-1"/></EngagementProvider>);await screen.findByText('Other participant message');expect(writes).toBe(0);expect(await screen.findByRole('dialog',{name:e.report})).toBeInTheDocument();
});
it('explicitly wraps Tab and Shift+Tab at visible modal boundaries and restores opener',()=>{
 vi.spyOn(HTMLElement.prototype,'getClientRects').mockImplementation(function(this:HTMLElement){return (this.hasAttribute('hidden')?[]:[{width:1,height:1}]) as unknown as DOMRectList});const opener=document.createElement('button');document.body.append(opener);opener.focus();const close=vi.fn();const view=render(<Modal title="Focus" onClose={close}><input aria-label="Middle"/><button hidden>Hidden</button><button>Last</button></Modal>);const first=screen.getByRole('button',{name:e.close});const last=screen.getByRole('button',{name:'Last'});last.focus();fireEvent.keyDown(last,{key:'Tab'});expect(first).toHaveFocus();fireEvent.keyDown(first,{key:'Tab',shiftKey:true});expect(last).toHaveFocus();view.unmount();expect(opener).toHaveFocus();opener.remove();
});
it('scopes pending locks to the current identity and an old completion cannot unlock its replacement', async () => {
 let probes=0; let writes=0; const first=deferred<Response>(); const second=deferred<Response>();
 fetchMock.mockImplementation(async(path,init)=>{
  if(path==='/bff/auth/session')return response(++probes===1?a:b);
  if(init?.method==='POST')return ++writes===1?first.promise:second.promise;
  return response({items:[],total:0,limit:100,offset:0});
 });
 render(<EngagementProvider><Identity/><SavedProvider><SaveButton listingId="listing-1" title="Synthetic"/></SavedProvider></EngagementProvider>);
 await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));
 const button=screen.getByRole('button',{name:'Zapisz: Synthetic'}); await waitFor(()=>expect(button).toBeEnabled());
 fireEvent.click(button); await waitFor(()=>expect(writes).toBe(1)); expect(button).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Refresh identity'})); await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-b'));
 await waitFor(()=>expect(button).toBeEnabled()); fireEvent.click(button); await waitFor(()=>expect(writes).toBe(2));
 await act(async()=>first.reject(new TypeError('old response lost')));
 expect(writes).toBe(2); expect(button).toBeDisabled(); expect(button).toHaveAttribute('aria-pressed','false');
 await act(async()=>second.resolve(new Response(null,{status:204})));
 expect(await screen.findByRole('button',{name:'Usuń z zapisanych: Synthetic'})).toBeEnabled();
});
it.each(['own','removed','system'])('discards a restored report intent when fresh message is %s', async kind => {
 const conversation={id:'thread-1',listing_id:'listing-1',my_side:'tenant',status:'ACTIVE',created_at:slot,last_message_at:slot};
 const message={id:'message-1',body:kind==='removed'?null:'Synthetic body',sender_user_id:kind==='own'?a.user.id:'provider',message_type:kind==='system'?'SYSTEM':'USER',moderation_state:kind==='removed'?'REMOVED':'NONE',created_at:slot};
 let writes=0;sessionStorage.setItem(INTENT_KEY,JSON.stringify({action:'report',message_id:'message-1',initiator_id:'engagement-status',created_at:Date.now()}));
 fetchMock.mockImplementation(async(path,init)=>{if(init?.method==='POST')writes++;if(path==='/bff/auth/session')return response(a);if(path==='/bff/v1/conversations')return response([conversation]);if(path==='/bff/v1/conversations/thread-1')return response({conversation,messages:[message]});return response({title:'Synthetic',district:null})});
 render(<EngagementProvider><Identity/><ConversationWorkspace conversationId="thread-1"/></EngagementProvider>);
 await screen.findByRole('log');await act(async()=>{await Promise.resolve()});
 expect(screen.queryByRole('dialog',{name:e.report})).not.toBeInTheDocument();expect(writes).toBe(0);expect(sessionStorage.getItem(INTENT_KEY)).toBeNull();
});
