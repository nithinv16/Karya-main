import React, { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { Terminal, ArrowRight } from "@phosphor-icons/react";
import VoiceButton from "@/components/VoiceButton";

const examples = [
  "Ramesh took an advance of ₹5000",
  "Pay Manoj ₹12000",
  "Ten workers arrived today at Skyline Towers",
  "Add worker Sunil as mason at 950 daily",
];

export default function CommandBar() {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [ph, setPh] = useState(0);
  const qc = useQueryClient();

  React.useEffect(() => {
    const t = setInterval(() => setPh((p) => (p + 1) % examples.length), 3200);
    return () => clearInterval(t);
  }, []);

  const runCommand = async (cmd) => {
    if (!cmd.trim() || loading) return;
    setLoading(true);
    try {
      const res = await api.post("/command", { text: cmd });
      if (res.data.applied) {
        toast.success(res.data.summary || "Done");
        qc.invalidateQueries();
      } else {
        toast.warning(res.data.summary || "Couldn't apply that.");
      }
      setText("");
    } catch {
      toast.error("Command failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const onVoice = (transcript) => {
    setText(transcript);
    toast.message("Heard: " + transcript);
    runCommand(transcript);
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); runCommand(text); }} className="flex-1 flex items-center gap-2" data-testid="command-bar">
      <div className="flex items-center gap-2 flex-1 border-2 border-[#09090B] focus-within:border-[#EA580C] transition-colors duration-200 bg-white">
        <Terminal size={18} weight="bold" className="ml-3 text-[#EA580C] shrink-0" />
        <input
          data-testid="command-bar-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={`Type or speak — e.g. "${examples[ph]}"`}
          className="flex-1 py-2.5 pr-2 text-sm font-mono bg-transparent outline-none placeholder:text-[#a1a1aa]"
        />
        <button
          type="submit"
          data-testid="command-bar-submit"
          disabled={loading}
          className="h-full px-3 py-2.5 bg-[#09090B] text-white hover:bg-[#EA580C] transition-colors duration-200 disabled:opacity-50 shrink-0"
        >
          {loading ? <span className="w-2 h-2 bg-white block pulse-dot" /> : <ArrowRight size={16} weight="bold" />}
        </button>
      </div>
      <VoiceButton onResult={onVoice} title="Speak a command" />
    </form>
  );
}
