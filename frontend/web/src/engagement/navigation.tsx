"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "./api";
import { e } from "./copy";
import { useSession } from "./session";
import { ContextSwitch } from "./viewings";
import { ErrorNotice } from "./ui";

export function EngagementNavigation() {
  const session = useSession(); const [error, setError] = useState<unknown>(); const [pending, setPending] = useState(false);
  async function logout() { setPending(true); setError(undefined); try { await api("/auth/logout", "POST"); await session.refresh(); } catch (error) { setError(error); } finally { setPending(false); } }
  return <><li><Link href="/zapisane">{e.saved}</Link></li><li><Link href="/wiadomosci">{e.inbox}</Link></li><li><Link href="/ogladania">{e.myViewings}</Link></li>{session.user ? <><li><ContextSwitch /></li><li><button className="btn" disabled={pending} onClick={() => void logout()}>{e.logout}</button><ErrorNotice error={error} /></li></> : <li><button className="btn" onClick={() => void session.ensure({ action: "account" })}>{e.login}</button></li>}</>;
}
