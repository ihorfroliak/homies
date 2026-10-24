import { ConversationWorkspace } from "@/engagement/conversations";
export const metadata = { robots: { index: false, follow: false } };
export default function Page() { return <ConversationWorkspace provider />; }
