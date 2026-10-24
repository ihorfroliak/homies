import { AuthForm } from "@/engagement/session";
import { e } from "@/engagement/copy";
export const metadata = { title: e.login, robots: { index: false, follow: false } };
export default function Page() { return <div className="container state"><h1>{e.login}</h1><AuthForm /></div>; }
