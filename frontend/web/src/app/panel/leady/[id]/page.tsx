import { ConversationWorkspace } from "@/engagement/conversations";
export const metadata = { robots: { index: false, follow: false } };
export default async function Page({ params }: { params: Promise<{ id: string }> }) { const { id } = await params; return <ConversationWorkspace provider conversationId={id} />; }
