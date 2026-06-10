import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, Info, TriangleAlert, User } from "lucide-react";
import { cn } from "../lib/utils.js";
import ResultCards from "./ResultCards.jsx";

const proseClasses = cn(
  "prose prose-sm max-w-none dark:prose-invert",
  "prose-p:my-2 prose-headings:mb-2 prose-headings:mt-3 prose-headings:tracking-tight",
  "prose-strong:text-foreground",
  "prose-a:text-primary prose-a:underline-offset-4 hover:prose-a:underline",
  "prose-code:rounded prose-code:bg-secondary prose-code:px-1 prose-code:py-0.5 prose-code:text-xs",
  "prose-ul:my-2 prose-li:my-0.5",
);

function SystemBubble({ content }) {
  return (
    <div className="animate-fade-in rounded-xl border border-border bg-secondary/60 px-4 py-3 text-xs text-muted-foreground">
      <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-foreground/70">
        <Info className="h-3.5 w-3.5" />
        Notice
      </div>
      <div className="whitespace-pre-line leading-relaxed">{content}</div>
    </div>
  );
}

function Avatar({ isUser, isError }) {
  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
        isUser && "bg-secondary text-secondary-foreground",
        !isUser && isError && "bg-destructive/15 text-destructive",
        !isUser && !isError && "bg-primary text-primary-foreground",
      )}
    >
      {isUser ? (
        <User className="h-4 w-4" />
      ) : isError ? (
        <TriangleAlert className="h-4 w-4" />
      ) : (
        <Bot className="h-4 w-4" />
      )}
    </div>
  );
}

function UserMessage({ content }) {
  return (
    <div className="flex animate-fade-in flex-row-reverse gap-3">
      <Avatar isUser />
      <div className="max-w-[85%] rounded-2xl border border-primary/20 bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground shadow-sm">
        <p className="whitespace-pre-wrap">{content}</p>
      </div>
    </div>
  );
}

function AssistantError({ content }) {
  return (
    <div className="flex animate-fade-in gap-3">
      <Avatar isError />
      <div className="max-w-[85%] rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm leading-relaxed text-destructive shadow-sm">
        <div className={proseClasses}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

function AssistantMessage({ content, results }) {
  const hasCards = results && (
    (results.type === "agencies" && results.items_agencies?.length) ||
    (results.type === "doctors" && results.items_doctors?.length)
  );

  // Plain markdown bubble when there are no structured results.
  if (!hasCards) {
    return (
      <div className="flex animate-fade-in gap-3">
        <Avatar />
        <div className="max-w-[85%] rounded-2xl border border-border bg-card px-4 py-3 text-sm leading-relaxed text-card-foreground shadow-sm">
          <div className={proseClasses}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
        </div>
      </div>
    );
  }

  // With results, widen the container to a full-width panel and render cards.
  return (
    <div className="flex animate-fade-in gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
        <ResultCards results={results} />
      </div>
    </div>
  );
}

export default function ChatMessage({ role, content, kind, results }) {
  if (role === "system") return <SystemBubble content={content} />;
  if (role === "user") return <UserMessage content={content} />;
  if (kind === "error") return <AssistantError content={content} />;
  return <AssistantMessage content={content} results={results} />;
}
