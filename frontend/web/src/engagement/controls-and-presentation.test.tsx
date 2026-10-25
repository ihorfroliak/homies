// Independent ec2bfa9 review controls, retained as causal regression coverage.
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { EngagementProvider, useSession } from '@/engagement/session';
import { ViewingPicker } from '@/engagement/viewings';
import { ReportDialog } from '@/engagement/conversations';
import { SaveButton, SavedProvider } from '@/engagement/saved';
import { DetailEngagement } from '@/engagement/detail';
import { CostBreakdown } from '@/engagement/cost-breakdown';
import { e } from '@/engagement/copy';
vi.mock('next/navigation',()=>({useRouter:()=>({push:vi.fn()}),usePathname:()=>'/oferta/listing-1'}));
const account={authenticated:true,user:{id:'account-a',name:'A',phoneVerified:false,emailVerified:false}};
const slot='2026-12-01T12:00:00Z';
const fetchMock=vi.fn<typeof fetch>();
const response=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
function Identity(){const session=useSession();return <output aria-label="identity">{session.ready?session.user?.id??'anonymous':'loading'}</output>}
beforeEach(()=>{fetchMock.mockReset();vi.stubGlobal('fetch',fetchMock);sessionStorage.clear();localStorage.clear();Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value(){this.open=true}});Object.defineProperty(HTMLDialogElement.prototype,'close',{configurable:true,value(){this.open=false}})});
afterEach(()=>{cleanup();vi.unstubAllGlobals()});
it('control: current-account viewing note and successful result work',async()=>{
 fetchMock.mockImplementation(async(path,init)=>path==='/bff/auth/session'?response(account):init?.method==='POST'?response({id:'viewing-1',starts_at:slot,status:'CONFIRMED'},201):response({slots:[slot],duration_minutes:30,timezone:'Europe/Warsaw'}));
 render(<EngagementProvider><Identity/><ViewingPicker listingId="listing-1" onClose={()=>{}} onMessage={()=>{}}/></EngagementProvider>);
 await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));fireEvent.click(await screen.findByRole('radio'));fireEvent.click(screen.getByRole('button',{name:e.next}));fireEvent.change(await screen.findByLabelText(e.note),{target:{value:'A note'}});expect(screen.getByLabelText(e.note)).toHaveValue('A note');fireEvent.click(screen.getByRole('button',{name:e.confirmViewing}));await screen.findByText('Oglądanie potwierdzone');expect(Object.values(sessionStorage).join('')).not.toContain('A note');
});
it('control: same-account idempotent save retry succeeds',async()=>{
 let writes=0;fetchMock.mockImplementation(async(path,init)=>{if(path==='/bff/auth/session')return response(account);if(init?.method==='POST'){if(++writes===1)throw new TypeError('lost');return new Response(null,{status:204})}return response({items:[],total:0,limit:100,offset:0})});
 render(<EngagementProvider><Identity/><SavedProvider><SaveButton listingId="listing-1" title="Synthetic"/></SavedProvider></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));const button=screen.getByRole('button',{name:'Zapisz: Synthetic'});await waitFor(()=>expect(button).toBeEnabled());fireEvent.click(button);await screen.findByRole('button',{name:'Usuń z zapisanych: Synthetic'});expect(writes).toBe(2);
});
it('control: unverified current-account participant can submit report',async()=>{
 fetchMock.mockImplementation(async path=>path==='/bff/auth/session'?response(account):response({id:'report-1'},201));render(<EngagementProvider><Identity/><ReportDialog messageId="message-1" onClose={()=>{}}/></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));fireEvent.click(screen.getByRole('button',{name:'Wyślij zgłoszenie'}));await screen.findByText(e.reportAccepted);expect(screen.queryByLabelText(e.email)).toBeNull();
});
it.each(['ARCHIVED','CLOSED'])('permits a new conversation when only an old %s conversation exists',async status=>{
 fetchMock.mockImplementation(async path=>{if(path==='/bff/auth/session')return response(account);if(path==='/bff/v1/conversations')return response([{id:'old-thread',listing_id:'listing-1',my_side:'tenant',status,created_at:'2026-01-01T00:00:00Z'}]);if(String(path).includes('saved-listings'))return response({items:[],total:0,limit:100,offset:0});return response([])});
 render(<EngagementProvider><Identity/><SavedProvider><DetailEngagement listing={{id:'listing-1',title:'Synthetic',contact_mode:'messages',monthly_total_estimate:100000,utilities_basis:'INCLUDED',currency:'PLN'}}/></SavedProvider></EngagementProvider>);await waitFor(()=>expect(screen.getByLabelText('identity')).toHaveTextContent('account-a'));await act(async()=>{await Promise.resolve()});expect(screen.queryByRole('link',{name:e.continueThread})).not.toBeInTheDocument();expect(screen.getByRole('button',{name:e.message})).toBeInTheDocument();
});
it('explains that owner other_costs prose is excluded from authoritative totals',()=>{
 render(<CostBreakdown listing={{rent_amount:100,admin_fee:0,utilities_amount:0,utilities_basis:'INCLUDED',parking_fee:0,monthly_total_estimate:200,deposit_amount:0,move_in_total:300,currency:'PLN',other_costs:'Synthetic description'}}/>);expect(screen.getByText(/Synthetic description/)).toHaveTextContent(/nie wliczon/i);
});
