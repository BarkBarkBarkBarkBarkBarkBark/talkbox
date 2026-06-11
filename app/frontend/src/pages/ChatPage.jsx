import { useEffect, useRef } from "react";
import { Sparkles } from "lucide-react";
import ChatInput from "../components/ChatInput.jsx";
import ChatMessage from "../components/ChatMessage.jsx";
import { Spinner } from "../components/ui/Spinner.jsx";
import { useChat } from "../hooks/useChat.js";

const SUGGESTIONS = [
  "I need a shelter for tonight",
  "Where can I find free food in Sacramento?",
  "I am a veteran and I need housing help",
  "I need a mental-health clinic that accepts Medi-Cal",
];

export default function ChatPage() {
  const { messages, pending, send } = useChat();
  const endRef = useRef(null);
  const hasConversation = messages.some((m) => m.role !== "system");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, pending]);

  return (
    <div className="mx-auto flex h-[calc(100vh-56px)] max-w-3xl flex-col px-4 py-6 sm:px-6">
      <div className="mb-4">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          <Sparkles className="h-3.5 w-3.5 text-primary" />
          Routing console
        </div>
        <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
          Ask Talk Box
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Describe the need in natural language — Talk Box will route it to the right local
          service and return contact details.
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto pr-1">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} {...msg} />
        ))}

        {!hasConversation ? (
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => send(s)}
                className="group rounded-xl border border-border bg-card px-4 py-3 text-left text-sm text-foreground shadow-sm transition hover:border-primary/60 hover:bg-secondary/60"
              >
                <span className="text-muted-foreground group-hover:text-foreground">“</span>
                {s}
                <span className="text-muted-foreground group-hover:text-foreground">”</span>
              </button>
            ))}
          </div>
        ) : null}

        {pending ? (
          <div className="flex items-center gap-3 px-1 text-sm text-muted-foreground">
            <Spinner size="sm" />
            Talk Box is thinking…
          </div>
        ) : null}
        <div ref={endRef} />
      </div>

      <div className="mt-4 pb-4">
        <ChatInput onSend={send} disabled={pending} />
        <p className="mt-2 text-center text-[11px] text-muted-foreground">
          Experimental — double-check important info. Avoid sharing sensitive data.
        </p>
      </div>
    </div>
  );
}
