import { useEffect, useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { ChatBubble, type ChatMessage } from "../components/ChatBubble";
import "./AskAI.css";

const SUGGESTIONS = ["What's in my videos?", "Show me outdoor photos", "Any videos with people talking?"];

export function AskAIPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text:
        "Ask me anything about your vault — I retrieve from your filenames, tags, and video transcripts, then answer with citations you can click.",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text: string) => {
    if (!text.trim() || sending) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      const res = await api.ask(text);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: res.answer, provider: res.provider, citations: res.citations },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Something went wrong reaching the backend: ${(err as Error).message}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <span className="eyebrow">Ask your vault</span>
        <h1>
          <Sparkles size={22} style={{ verticalAlign: -4, marginRight: 6, color: "var(--accent)" }} />
          Ask AI<span className="heading-period">.</span>
        </h1>
        <p>A retrieval-augmented assistant that only answers from your own vault — every claim is cited.</p>
      </div>

      <div className="glass-card ask-layout">
        <div className="ask-messages" ref={scrollRef}>
          {messages.map((m, i) => (
            <ChatBubble key={i} message={m} />
          ))}
          {sending && <ChatBubble message={{ role: "assistant", text: "Thinking…" }} />}
        </div>

        {messages.length <= 1 && (
          <div className="ask-suggestions">
            {SUGGESTIONS.map((s) => (
              <span key={s} className="ask-suggestion" onClick={() => send(s)}>
                {s}
              </span>
            ))}
          </div>
        )}

        <form
          className="ask-input-row"
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
        >
          <input
            placeholder="Ask about your photos and videos…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button className="btn btn-primary" type="submit" disabled={sending}>
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
