import { useCallback, useState } from "react";
import { postQuery } from "../lib/api.js";

const SYSTEM_PROMPT = `Pointer helps you find the right local service quickly — just describe what you need in plain English.
Do not include sensitive information; conversations may be reviewed during development.
Pointer is experimental — double-check important information before acting on it.
Also available by text at 866-764-4632.`;

export function useChat() {
  const [messages, setMessages] = useState([
    { role: "system", content: SYSTEM_PROMPT },
  ]);
  const [pending, setPending] = useState(false);

  const send = useCallback(
    async (text) => {
      const trimmed = text.trim();
      if (!trimmed || pending) return;

      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
      setPending(true);

      try {
        const { markdown, results } = await postQuery(trimmed);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: markdown || "No response from API.",
            results: results || null,
          },
        ]);
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Request failed: ${err.message}`,
            kind: "error",
          },
        ]);
      } finally {
        setPending(false);
      }
    },
    [pending],
  );

  return { messages, pending, send };
}
