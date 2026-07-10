import React, { useState, useRef, useEffect } from "react";
import api from "@/lib/api";
import { Sparkle, X, PaperPlaneRight } from "@phosphor-icons/react";
import VoiceButton from "@/components/VoiceButton";

const suggestions = [
  "How much do I owe Rajesh?",
  "What is today's labour cost?",
  "Which workers have taken advances?",
  "Who worked at Skyline Towers this week?",
];

export default function AIAssistant({ open, onClose }) {
  const [messages, setMessages] = useState([
    { role: "ai", text: "I'm your operations assistant. Ask me about workforce, wages, advances, settlements or projects." },
  ]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  const ask = async (question) => {
    if (!question.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", text: question }]);
    setQ("");
    setLoading(true);
    try {
      const res = await api.post("/assistant/ask", { question });
      setMessages((m) => [...m, { role: "ai", text: res.data.answer }]);
    } catch {
      setMessages((m) => [...m, { role: "ai", text: "Sorry, I couldn't fetch that right now." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div
        className={`fixed inset-0 bg-black/40 z-50 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0 pointer-events-none"}`}
        onClick={onClose}
      />
      <aside
        data-testid="ai-assistant-panel"
        className={`fixed top-0 right-0 h-full w-full sm:w-[440px] bg-[#FAFAFA] border-l border-[#E4E4E7] z-50 flex flex-col transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}
      >
        <div className="h-16 flex items-center justify-between px-5 border-b border-[#E4E4E7] bg-white">
          <div className="flex items-center gap-2">
            <Sparkle size={18} weight="fill" className="text-[#EA580C]" />
            <span className="font-display font-bold">AI Operations Assistant</span>
          </div>
          <button data-testid="close-assistant-button" onClick={onClose} className="text-[#71717A] hover:text-[#09090B] transition-colors duration-200">
            <X size={20} weight="bold" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] px-4 py-3 text-sm whitespace-pre-wrap border ${
                  m.role === "user"
                    ? "bg-[#09090B] text-white border-[#09090B]"
                    : "bg-white text-[#09090B] border-[#E4E4E7]"
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-[#E4E4E7] px-4 py-3 flex gap-1">
                <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" />
                <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" style={{ animationDelay: "0.2s" }} />
                <span className="w-1.5 h-1.5 bg-[#EA580C] pulse-dot" style={{ animationDelay: "0.4s" }} />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {messages.length <= 1 && (
          <div className="px-5 pb-3 grid grid-cols-1 gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                data-testid="assistant-suggestion"
                onClick={() => ask(s)}
                className="text-left text-xs font-medium border border-[#E4E4E7] bg-white px-3 py-2 hover:border-[#EA580C] hover:text-[#EA580C] transition-colors duration-200"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <form
          onSubmit={(e) => { e.preventDefault(); ask(q); }}
          className="p-4 border-t border-[#E4E4E7] bg-white flex gap-2"
        >
          <input
            data-testid="assistant-input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask anything about your operations…"
            className="flex-1 border-2 border-[#E4E4E7] focus:border-[#EA580C] outline-none px-3 py-2.5 text-sm transition-colors duration-200"
          />
          <VoiceButton
            showLang={false}
            title="Speak your question"
            onResult={(text) => {
              setQ(text);
              ask(text);
            }}
          />
          <button
            data-testid="assistant-send-button"
            type="submit"
            disabled={loading}
            className="bg-[#09090B] text-white px-4 hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50"
          >
            <PaperPlaneRight size={18} weight="fill" />
          </button>
        </form>
      </aside>
    </>
  );
}
