import { AuthForm } from "@/engagement/session";
import { e } from "@/engagement/copy";
export const metadata = { title: e.register, robots: { index: false, follow: false } };
export default function Page() { return <div className="container state"><h1>{e.register}</h1><AuthForm registration /></div>; }
