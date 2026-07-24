import React, { useState } from "react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DownloadSimple, FilePdf, FileDoc, FileXls, CaretDown } from "@phosphor-icons/react";
import api from "@/lib/api";
import { toast } from "sonner";

const FORMATS = [
  { key: "pdf", label: "PDF", icon: FilePdf },
  { key: "docx", label: "Word (.docx)", icon: FileDoc },
  { key: "xlsx", label: "Excel (.xlsx)", icon: FileXls },
];

/**
 * Generic export dropdown.
 * @param {string} endpoint  API path relative to `/api`, e.g. "/payroll/export".
 * @param {string} filename  Suggested filename stem (extension added automatically).
 * @param {string} label     Button label.
 */
export default function ExportMenu({ endpoint, filename = "export", label = "Export", size = "md", disabled = false, testId = "export-menu" }) {
  const [busy, setBusy] = useState(null);

  const download = async (fmt) => {
    setBusy(fmt);
    try {
      const res = await api.get(endpoint, { params: { format: fmt }, responseType: "blob" });
      const blob = new Blob([res.data], { type: res.headers["content-type"] });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${filename}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
      toast.success(`${fmt.toUpperCase()} ready`);
    } catch (e) {
      if (process.env.NODE_ENV !== "production") console.error("Export failed:", e);
      // With responseType:'blob', error responses arrive as blobs — decode JSON if possible.
      let detail = "server error";
      const blob = e?.response?.data;
      if (blob instanceof Blob) {
        try {
          const text = await blob.text();
          const parsed = JSON.parse(text);
          detail = parsed?.detail || text || detail;
        } catch { /* not JSON */ }
      } else if (e?.response?.data?.detail) {
        detail = e.response.data.detail;
      }
      toast.error(`Couldn't generate ${fmt.toUpperCase()} — ${detail}`);
    } finally {
      setBusy(null);
    }
  };

  const btnCls = size === "sm"
    ? "flex items-center gap-1.5 border-2 border-[#09090B] px-2.5 py-1.5 text-xs font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-50"
    : "flex items-center gap-2 border-2 border-[#09090B] px-3 py-2 text-sm font-semibold hover:bg-[#09090B] hover:text-white transition-colors duration-200 disabled:opacity-50";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button data-testid={testId} disabled={disabled || !!busy} className={btnCls}>
          <DownloadSimple size={size === "sm" ? 14 : 16} weight="bold" />
          {busy ? `${busy.toUpperCase()}…` : label}
          <CaretDown size={12} weight="bold" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="rounded-none border-2 border-[#09090B] p-0 min-w-[180px]">
        {FORMATS.map((f) => (
          <DropdownMenuItem
            key={f.key}
            data-testid={`${testId}-${f.key}`}
            onSelect={() => download(f.key)}
            disabled={!!busy}
            className="rounded-none flex items-center gap-2 px-3 py-2.5 text-sm cursor-pointer focus:bg-[#FFF7ED] focus:text-[#09090B] hover:bg-[#FFF7ED] transition-colors duration-150"
          >
            <f.icon size={16} weight="duotone" className="text-[#EA580C]" />
            <span className="font-medium">{f.label}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
